from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

from fraud_ml.ensemble.config import DATASET_SHA256


def class_counts(target) -> dict[str, int]:
    return {
        str(int(key)): int(value)
        for key, value in pd.Series(target).value_counts().sort_index().items()
    }


def environment_record() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "scipy": scipy.__version__,
    }


def code_record() -> dict:
    ml_root = Path(__file__).resolve().parents[3]
    repo_root = ml_root.parents[1]
    paths = [
        ml_root / "pyproject.toml",
        *sorted((ml_root / "src" / "fraud_ml").rglob("*.py")),
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ml_root).as_posix().encode())
        digest.update(path.read_bytes())
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    return {
        "git_revision": revision,
        "dirty_worktree_fingerprint": digest.hexdigest(),
        "command": "uv run fraud-ensemble-develop --local-csv data/creditcard.csv",
    }


def write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def write_model_card_scaffold(
    path: Path,
    locked_test_rows: int,
    selected_fusion: str,
    recommended_profile: str,
    selected_metrics: dict,
    profiles: dict,
) -> None:
    profile_rows = "\n".join(
        (
            f"- {name}: available={profile['available']}, "
            f"action_rate={profile['measured_policy']['action_rate']:.6f}, "
            f"precision={profile['measured_policy']['precision']:.6f}, "
            f"recall={profile['measured_policy']['recall']:.6f}"
        )
        for name, profile in profiles.items()
        if profile["available"]
    )
    content = f"""# Calibrated ensemble model card

Status: Validation-only development; locked test not opened.

## Purpose

Offline research demonstration of calibrated fraud probabilities and
Allow/Review/Block policy analysis on the historical anonymized ULB benchmark.
It is not approved for live payments, customer decisions or issuer loss claims.

Intended users are the project owner, academic reviewers and developers
reproducing the controlled offline experiment. It must not be used by banks,
analysts or automated payment systems to make real customer decisions.

## Data and leakage controls

- Dataset SHA-256: {DATASET_SHA256}
- Training and validation only were used in this development report.
- The locked test contains {locked_test_rows} rows and remains unopened.
- The outer split is chronological; calibration folds exist only inside training.
- `Class` is never part of an inference feature vector.

## Models and fusion

All four Task 4 models are calibrated from training-only out-of-fold scores.
The validation-selected fusion candidate is {selected_fusion}. SVM margins are
never used directly as probabilities.

Logistic Regression, linear SVM and KNN include robust scaling. Random Forest
uses the ordered numeric feature contract directly. The bundle records the
ordered features and fitted pipeline classes for compatibility checking.

## Validation evidence

- Average precision: {selected_metrics["average_precision"]:.8f}
- ROC AUC: {selected_metrics["roc_auc"]:.8f}
- Brier score: {selected_metrics["brier_score"]:.8f}
- Log loss: {selected_metrics["log_loss"]:.8f}
- Expected calibration error: {selected_metrics["expected_calibration_error"]:.8f}

## Decision policy

Three measured profiles are available. The current recommendation is
{recommended_profile}, but no policy is frozen until owner approval M4.

{profile_rows}

Approval record: M4 pending. No Review or Block thresholds are frozen.

## Security and integrity

Binary models remain local and ignored by Git. Every bundle file is covered by
`checksums.sha256`; loading rejects missing, additional or corrupted files and
checks the feature, model-order and weight contracts. Only this locally produced
trusted joblib bundle may be deserialized.

## Reproduction

```text
uv run fraud-ensemble-develop --local-csv data/creditcard.csv
uv run fraud-ensemble-smoke --bundle-dir artifacts/model-bundles/ensemble-development-v1
```

## Limitations

The ULB dataset is historical, anonymized and highly imbalanced. It does not
represent current issuer populations, card-present/card-not-present behavior,
review capacity, customer friction, confirmed loss, fairness groups or live
latency. Amount evidence is a benchmark scenario only.

## Final test

Not run. This section must only be completed after freeze approval M5 and
separate one-time test authorization M6. No post-test tuning is permitted.
"""
    path.write_text(content, encoding="utf-8")
