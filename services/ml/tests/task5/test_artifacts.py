from pathlib import Path

import joblib
import pytest

from fraud_ml.task5.artifacts import trusted_load, verify_checksums, write_checksums


def test_bundle_checksum_verification_and_corruption_rejection(tmp_path: Path):
    joblib.dump({"safe": True}, tmp_path / "component.joblib")
    write_checksums(tmp_path)
    assert verify_checksums(tmp_path)
    assert trusted_load(tmp_path, "component.joblib") == {"safe": True}
    (tmp_path / "component.joblib").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_checksums(tmp_path)


def test_trusted_load_rejects_path_escape(tmp_path: Path):
    joblib.dump({"safe": True}, tmp_path / "component.joblib")
    write_checksums(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        trusted_load(tmp_path, "../outside.joblib")
