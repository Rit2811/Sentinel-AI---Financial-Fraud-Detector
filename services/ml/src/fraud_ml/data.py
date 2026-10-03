"""Pinned Sparkov development loader; the future test is not a development input."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path

import numpy as np
import pandas as pd

from .features import (
    FEATURE_ORDER,
    FEATURE_VERSION,
    NUMERIC_FEATURES,
    SOURCE_INPUT_COLUMNS,
    FeatureStream,
    features_from_prior,
    source_to_event,
)
from .sparkov_audit import DATASET_HANDLE, SOURCE_COLUMNS, file_hash

SOURCE_HASHES = {
    "fraudTrain.csv": "fd7139200dbfcbed0b6742bbe05a4f1abce532c4fef20918228a651647a3e75d",
    "fraudTest.csv": "12d553ab19440c752d2531ee1af44bb64f12cc3d3839f1649f19e81c230545f0",
}
DEFAULT_DATA_DIR = Path("data/kagglehub/datasets/kartik2112/fraud-detection/versions/1")
CACHE_DIR = Path("artifacts/sparkov-v1")
DATASET_ID = "sparkov-kartik2112-v1"


def load_key(path: Path, *, create: bool = False) -> bytes:
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(secrets.token_bytes(32))
    key = path.read_bytes()
    if len(key) < 32:
        raise ValueError("Local replay key must contain at least 32 bytes")
    return key


def verify_source(path: Path) -> str:
    expected = SOURCE_HASHES.get(path.name)
    if expected is None or file_hash(path) != expected:
        raise ValueError("Source is not the pinned Sparkov version; audit before use")
    return expected


def verify_audit(path: Path = CACHE_DIR / "source-audit.json") -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("dataset_handle") != DATASET_HANDLE:
        raise ValueError("A passing pinned source audit is required before training")
    if (
        not report.get("supplied_test_strictly_later")
        or report.get("cross_file_transaction_id_overlap") != 0
    ):
        raise ValueError("Source chronology/identity gate failed")
    for name, expected in SOURCE_HASHES.items():
        if report["files"][name]["sha256"] != expected:
            raise ValueError("Audit does not match source pins")
    return report


def load_development(
    data_dir: Path, key: bytes
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    verify_audit()
    source = data_dir / "fraudTrain.csv"
    source_hash = verify_source(source)
    from . import features as feature_module

    fingerprint = {
        "dataset": DATASET_HANDLE,
        "source_sha256": source_hash,
        "feature_version": FEATURE_VERSION,
        "feature_code_sha256": file_hash(Path(feature_module.__file__)),
        "loader_code_sha256": file_hash(Path(__file__)),
        "key_fingerprint": hashlib.sha256(key).hexdigest(),
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / "development-features.npz"
    manifest_path = CACHE_DIR / "feature-cache.json"
    if cache.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("fingerprint") == fingerprint and manifest.get(
            "cache_sha256"
        ) == file_hash(cache):
            with np.load(cache, allow_pickle=False) as loaded:
                features = pd.DataFrame(loaded["numeric"], columns=NUMERIC_FEATURES)
                features["merchant_category"] = pd.Categorical(loaded["category"])
                labels = pd.Series(loaded["labels"], name="is_fraud")
                times = pd.Series(
                    pd.to_datetime(loaded["times"], utc=True), name="event_time"
                )
            print(
                "Verified development feature cache; locked test not loaded.",
                flush=True,
            )
            return features, labels, times

    if tuple(pd.read_csv(source, nrows=0).columns) != SOURCE_COLUMNS:
        raise ValueError("Unexpected source columns")
    frame = pd.read_csv(
        source,
        usecols=[*SOURCE_INPUT_COLUMNS, "is_fraud"],
        dtype={
            "cc_num": "string",
            "trans_num": "string",
            "merchant": "category",
            "category": "category",
        },
    )
    frame["_time"] = pd.to_datetime(
        frame.trans_date_trans_time, format="%Y-%m-%d %H:%M:%S", utc=True
    )
    frame = frame.sort_values(["_time", "trans_num"], kind="stable").reset_index(
        drop=True
    )
    labels = frame.pop("is_fraud").astype("int8").rename("is_fraud")
    times = frame.pop("_time").rename("event_time")
    numeric = np.empty((len(frame), len(NUMERIC_FEATURES)), dtype=np.float64)
    categories = frame["category"].astype(str).to_numpy(dtype="U32")
    stream = FeatureStream()
    parity_history = {}
    parity_count = 0
    for index, values in enumerate(
        frame.loc[:, list(SOURCE_INPUT_COLUMNS)].itertuples(index=False, name=None)
    ):
        row = dict(zip(SOURCE_INPUT_COLUMNS, values, strict=True))
        event = source_to_event(row, key)
        features = stream.transform(event)
        numeric[index] = [features[name] for name in NUMERIC_FEATURES]
        # Independent history query proves source/replay parity on real early rows.
        if index < 10_000:
            history = parity_history.setdefault(event["card_token"], [])
            if features != features_from_prior(event, history):
                raise ValueError("Historical/replay feature parity failed")
            history.append((int(times.iloc[index].timestamp()), event["amount_minor"]))
            parity_count += 1
        if (index + 1) % 250_000 == 0:
            print(f"Built {index + 1} point-in-time development rows", flush=True)
    del frame, stream, parity_history
    categories = categories.astype("U32")
    np.savez_compressed(
        cache,
        numeric=numeric,
        category=categories,
        labels=labels.to_numpy(),
        times=times.to_numpy(dtype="datetime64[ns]"),
    )
    manifest_path.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "cache_sha256": file_hash(cache),
                "rows": len(labels),
                "feature_order": list(FEATURE_ORDER),
                "parity_rows": parity_count,
                "parity_passed": True,
                "test_predictions_generated": False,
                "test_loaded_by_development": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    output = pd.DataFrame(numeric, columns=NUMERIC_FEATURES)
    output["merchant_category"] = pd.Categorical(categories)
    return output, labels, times
