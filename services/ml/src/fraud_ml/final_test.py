"""One owner-authorized evaluation of an immutable package, without fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from threadpoolctl import threadpool_limits

from .data import DEFAULT_DATA_DIR, verify_audit, verify_source
from .ensemble.reporting import code_record, write_json
from .features import SOURCE_INPUT_COLUMNS, FeatureStream, source_to_event
from .serving import FrozenScorer, sha256


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def wilson(successes, total):
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return [max(0.0, center - width), min(1.0, center + width)]


def policy_metrics(counts, policy):
    fraud, legitimate = counts["fraud"], counts["legitimate"]
    routed = counts["fraud_review"] + counts["fraud_block"]
    review_rate = (counts["fraud_review"] + counts["legitimate_review"]) / (
        fraud + legitimate
    )
    metrics = {
        "fraud_routed_rate": routed / fraud,
        "false_block_rate": counts["legitimate_block"] / legitimate,
        "false_block_wilson_95": wilson(counts["legitimate_block"], legitimate),
        "fraud_routed_wilson_95": wilson(routed, fraud),
        "reviews_per_hour_normal": review_rate
        * policy["normal_transactions_per_second"]
        * 3600,
        "reviews_per_hour_peak": review_rate
        * policy["peak_transactions_per_second"]
        * 3600,
        "reviews_per_staffed_day_normal": review_rate
        * policy["normal_transactions_per_second"]
        * 3600
        * policy["staffed_hours_per_day"],
    }
    checks = {
        "fraud_routing": metrics["fraud_routed_rate"]
        >= policy["minimum_fraud_routed_rate"],
        "legitimate_false_blocks": metrics["false_block_rate"]
        <= policy["maximum_false_block_rate"],
        "normal_review_capacity": metrics["reviews_per_hour_normal"]
        <= policy["maximum_reviews_per_hour"],
        "peak_review_capacity": metrics["reviews_per_hour_peak"]
        <= policy["maximum_reviews_per_hour"],
        "staffed_day_review_capacity": metrics["reviews_per_staffed_day_normal"]
        <= policy["maximum_reviews_per_staffed_day"],
    }
    return metrics, checks


def verify_authorization(path, pin):
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        record.get("evaluation_kind") != "reserved_test"
        or record.get("bundle_sha256") != pin
        or not record.get("owner_authorized_at")
        or record.get("maximum_evaluations") != 1
        or record.get("threshold_changes_permitted") is not False
        or record.get("test_result_tuning_permitted") is not False
        or record.get("review_threshold") != 0.1
        or record.get("block_threshold") != 0.25
    ):
        raise ValueError(
            "Explicit exact-package single-evaluation authorization required"
        )
    return record


@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    authorization = verify_authorization(args.authorization, args.bundle_sha256)
    scorer = FrozenScorer(args.bundle, args.bundle_sha256)
    references = scorer.verify_references()
    if (scorer.r, scorer.b) != (
        authorization["review_threshold"],
        authorization["block_threshold"],
    ):
        raise ValueError("Authorized thresholds do not match frozen package")
    verify_audit()
    # Exclusive directory is a durable single-use guard before any test access.
    output = Path("reports/final-test") / args.bundle_sha256
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    write_json(
        output / "started.json",
        {
            "authorization": authorization,
            "started_at": datetime.now(UTC).isoformat(),
            "bundle_sha256": args.bundle_sha256,
            "code": code_record(),
        },
    )
    train_hash = verify_source(args.data_dir / "fraudTrain.csv")
    test_hash = verify_source(args.data_dir / "fraudTest.csv")
    options = {"dtype": {name: "string" for name in SOURCE_INPUT_COLUMNS}}
    frame = pd.read_csv(
        args.data_dir / "fraudTest.csv",
        usecols=[*SOURCE_INPUT_COLUMNS, "is_fraud"],
        **options,
    )
    frame = frame.sort_values(
        ["trans_date_trans_time", "trans_num"], kind="stable"
    ).reset_index(drop=True)
    labels = frame.pop("is_fraud").to_numpy()
    if (
        len(labels) != 555719
        or set(np.unique(labels)) != {0, 1}
        or np.sum(labels) != 2145
    ):
        raise ValueError("Reserved-test coverage differs from audit")
    cutoff = (
        pd.Timestamp(frame.iloc[0]["trans_date_trans_time"]) - pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d %H:%M:%S")
    key, stream = secrets.token_bytes(32), FeatureStream()
    warm = []
    for chunk in pd.read_csv(
        args.data_dir / "fraudTrain.csv",
        usecols=list(SOURCE_INPUT_COLUMNS),
        chunksize=100_000,
        **options,
    ):
        warm.append(chunk.loc[chunk["trans_date_trans_time"] >= cutoff])
    history = pd.concat(warm).sort_values(
        ["trans_date_trans_time", "trans_num"], kind="stable"
    )
    del warm
    for values in history.loc[:, list(SOURCE_INPUT_COLUMNS)].itertuples(
        index=False, name=None
    ):
        stream.transform(
            source_to_event(dict(zip(SOURCE_INPUT_COLUMNS, values, strict=True)), key)
        )
    warm_rows = len(history)
    del history
    probabilities = np.empty(len(frame), dtype=np.float64)
    actions = np.empty(len(frame), dtype="U6")
    batch = []
    for index, values in enumerate(
        frame.loc[:, list(SOURCE_INPUT_COLUMNS)].itertuples(index=False, name=None)
    ):
        batch.append(
            stream.transform(
                source_to_event(
                    dict(zip(SOURCE_INPUT_COLUMNS, values, strict=True)), key
                )
            )
        )
        if len(batch) == 8192 or index + 1 == len(frame):
            first = index + 1 - len(batch)
            probabilities[first : index + 1], actions[first : index + 1] = scorer.score(
                batch
            )
            batch.clear()
            if (index + 1) % 81920 == 0:
                print(f"Evaluated {index + 1} authorized rows", flush=True)
    counts = {"fraud": int(np.sum(labels)), "legitimate": int(np.sum(labels == 0))}
    for prefix, label in (("fraud", 1), ("legitimate", 0)):
        for action in ("Pass", "Review", "Block"):
            counts[f"{prefix}_{action.lower()}"] = int(
                np.sum((labels == label) & (actions == action))
            )
    metrics, checks = policy_metrics(counts, scorer.policy)
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "evaluation_kind": "reserved_test",
        "bundle_sha256": args.bundle_sha256,
        "policy_sha256": digest(scorer.policy),
        "test_source_sha256": test_hash,
        "history_source_sha256": train_hash,
        "history_warmup_rows": warm_rows,
        "history_basis": "Earlier training attempts within the first test transaction's 24-hour lookback; no history labels",
        "authorization": authorization,
        "authorization_file_sha256": sha256(args.authorization),
        "reference_verification": references,
        "completed_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "metrics": {
            **metrics,
            "average_precision": average_precision_score(labels, probabilities),
            "roc_auc": roc_auc_score(labels, probabilities),
            "brier_score": brier_score_loss(labels, probabilities),
        },
        "acceptance_checks": checks,
        "prediction_sha256": hashlib.sha256(
            probabilities.astype("<f8").tobytes() + actions.astype("S6").tobytes()
        ).hexdigest(),
        "tuning_performed": False,
        "confidence_interval_basis": "Wilson binomial descriptive intervals; correlated transactions may invalidate independence assumption",
        "limitations": "Synthetic dataset; workload-scaled review expectations are not a measured real-world arrival guarantee; no live activation by evaluator",
    }
    write_json(output / "report.json", report)
    print(
        json.dumps(
            {
                "report": str(output / "report.json"),
                "sha256": sha256(output / "report.json"),
                "status": report["status"],
                "counts": counts,
                "metrics": metrics,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
