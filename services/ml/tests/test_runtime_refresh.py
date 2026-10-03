import json

import pytest

from fraud_ml import runtime


def fixture(tmp_path):
    normal, peak = tmp_path / "normal.json", tmp_path / "peak.json"
    normal.write_text("{}")
    peak.write_text("{}")
    record = {
        "run_id": "unchanged-run",
        "environment_sha256": "unchanged-credentials-checksum",
        "bundle_sha256": "unchanged-frozen-package",
        "gate_report_sha256": "unchanged-model-gate",
        "reviewer_identity": "project_owner",
        "backend_image_id": "old-backend",
        "worker_image_id": "worker",
    }
    metadata = tmp_path / "application.json"
    metadata.write_text(json.dumps(record))
    report = {"backend_image_id": "new-backend", "worker_image_id": "worker"}
    return metadata, record, normal, peak, report


def test_refresh_preserves_identity_and_archives_exact_previous_record(tmp_path):
    metadata, record, normal, peak, report = fixture(tmp_path)
    previous = metadata.read_bytes()
    assert runtime.refresh_runtime_evidence(metadata, record, normal, peak, report)
    updated = json.loads(metadata.read_text())
    for key in (
        "run_id",
        "environment_sha256",
        "bundle_sha256",
        "gate_report_sha256",
        "reviewer_identity",
    ):
        assert updated[key] == record[key]
    assert updated["backend_image_id"] == "new-backend"
    assert updated["normal_report_sha256"] == runtime.sha256(normal)
    assert updated["peak_report_sha256"] == runtime.sha256(peak)
    backups = list(tmp_path.glob("application-before-requalification-*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == previous
    assert not runtime.refresh_runtime_evidence(metadata, updated, normal, peak, report)
    assert len(list(tmp_path.glob("application-before-requalification-*.json"))) == 1


def test_failed_atomic_replacement_preserves_original_and_cleans_temporary(
    tmp_path, monkeypatch
):
    metadata, record, normal, peak, report = fixture(tmp_path)
    previous = metadata.read_bytes()

    def fail(*_):
        raise OSError("interrupted replacement")

    monkeypatch.setattr(runtime.os, "replace", fail)
    with pytest.raises(OSError, match="interrupted"):
        runtime.refresh_runtime_evidence(metadata, record, normal, peak, report)
    assert metadata.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))
    assert len(list(tmp_path.glob("application-before-requalification-*.json"))) == 1


def test_refresh_refuses_unexpected_metadata_edits(tmp_path):
    metadata, record, normal, peak, report = fixture(tmp_path)
    metadata.write_text(json.dumps(record | {"run_id": "different-run"}))
    with pytest.raises(ValueError, match="changed"):
        runtime.refresh_runtime_evidence(metadata, record, normal, peak, report)
    assert json.loads(metadata.read_text())["run_id"] == "different-run"
    assert not list(tmp_path.glob("application-before-requalification-*"))
