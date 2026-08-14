import numpy as np

from fraud_ml.task5.calibration import (
    assert_probability_bounds,
    cross_fitted_calibration,
)
from fraud_ml.task5.config import Task5Config


def test_cross_fitted_calibration_is_deterministic_and_bounded():
    raw = np.linspace(-3, 3, 100)
    target = np.array([0] * 90 + [1] * 10)
    config = Task5Config(folds=5)
    first = cross_fitted_calibration(raw, target, "sigmoid", config)
    second = cross_fitted_calibration(raw, target, "sigmoid", config)
    np.testing.assert_allclose(first, second)
    assert_probability_bounds(first, config)


def test_probability_guard_rejects_invalid_values():
    config = Task5Config()
    for values in ([0.1, np.nan], [-0.1, 0.2], [0.2, 1.1]):
        try:
            assert_probability_bounds(values, config)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid probability values were accepted")
