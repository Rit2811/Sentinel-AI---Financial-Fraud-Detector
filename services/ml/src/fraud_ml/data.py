from __future__ import annotations

import hashlib
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import kagglehub
import numpy as np
import pandas as pd
from kagglehub import KaggleDatasetAdapter

DATASET_HANDLE = "mlg-ulb/creditcardfraud"
FILE_PATH = "creditcard.csv"
LOCAL_DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / FILE_PATH
EXPECTED_COLUMNS = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class"]
EXPECTED_SHAPE = (284_807, 31)
EXPECTED_CLASS_COUNTS = {0: 284_315, 1: 492}


def load_kaggle_dataset() -> pd.DataFrame:
    try:
        frame = kagglehub.dataset_load(
            KaggleDatasetAdapter.PANDAS,
            DATASET_HANDLE,
            FILE_PATH,
        )
    except ValueError:
        cached_path = Path(kagglehub.dataset_download(DATASET_HANDLE, FILE_PATH))
        if not zipfile.is_zipfile(cached_path):
            raise
        _materialize_csv(cached_path)
        frame = pd.read_csv(LOCAL_DATASET_PATH)
    validate_dataset(frame)
    cached_path = Path(kagglehub.dataset_download(DATASET_HANDLE, FILE_PATH))
    _materialize_csv(cached_path)
    counts = {
        int(key): int(value) for key, value in frame["Class"].value_counts().items()
    }
    print("Dataset loaded and validated successfully.")
    print("Shape:", frame.shape)
    print("Class distribution:", counts)
    print("Fraud percentage:", round(frame["Class"].mean() * 100, 4), "%")
    print(frame.head())
    return frame


def _materialize_csv(cached_path: Path) -> None:
    LOCAL_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(cached_path):
        with zipfile.ZipFile(cached_path) as archive:
            with archive.open(FILE_PATH) as source:
                with LOCAL_DATASET_PATH.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
    elif cached_path.resolve() != LOCAL_DATASET_PATH.resolve():
        shutil.copy2(cached_path, LOCAL_DATASET_PATH)


def kaggle_source_path() -> Path:
    return LOCAL_DATASET_PATH


def load_local_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    validate_dataset(frame)
    return frame


def validate_dataset(frame: pd.DataFrame) -> None:
    if frame.shape != EXPECTED_SHAPE:
        raise ValueError(f"Expected shape {EXPECTED_SHAPE}, got {frame.shape}")
    if list(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError("Dataset columns or order do not match the locked schema")
    counts = {
        int(key): int(value) for key, value in frame["Class"].value_counts().items()
    }
    if counts != EXPECTED_CLASS_COUNTS:
        raise ValueError(f"Unexpected Class counts: {counts}")
    if frame.isna().any().any():
        raise ValueError("Dataset contains null values")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("Dataset contains non-finite values")
    if (frame[["Time", "Amount"]] < 0).any().any():
        raise ValueError("Time and Amount must be non-negative")


def audit_dataset(frame: pd.DataFrame, source_path: Path | None = None) -> dict:
    validate_dataset(frame)
    source = {
        "kaggle_handle": DATASET_HANDLE,
        "file_name": FILE_PATH,
        "acquired_at_utc": datetime.now(UTC).isoformat(),
    }
    if source_path:
        raw = source_path.read_bytes()
        source.update(
            {
                "path": str(source_path),
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "source": source,
        "shape": list(frame.shape),
        "columns": list(frame.columns),
        "dtypes": {key: str(value) for key, value in frame.dtypes.items()},
        "class_counts": EXPECTED_CLASS_COUNTS,
        "null_cells": int(frame.isna().sum().sum()),
        "infinite_cells": int(np.isinf(frame.to_numpy(dtype=float)).sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "time_min": float(frame["Time"].min()),
        "time_max": float(frame["Time"].max()),
        "amount_min": float(frame["Amount"].min()),
        "amount_max": float(frame["Amount"].max()),
    }
