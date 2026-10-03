"""Run-local source evidence for Task 4; this is not a frozen serving bundle."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .data import CACHE_DIR
from .sparkov_audit import file_hash


def record_run_provenance(report_dir: Path, *, phase="before_fit") -> None:
    destination = report_dir / "provenance.json"
    if destination.exists():
        raise ValueError("Run provenance is immutable; use a new run directory")
    manifest = json.loads(
        (CACHE_DIR / "feature-cache.json").read_text(encoding="utf-8")
    )
    if file_hash(CACHE_DIR / "development-features.npz") != manifest["cache_sha256"]:
        raise ValueError("Feature cache checksum does not match its provenance")
    source_files = sorted(Path("src/fraud_ml").rglob("*.py"))
    source_files.extend([Path("pyproject.toml"), Path("uv.lock")])
    payload = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "capture_phase": phase,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_file_sha256": {str(path): file_hash(path) for path in source_files},
        "feature_cache": manifest,
        "source_audit": json.loads(
            (CACHE_DIR / "source-audit.json").read_text(encoding="utf-8")
        ),
        "artifact_status": "TASK4_BASELINES_NOT_CALIBRATED_NOT_FROZEN",
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)


def record_artifact_inventory(artifact_dir: Path, report_dir: Path) -> None:
    payload = {
        "status": "TASK4_BASELINES_NOT_CALIBRATED_NOT_FROZEN",
        "sha256": {
            path.name: file_hash(path)
            for path in sorted(artifact_dir.iterdir())
            if path.is_file()
        },
    }
    with (report_dir / "artifact-inventory.json").open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
