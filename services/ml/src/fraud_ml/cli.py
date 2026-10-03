from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import sklearn
import joblib
import numpy
import pandas
from threadpoolctl import threadpool_info, threadpool_limits

from . import data
from .evaluation import all_legitimate_metrics, evaluate_model, score_model
from .features import FEATURE_ORDER, FEATURE_VERSION
from .models import build_models, reduce_knn_majority, validate_features
from .provenance import record_artifact_inventory, record_run_provenance
from .split import chronological_split, partition_summary


def audit_main() -> None:
    from .sparkov_audit import main

    main()


@threadpool_limits.wrap(limits=1)
def baseline_main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Sparkov Task 4 development baselines")
    parser.add_argument("--data-dir", type=Path, default=data.DEFAULT_DATA_DIR)
    parser.add_argument(
        "--key-file", type=Path, default=Path("secrets/replay-hmac.key")
    )
    parser.add_argument(
        "--artifacts-dir", type=Path, default=Path("artifacts/sparkov-v1")
    )
    parser.add_argument(
        "--report-dir", type=Path, default=Path("reports/sparkov-task4")
    )
    args = parser.parse_args(argv)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    artifacts, reports = args.artifacts_dir / run_id, args.report_dir / run_id
    _require_ignored_artifacts(artifacts)
    # The data boundary owns pinned-hash verification and reads only fraudTrain.
    features, labels, times = data.load_development(
        args.data_dir, data.load_key(args.key_file, create=True)
    )
    record_run_provenance(reports)
    validate_features(features)
    if not features.index.equals(labels.index) or not labels.index.equals(times.index):
        raise ValueError("Development features, labels and timestamps must be aligned")
    positions = dict(
        zip(
            ("train", "calibration", "validation"),
            chronological_split(times),
            strict=True,
        )
    )
    train, calibration, validation = (positions[name] for name in positions)
    train_x, train_y = features.iloc[train], labels.iloc[train]
    validation_x, validation_y = features.iloc[validation], labels.iloc[validation]
    report = {
        "status": "running",
        "run_id": run_id,
        "seed": 42,
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "pandas": pandas.__version__,
            "numpy": numpy.__version__,
            "joblib": joblib.__version__,
        },
        "dataset_source": {
            "handle": data.DATASET_HANDLE,
            "pinned_sha256": dict(data.SOURCE_HASHES),
            "data_dir": str(args.data_dir),
            "development_file": "fraudTrain.csv",
        },
        "feature_version": FEATURE_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "runtime": {
            "thread_limit": 1,
            "threadpools": [
                {
                    key: pool.get(key)
                    for key in ("internal_api", "num_threads", "version")
                }
                for pool in threadpool_info()
            ],
        },
        "split_policy": {
            "fractions": {"train": 0.6, "calibration": 0.2, "validation": 0.2},
            "ties": "advance boundary through the entire canonical timestamp group",
        },
        "partitions": {
            name: partition_summary(labels.iloc[rows], times.iloc[rows])
            for name, rows in positions.items()
        },
        "supplied_test": {"file": "fraudTest.csv", "status": "locked_unscored"},
        "test_partition_evaluated": False,
        "calibration_performed": False,
        "all_legitimate": all_legitimate_metrics(validation_y),
        "models": {},
    }
    _write_json(reports / "summary.json", report)
    artifacts.mkdir(parents=True, exist_ok=False)
    for name, model in build_models().items():
        print(f"Fitting {name}", flush=True)
        model_train_x, model_train_y = train_x, train_y
        started = time.perf_counter()
        if name == "knn":
            model_train_x, model_train_y = reduce_knn_majority(train_x, train_y)
        sampling_seconds = time.perf_counter() - started
        evidence = {
            "classifier_parameters": model.named_steps["classifier"].get_params(),
            "training": {
                "available": report["partitions"]["train"],
                "fitted_rows": len(model_train_y),
                "fitted_class_counts": {
                    str(value): int((model_train_y == value).sum()) for value in (0, 1)
                },
                "sampling": {
                    "method": "uniform majority without replacement, all fraud retained"
                    if name == "knn"
                    else "none: natural training partition",
                    "partition": "train",
                    "seed": 42,
                    "majority_limit": 10_000 if name == "knn" else None,
                    "seconds": sampling_seconds,
                },
            },
        }
        _write_json(reports / f"{name}.json", {**evidence, "status": "running"})
        result = {}
        try:
            result = evaluate_model(
                model,
                model_train_x,
                model_train_y,
                validation_x,
                validation_y,
                validation_scores_path=artifacts / f"{name}.validation.npy",
            )
            if result["status"].startswith("completed"):
                model_path = artifacts / f"{name}.joblib"
                joblib.dump(model, model_path)
                result["model_artifact"] = str(model_path)
                _write_json(
                    reports / f"{name}.json",
                    {**evidence, **result, "status": "saving_calibration_scores"},
                )
                started = time.perf_counter()
                calibration_scores = score_model(model, features.iloc[calibration])
                result["calibration_score_seconds"] = time.perf_counter() - started
                calibration_path = artifacts / f"{name}.calibration.npy"
                numpy.save(calibration_path, calibration_scores, allow_pickle=False)
                result["raw_scores"] = {
                    "validation": str(artifacts / f"{name}.validation.npy"),
                    "calibration": str(calibration_path),
                }
        except Exception as error:
            result = {
                **result,
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        report["models"][name] = {**evidence, **result}
        _write_json(reports / f"{name}.json", report["models"][name])
        _write_json(reports / "summary.json", report)
    statuses = [result["status"] for result in report["models"].values()]
    failed = any(status.startswith("failed") for status in statuses)
    report["status"] = (
        "failed"
        if failed
        else (
            "completed_with_warnings"
            if "completed_with_warnings" in statuses
            else "completed"
        )
    )
    _write_json(reports / "summary.json", report)
    if failed:
        raise SystemExit(1)
    record_artifact_inventory(artifacts, reports)


def _require_ignored_artifacts(directory: Path) -> None:
    for filename in ("probe.joblib", "probe.validation.npy", "probe.calibration.npy"):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(directory / filename)],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            raise ValueError(
                "Model and raw-score artifacts must be in a Git-ignored path"
            )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)
    print(path, flush=True)
