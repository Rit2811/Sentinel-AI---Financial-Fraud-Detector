import json

import pytest

from fraud_ml import provenance
from fraud_ml.sparkov_audit import file_hash


def test_run_snapshot_survives_replaced_cache_and_cannot_be_overwritten(
    tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    cache.mkdir()
    feature_file = cache / "development-features.npz"
    feature_file.write_bytes(b"synthetic-feature-cache")
    manifest = {
        "cache_sha256": file_hash(feature_file),
        "fingerprint": {"feature_version": "test-v1"},
    }
    (cache / "feature-cache.json").write_text(json.dumps(manifest))
    (cache / "source-audit.json").write_text(json.dumps({"status": "PASS"}))
    monkeypatch.setattr(provenance, "CACHE_DIR", cache)
    destination = tmp_path / "run"
    provenance.record_run_provenance(destination)
    original = (destination / "provenance.json").read_bytes()
    feature_file.write_bytes(b"replacement-cache")
    with pytest.raises(ValueError, match="immutable"):
        provenance.record_run_provenance(destination)
    assert (destination / "provenance.json").read_bytes() == original
    assert json.loads(original)["feature_cache"] == manifest
    with pytest.raises(ValueError, match="checksum"):
        provenance.record_run_provenance(tmp_path / "second-run")
