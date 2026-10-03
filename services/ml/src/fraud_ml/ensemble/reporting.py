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
