import numpy as np

from fraud_ml.task5.config import Task5Config
from fraud_ml.task5.fusion import optimize_weights
from fraud_ml.task5.policy import named_profiles, threshold_tradeoffs


def test_weighted_fusion_is_deterministic_nonnegative_and_sums_to_one():
    probabilities = np.array([[0.01, 0.02, 0.03, 0.04], [0.8, 0.7, 0.6, 0.5]] * 50)
    target = np.array([0, 1] * 50)
    config = Task5Config()
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
