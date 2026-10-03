import numpy as np

from fraud_ml.ensemble.calibration import (
    assert_probability_bounds,
    chronological_stability_metrics,
    probability_metrics,
)
from fraud_ml.ensemble.config import EnsembleConfig


def test_probability_metrics_report_calibration_without_fitting():
    evidence = probability_metrics([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8], bins=5)
    assert np.isclose(evidence["brier_score"], 0.025)
    assert np.isclose(evidence["expected_calibration_error"], 0.15)
    assert evidence["average_precision"] == 1.0
    assert sum(row["count"] for row in evidence["reliability_bins"]) == 4


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
