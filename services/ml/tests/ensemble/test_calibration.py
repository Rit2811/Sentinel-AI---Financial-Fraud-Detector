import numpy as np

from fraud_ml.ensemble.calibration import (
    assert_probability_bounds,
    chronological_stability_metrics,
    cross_fitted_calibration,
)
from fraud_ml.ensemble.config import EnsembleConfig


def test_cross_fitted_calibration_is_deterministic_and_bounded():
    raw = np.linspace(-3, 3, 100)
    target = np.array([0] * 90 + [1] * 10)
    config = EnsembleConfig(folds=5)
    first = cross_fitted_calibration(raw, target, "sigmoid", config)
    second = cross_fitted_calibration(raw, target, "sigmoid", config)
    np.testing.assert_allclose(first, second)
    assert_probability_bounds(first, config)


def test_probability_guard_rejects_invalid_values():
    config = EnsembleConfig()
    for values in ([0.1, np.nan], [-0.1, 0.2], [0.2, 1.1]):
        try:
            assert_probability_bounds(values, config)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid probability values were accepted")


def test_chronological_stability_reports_each_segment():
    target = np.array([0, 1] * 50)
    probabilities = np.linspace(0.01, 0.99, 100)
    evidence = chronological_stability_metrics(target, probabilities, segments=5)
    assert evidence["measured_segments"] == 5
    assert len(evidence["segments"]) == 5
    assert evidence["minimum_average_precision"] >= 0
