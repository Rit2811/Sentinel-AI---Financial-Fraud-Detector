from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import sklearn
import kagglehub
import numpy
import pandas

from .data import (
    audit_dataset,
    kaggle_source_path,
    load_kaggle_dataset,
    load_local_dataset,
)
from .evaluation import evaluate_model
from .models import build_models, reduce_knn_majority
from .split import chronological_split


def _load(path: str | None):
    if path:
        source_path = Path(path)
        return load_local_dataset(source_path), source_path
    frame = load_kaggle_dataset()
    return frame, kaggle_source_path()


def audit_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-csv")
    parser.add_argument("--output", default="artifacts/dataset-audit.json")
    args = parser.parse_args()
    frame, source_path = _load(args.local_csv)
    report = audit_dataset(frame, source_path)
    _write_json(Path(args.output), report)


def baseline_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-csv")
    parser.add_argument("--output", default="artifacts/validation-metrics.json")
    args = parser.parse_args()
    frame, source_path = _load(args.local_csv)
    train, validation, test = chronological_split(frame)
    feature_names = [column for column in frame.columns if column != "Class"]
    train_x, train_y = train[feature_names], train["Class"]
    validation_x, validation_y = validation[feature_names], validation["Class"]
    results = {}
    for name, model in build_models().items():
        model_train_x, model_train_y = train_x, train_y
        if name == "knn":
            model_train_x, model_train_y = reduce_knn_majority(train_x, train_y)
        results[name] = evaluate_model(
            model, model_train_x, model_train_y, validation_x, validation_y
        )
    _write_json(
        Path(args.output),
        {
            "seed": 42,
            "versions": {
                "python": platform.python_version(),
                "sklearn": sklearn.__version__,
                "pandas": pandas.__version__,
                "numpy": numpy.__version__,
                "kagglehub": kagglehub.__version__,
            },
            "dataset_source": audit_dataset(frame, source_path)["source"],
            "split_rows": {
                "train": len(train),
                "validation": len(validation),
                "test_held_out": len(test),
            },
            "test_partition_evaluated": False,
            "models": results,
        },
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(path)
