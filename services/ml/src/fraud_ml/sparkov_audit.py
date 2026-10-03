"""Aggregate-only source audit; never emits source identities or row samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

DATASET_HANDLE = "kartik2112/fraud-detection/versions/1"
SOURCE_COLUMNS = (
    "Unnamed: 0",
    "trans_date_trans_time",
    "cc_num",
    "merchant",
    "category",
    "amt",
    "first",
    "last",
    "gender",
    "street",
    "city",
    "state",
    "zip",
    "lat",
    "long",
    "city_pop",
    "job",
    "dob",
    "trans_num",
    "unix_time",
    "merch_lat",
    "merch_long",
    "is_fraud",
)
SOURCE_FILES = ("fraudTrain.csv", "fraudTest.csv")


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_source(path: Path, *, usecols=None) -> pd.DataFrame:
    return pd.read_csv(
        path, dtype={"cc_num": "string", "trans_num": "string"}, usecols=usecols
    )


def audit_file(path: Path):
    from collections import Counter

    counts, nulls, offsets, checks = Counter(), Counter(), Counter(), Counter()
    cards, merchants, categories = set(), set(), set()
    ids, row_hashes, content_hashes, time_values = [], [], [], []
    rows = descending_pairs = 0
    first_time = last_time = previous_time = None
    amount_min, amount_max = float("inf"), float("-inf")
    monotonic = True
    for frame in pd.read_csv(
        path, dtype={"cc_num": "string", "trans_num": "string"}, chunksize=25_000
    ):
        if tuple(frame.columns) != SOURCE_COLUMNS:
            raise ValueError(f"Unexpected schema in {path.name}")
        dtypes = {key: str(value) for key, value in frame.dtypes.items()}
        times = pd.to_datetime(
            frame.trans_date_trans_time, format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )
        unix = pd.to_datetime(frame.unix_time, unit="s", errors="coerce")
        time_values.append(times.to_numpy(dtype="datetime64[ns]"))
        offsets.update((times - unix).dt.total_seconds().value_counts().to_dict())
        counts.update(frame.is_fraud.value_counts().to_dict())
        nulls.update(frame.isna().sum().to_dict())
        numeric = frame.select_dtypes(include="number")
        checks.update(
            {
                "nulls": int(frame.isna().sum().sum()),
                "nonfinite_numeric": int((~np.isfinite(numeric)).sum().sum()),
                "invalid_labels": int((~frame.is_fraud.isin([0, 1])).sum()),
                "invalid_times": int(times.isna().sum() + unix.isna().sum()),
                "calendar_shift_mismatches": int(
                    (times != unix + pd.DateOffset(years=7)).sum()
                ),
                "invalid_transaction_ids": int(
                    (~frame.trans_num.str.fullmatch(r"[a-f0-9]{32}")).sum()
                ),
                "invalid_card_ids": int((~frame.cc_num.str.fullmatch(r"[0-9]+")).sum()),
                "negative_amounts": int((frame.amt < 0).sum()),
                "subcent_amounts": int(
                    (np.abs(frame.amt * 100 - np.round(frame.amt * 100)) > 1e-6).sum()
                ),
            }
        )
        ids.append(frame.trans_num.to_numpy(dtype="S32"))
        row_hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy())
        content_hashes.append(
            pd.util.hash_pandas_object(
                frame.drop(columns="Unnamed: 0"), index=False
            ).to_numpy()
        )
        cards.update(frame.cc_num)
        merchants.update(frame.merchant)
        categories.update(frame.category)
        monotonic = (
            monotonic
            and times.is_monotonic_increasing
            and (previous_time is None or times.iloc[0] >= previous_time)
        )
        descending_pairs += int((times.diff().dt.total_seconds() < 0).sum()) + int(
            previous_time is not None and times.iloc[0] < previous_time
        )
        first_time = times.min() if first_time is None else min(first_time, times.min())
        last_time = times.max() if last_time is None else max(last_time, times.max())
        previous_time = times.iloc[-1]
        amount_min = min(amount_min, float(frame.amt.min()))
        amount_max = max(amount_max, float(frame.amt.max()))
        rows += len(frame)
        if rows % 250_000 == 0:
            print(f"Auditing {path.name}: {rows} rows", flush=True)
    identities = np.concatenate(ids)
    checks["duplicate_transaction_ids"] = rows - len(np.unique(identities))
    duplicate_rows = rows - len(np.unique(np.concatenate(row_hashes)))
    duplicate_contents = rows - len(np.unique(np.concatenate(content_hashes)))
    equal_times = rows - len(np.unique(np.concatenate(time_values)))
    report = {
        "bytes": path.stat().st_size,
        "sha256": file_hash(path),
        "rows": rows,
        "columns": list(SOURCE_COLUMNS),
        "dtypes": dtypes,
        "class_counts": {str(k): int(v) for k, v in counts.items()},
        "fraud_prevalence": counts[1] / rows,
        "nulls_by_column": dict(nulls),
        "checks": dict(checks),
        "duplicate_rows": duplicate_rows,
        "duplicate_rows_without_export_index": duplicate_contents,
        "duplicate_method": "64-bit row fingerprints: zero rules out exact duplicates; candidates require exact follow-up. Transaction IDs checked exactly.",
        "unique_cards": len(cards),
        "unique_merchants": len(merchants),
        "categories": sorted(categories),
        "event_time_min": str(first_time),
        "event_time_max": str(last_time),
        "file_time_monotonic": bool(monotonic),
        "descending_time_pairs": descending_pairs,
        "equal_time_rows": equal_times,
        "text_minus_unix_seconds": {str(k): int(v) for k, v in offsets.items()},
        "amount_min": amount_min,
        "amount_max": amount_max,
    }
    failures = [f"{path.name}:{key}" for key, value in checks.items() if value]
    if duplicate_rows or duplicate_contents:
        failures.append(f"{path.name}:duplicate_row_candidates")
    print(f"Audited {path.name}: {rows} rows", flush=True)
    return report, identities, cards, (first_time, last_time), failures


def audit_sources(directory: Path) -> dict:
    reports, identities, time_bounds, card_sets = {}, {}, {}, {}
    gates = []
    for name in SOURCE_FILES:
        (
            reports[name],
            identities[name],
            card_sets[name],
            time_bounds[name],
            failures,
        ) = audit_file(directory / name)
        gates.extend(failures)
    overlap = len(
        np.intersect1d(identities[SOURCE_FILES[0]], identities[SOURCE_FILES[1]])
    )
    forward = time_bounds[SOURCE_FILES[0]][1] < time_bounds[SOURCE_FILES[1]][0]
    if overlap:
        gates.append("cross_file_duplicate_transaction_ids")
    if not forward:
        gates.append("supplied_test_is_not_strictly_later")
    result = {
        "dataset_handle": DATASET_HANDLE,
        "dataset_version": 1,
        "source_url": "https://www.kaggle.com/datasets/kartik2112/fraud-detection",
        "license_listing": "CC0: Public Domain",
        "license_verified_via": "https://www.kaggle.com/api/v1/datasets/list?search=kartik2112%2Ffraud-detection",
        "audited_at_utc": datetime.now(UTC).isoformat(),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "audit_code_sha256": file_hash(Path(__file__)),
        "files": reports,
        "cross_file_transaction_id_overlap": overlap,
        "cross_file_card_overlap": len(
            card_sets[SOURCE_FILES[0]] & card_sets[SOURCE_FILES[1]]
        ),
        "supplied_test_strictly_later": bool(forward),
        "clock_resolution": "Text time equals unix time plus seven calendar years; leap years change the seconds offset. Use text time only, interpreted as UTC simulation time; sort before history.",
        "test_access": "Source integrity and aggregate labels audited only; no features scored, model selection or evaluation.",
        "failed_checks": gates,
        "status": "PASS" if not gates else "FAIL",
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/sparkov-v1/source-audit.json")
    )
    args = parser.parse_args(argv)
    report = audit_sources(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
