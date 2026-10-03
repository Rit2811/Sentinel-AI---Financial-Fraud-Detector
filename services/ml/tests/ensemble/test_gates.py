import builtins
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from fraud_ml.ensemble import bundle, development


BLOCKED = (
    "Task 5 blocked: Sparkov Task 4 evidence and approved operating constraints "
    "required; no compatible frozen bundle"
)
ML_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("entry", [development.main, bundle.main])
@pytest.mark.parametrize("arguments", [[], ["--help"], ["--approved"], None])
def test_commands_fail_closed_before_io(entry, arguments, monkeypatch, tmp_path):
    legacy = tmp_path / "legacy-bundle"
    legacy.mkdir()
    artifact = legacy / "component.joblib"
    artifact.write_bytes(b"retired artifact must never be opened")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ensemble", "--bundle-dir", str(legacy)])

    def forbidden(*args, **kwargs):
        pytest.fail("Blocked Task 5 command attempted file access")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        for method in ("open", "read_text", "read_bytes", "mkdir"):
            guard.setattr(Path, method, forbidden)
        with pytest.raises(SystemExit) as error:
            entry(arguments)
    assert error.value.code == BLOCKED
    assert artifact.read_bytes() == b"retired artifact must never be opened"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["legacy-bundle"]


@pytest.mark.parametrize("module", ["development", "bundle"])
def test_module_commands_exit_nonzero_without_loading_workflow(module, tmp_path):
    script = """
import builtins
import runpy
import sys

original_import = builtins.__import__
forbidden = (
    'fraud_ml.data', 'fraud_ml.models', 'fraud_ml.split',
    'fraud_ml.ensemble.calibration', 'fraud_ml.ensemble.artifacts',
    'numpy', 'pandas', 'sklearn', 'scipy', 'joblib',
)

def guarded_import(name, *args, **kwargs):
    if any(name == item or name.startswith(item + '.') for item in forbidden):
        raise AssertionError('Blocked command imported ' + name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
runpy.run_module(sys.argv[1], run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, f"fraud_ml.ensemble.{module}"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ML_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == BLOCKED
    assert list(tmp_path.iterdir()) == []


def test_project_commands_keep_task4_and_blocked_task5_entry_points():
    project = tomllib.loads((ML_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"] == {
        "fraud-audit": "fraud_ml.sparkov_audit:main",
        "fraud-baselines": "fraud_ml.cli:baseline_main",
        "fraud-ensemble-develop": "fraud_ml.ensemble.development:main",
        "fraud-ensemble-smoke": "fraud_ml.ensemble.bundle:main",
        "fraud-calibration-develop": "fraud_ml.ensemble.evidence:main",
        "fraud-policy-options": "fraud_ml.ensemble.options:main",
    }
