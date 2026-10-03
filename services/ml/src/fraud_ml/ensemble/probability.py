"""Probability mappings over verified, already-fitted Task 4 model scores."""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator


class ScoreClassifier(ClassifierMixin, BaseEstimator):
    """Expose stored scores to sklearn without fitting a second base classifier."""

    classes_ = np.array([0, 1])

    def __sklearn_is_fitted__(self):
        return True

    def fit(self, X, y):
        raise RuntimeError("The score adapter must never be refitted")

    def predict(self, X):
        return (self.decision_function(X) >= 0).astype(int)

    def decision_function(self, X):
        values = np.asarray(X, dtype=float)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError("Expected one raw score per row")
        if not np.isfinite(values).all():
            raise ValueError("Raw scores must be finite")
        return values[:, 0]


def fit_mapping(scores, target, method):
    if method not in ("sigmoid", "isotonic"):
        raise ValueError("Unsupported calibration method")
    values = np.asarray(scores, dtype=float)
    labels = np.asarray(target)
    if (
        values.ndim != 1
        or values.shape != labels.shape
        or not np.isfinite(values).all()
        or set(np.unique(labels)) != {0, 1}
    ):
        raise ValueError("Calibration requires aligned finite scores and both classes")
    mapper = CalibratedClassifierCV(
        FrozenEstimator(ScoreClassifier()),
        method=method,
        ensemble=False,
        cv=[(np.arange(len(values)), np.arange(len(values)))],
    )
    mapper.fit(values.reshape(-1, 1), labels)
    return mapper


def mapped_probability(mapper, scores):
    values = mapper.predict_proba(np.asarray(scores).reshape(-1, 1))[:, 1]
    return checked_probability(values)


def checked_probability(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Probability output must be a nonempty finite vector")
    if np.any((values < 0) | (values > 1)):
        raise ValueError("Probability output outside [0, 1]")
    return values


def policy_actions(probabilities, review_threshold, block_threshold):
    values = checked_probability(probabilities)
    if not 0 <= review_threshold < block_threshold <= 1:
        raise ValueError("Policy requires 0 <= r < b <= 1")
    return np.where(
        values >= block_threshold,
        "Block",
        np.where(values >= review_threshold, "Review", "Pass"),
    )
