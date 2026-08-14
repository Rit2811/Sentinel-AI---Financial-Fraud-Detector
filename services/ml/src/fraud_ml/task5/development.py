from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np

from fraud_ml.data import load_local_dataset
from fraud_ml.task5.access import development_partitions
from fraud_ml.task5.artifacts import sha256_file, verify_checksums, write_checksums
from fraud_ml.task5.calibration import fit_calibrated_models
from fraud_ml.task5.config import (
    DATASET_SHA256,
    FEATURE_ORDER,
    MODEL_ORDER,
    Task5Config,
)
from fraud_ml.task5.fusion import fusion_analysis
from fraud_ml.task5.policy import named_profiles, threshold_tradeoffs
from fraud_ml.task5.reporting import (
    class_counts,
    code_record,
    environment_record,
    json_safe,
    write_json,
    write_model_card_scaffold,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Task 5 validation-only calibrated ensemble development."
    )
    parser.add_argument(
        "--local-csv",
        type=Path,
        default=Path("data/creditcard.csv"),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/task5"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/task5-development"),
    )
    return parser.parse_args(argv)


def run_development(local_csv: Path, report_dir: Path, artifact_dir: Path) -> dict:
    if not local_csv.is_file():
        raise FileNotFoundError(f"Dataset not found: {local_csv}")
    actual_sha256 = sha256_file(local_csv)
    if actual_sha256 != DATASET_SHA256:
        raise ValueError(
            f"Dataset SHA-256 mismatch: expected {DATASET_SHA256}, got {actual_sha256}"
        )

    config = Task5Config()
    frame = load_local_dataset(local_csv)
    partitions = development_partitions(frame)
    del frame

    train_x = partitions.train.loc[:, FEATURE_ORDER]
    train_y = partitions.train.loc[:, "Class"]
    validation_x = partitions.validation.loc[:, FEATURE_ORDER]
    validation_y = partitions.validation.loc[:, "Class"]
    validation_amounts = partitions.validation.loc[:, "Amount"]

    models = fit_calibrated_models(
        train_x,
        train_y,
        validation_x,
        validation_y,
        config,
    )
    fusion = fusion_analysis(models, train_y, validation_y, config)
    selected_scores = fusion["selected_scores"]
    decision_latency_ms = (
        sum(model.evidence["validation_score_seconds"] for model in models.values())
        * 1000
        / len(validation_y)
    )
    tradeoffs = threshold_tradeoffs(
        validation_y,
        selected_scores,
        validation_amounts,
        config.action_rate_grid,
        config.block_rate_grid,
        decision_latency_ms,
    )
    profiles = named_profiles(tradeoffs)
    available_profiles = [
        name for name, value in profiles.items() if value["available"]
    ]
    if not available_profiles:
        raise RuntimeError("No validation profile satisfies the declared constraints")
    recommended_profile = (
        "Balanced Demo"
        if profiles["Balanced Demo"]["available"]
        else available_profiles[0]
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name in MODEL_ORDER:
        joblib.dump(models[name].base_model, artifact_dir / f"{name}_model.joblib")
        joblib.dump(models[name].calibrator, artifact_dir / f"{name}_calibrator.joblib")
    joblib.dump(
        {
            "selected_fusion": fusion["selected_fusion"],
            "selected_weights": fusion["selected_weights"],
            "model_order": MODEL_ORDER,
        },
        artifact_dir / "fusion.joblib",
    )
    write_json(artifact_dir / "development_config.json", config.to_dict())
    np.savez_compressed(
        artifact_dir / "validation_scores.npz",
        target=np.asarray(validation_y, dtype=np.int8),
        selected_fusion=np.asarray(selected_scores, dtype=float),
        base_probabilities=np.asarray(fusion["base_validation_matrix"], dtype=float),
    )
    checksums = write_checksums(artifact_dir)
    verify_checksums(artifact_dir)

    safe_fusion = {
        key: value
        for key, value in fusion.items()
        if key not in {"selected_scores", "base_validation_matrix"}
    }
    locked_test = {
        "state": partitions.locked_test.state,
        "start_row": partitions.locked_test.start,
        "stop_row": partitions.locked_test.stop,
        "row_count": partitions.locked_test.row_count,
        "features_accessed": False,
        "labels_accessed": False,
        "predictions_generated": False,
    }
    validation_report = {
        "status": "AWAITING_M4_PROFILE_SELECTION",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset": {
            "path": local_csv.as_posix(),
            "sha256": actual_sha256,
        },
        "configuration": config.to_dict(),
        "environment": environment_record(),
        "code": code_record(),
        "partitions": {
            "training": {
                "rows": len(train_y),
                "class_counts": class_counts(train_y),
            },
            "validation": {
                "rows": len(validation_y),
                "class_counts": class_counts(validation_y),
            },
            "locked_test": locked_test,
        },
        "calibration": {name: model.evidence for name, model in models.items()},
        "fusion": safe_fusion,
        "profiles": profiles,
        "recommended_profile": recommended_profile,
        "artifact_inventory": sorted(checksums),
        "limitations": [
            "Validation-only results are not final test evidence.",
            "Amount summaries are benchmark scenarios, not confirmed loss avoided.",
            "The historical anonymized dataset is not a live issuer population.",
            "No live latency, fairness, customer-friction or review-capacity claims.",
        ],
    }
    write_json(report_dir / "validation_metrics.json", validation_report)
    write_json(
        report_dir / "threshold_tradeoffs.json",
        {
            "status": "VALIDATION_ONLY",
            "selected_fusion": fusion["selected_fusion"],
            "tradeoffs": tradeoffs,
            "profiles": profiles,
            "recommended_profile": recommended_profile,
            "amount_interpretation": "Benchmark scenario only; not loss avoided.",
        },
    )
    write_model_card_scaffold(
        report_dir / "model_card.md",
        partitions.locked_test.row_count,
        fusion["selected_fusion"],
        recommended_profile,
    )
    return json_safe(validation_report)


def main(argv=None):
    args = parse_args(argv)
    report = run_development(args.local_csv, args.report_dir, args.artifact_dir)
    print("Task 5 validation development completed.")
    print("Selected fusion:", report["fusion"]["selected_fusion"])
    print("Recommended profile:", report["recommended_profile"])
    print("Locked test:", report["partitions"]["locked_test"]["state"])
    print("Status:", report["status"])


if __name__ == "__main__":
    main()
