"""Numerical helper settings only; no dataset, split, or operating policy."""

from dataclasses import dataclass

MODEL_ORDER = (
    "logistic_regression",
    "random_forest",
    "linear_svm",
    "knn",
)


@dataclass(frozen=True)
class EnsembleConfig:
    fusion_regularization: float = 0.05
    minimum_fusion_weight: float = 0.01
    probability_tolerance: float = 1e-12
