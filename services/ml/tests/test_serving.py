import json

import pytest

from fraud_ml.freeze import require_approval
from fraud_ml.serving import FrozenScorer, sha256, verify_manifest


def test_unapproved_freeze_rejected():
    for policy in (
        {},
        {
            "selected_scorer": "random_forest.sigmoid",
            "review_threshold": 0.1,
            "block_threshold": 0.25,
        },
    ):
        with pytest.raises(ValueError, match="approval"):
            require_approval(policy)


def test_manifest_pin_checked_before_model_loading(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {}}))
    monkeypatch.setattr(
        "fraud_ml.serving.joblib.load",
        lambda *args: pytest.fail("Unverified deserialization"),
    )
    with pytest.raises(ValueError, match="checksum"):
        FrozenScorer(tmp_path, "0" * 64)
    with pytest.raises(ValueError, match="status"):
        verify_manifest(tmp_path, sha256(manifest))


def test_label_and_identity_injection_rejected_before_scoring():
    scorer = object.__new__(FrozenScorer)
    for value in ([{"is_fraud": 0}], [{"cc_num": "forbidden"}], []):
        with pytest.raises(ValueError, match="label-free"):
            scorer.score(value)
