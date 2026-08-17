import numpy as np
from types import SimpleNamespace

from fraud_ml.ensemble.config import MODEL_ORDER, EnsembleConfig
from fraud_ml.ensemble.fusion import calibrated_matrix, optimize_weights
from fraud_ml.ensemble.policy import (
    fixed_rate_policy_evidence,
    named_profiles,
    precision_recall_evidence,
    threshold_tradeoffs,
)


def test_weighted_fusion_is_deterministic_nonnegative_and_sums_to_one():
    probabilities = np.array([[0.01, 0.02, 0.03, 0.04], [0.8, 0.7, 0.6, 0.5]] * 50)
    target = np.array([0, 1] * 50)
    config = EnsembleConfig()
    first = optimize_weights(probabilities, target, config)
    second = optimize_weights(probabilities, target, config)
    np.testing.assert_allclose(first, second)
    assert np.all(first >= 0)
    assert np.isclose(first.sum(), 1)


def test_threshold_profiles_are_measured_and_ordered():
    target = np.array([0] * 95 + [1] * 5)
    scores = np.linspace(0, 1, 100)
    amounts = np.ones(100)
    tradeoffs = threshold_tradeoffs(
        target,
        scores,
        amounts,
        (0.05, 0.1, 0.2),
        (0.01, 0.02, 0.04),
        0.1,
    )
    for row in tradeoffs:
        assert 0 <= row["review_threshold"] < row["block_threshold"] <= 1
    profiles = named_profiles(tradeoffs)
    assert set(profiles) == {
        "Conservative Block",
        "Balanced Demo",
        "Recall First",
    }


def test_precision_recall_and_bounded_budget_evidence_is_reported():
    target = np.array([0, 1] * 50)
    scores = np.linspace(0, 1, 100)
    evidence = precision_recall_evidence(
        target,
        scores,
        budgets=(10, 20),
        maximum_curve_points=11,
    )
    assert len(evidence["curve"]) <= 11
    assert set(evidence["bounded_review_budgets"]) == {"10", "20"}
    assert evidence["bounded_review_budgets"]["10"]["reviewed"] == 10
    fixed = fixed_rate_policy_evidence(target, scores, action_rate=0.1)
    assert 0 <= fixed["precision"] <= 1
    assert 0 <= fixed["recall"] <= 1


def test_fusion_uses_calibrated_probabilities_not_raw_svm_margins():
    models = {
        name: SimpleNamespace(
            training_probabilities=np.array([0.1, 0.9]),
            validation_probabilities=np.array([0.2, 0.8]),
            validation_raw_scores=(
                np.array([-50.0, 75.0])
                if name == "linear_svm"
                else np.array([0.2, 0.8])
            ),
        )
        for name in MODEL_ORDER
    }
    matrix = calibrated_matrix(models, "validation")
    assert np.all((matrix >= 0) & (matrix <= 1))
    np.testing.assert_array_equal(
        matrix[:, MODEL_ORDER.index("linear_svm")],
        np.array([0.2, 0.8]),
    )
