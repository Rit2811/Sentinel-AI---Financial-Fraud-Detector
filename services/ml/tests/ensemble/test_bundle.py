import json
from types import SimpleNamespace

import numpy as np
import pytest

from fraud_ml.ensemble.artifacts import write_checksums
from fraud_ml.ensemble.bundle import (
    package_development_bundle,
    smoke_score,
    verify_bundle,
)
from fraud_ml.ensemble.config import FEATURE_ORDER, MODEL_ORDER, EnsembleConfig


class DummyModel:
    feature_names_in_ = np.asarray(FEATURE_ORDER)
    n_features_in_ = len(FEATURE_ORDER)

    def predict_proba(self, features):
        probability = np.full(len(features), 0.2)
        return np.column_stack([1 - probability, probability])


class DummyCalibrator:
    def predict(self, scores):
        return np.asarray(scores, dtype=float)


def development_models():
    return {
        name: SimpleNamespace(
            base_model=DummyModel(),
            calibrator=DummyCalibrator(),
            evidence={"selected_method": "sigmoid"},
        )
        for name in MODEL_ORDER
    }


def development_fusion():
    probabilities = np.full((4, len(MODEL_ORDER)), 0.2)
    weights = {name: 1 / len(MODEL_ORDER) for name in MODEL_ORDER}
    return {
        "selected_fusion": "equal_weight",
        "selected_weights": weights,
        "selected_scores": probabilities.mean(axis=1),
        "base_validation_matrix": probabilities,
    }


def create_bundle(root):
    profiles = {
        "Balanced Demo": {
            "available": True,
            "constraints": {"maximum_action_rate": 0.01},
            "measured_policy": {"review_threshold": 0.1, "block_threshold": 0.2},
        }
    }
    package_development_bundle(
        root,
        development_models(),
        development_fusion(),
        profiles,
        "Balanced Demo",
        np.array([0, 0, 1, 0], dtype=int),
        EnsembleConfig(),
        {"locked_test": {"state": "LOCKED"}},
        {"python": "test"},
        {"git_revision": "test"},
    )


def test_structured_bundle_verifies_and_scores_without_target(tmp_path):
    create_bundle(tmp_path)
    assert verify_bundle(tmp_path)
    evidence = smoke_score(tmp_path)
    assert evidence["status"] == "PASS"
    assert evidence["contains_target"] is False
    assert 0 <= evidence["fused_probability"] <= 1


def test_bundle_rejects_semantically_incompatible_feature_contract(tmp_path):
    create_bundle(tmp_path)
    contract_path = tmp_path / "feature_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["feature_order"] = list(reversed(contract["feature_order"]))
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    write_checksums(tmp_path)
    with pytest.raises(ValueError, match="Feature contract order"):
        verify_bundle(tmp_path)
