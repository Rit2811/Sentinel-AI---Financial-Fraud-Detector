"""Numerical fusion helpers, without a dataset development workflow."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from fraud_ml.ensemble.config import EnsembleConfig, MODEL_ORDER


def calibrated_matrix(models, partition: str) -> np.ndarray:
    attribute = (
        "training_probabilities"
        if partition == "training"
        else "validation_probabilities"
    )
    matrix = np.column_stack([getattr(models[name], attribute) for name in MODEL_ORDER])
    if matrix.shape[1] != len(MODEL_ORDER):
        raise ValueError("Fusion input order is incomplete")
    return matrix


def optimize_weights(
    training_probabilities: np.ndarray,
    training_y,
    config: EnsembleConfig,
) -> np.ndarray:
    model_count = training_probabilities.shape[1]
    equal = np.full(model_count, 1 / model_count)

    def objective(weights):
        fused = np.clip(training_probabilities @ weights, 1e-12, 1 - 1e-12)
        target = np.asarray(training_y, dtype=float)
        loss = -np.mean(target * np.log(fused) + (1 - target) * np.log(1 - fused))
        penalty = config.fusion_regularization * np.sum((weights - equal) ** 2)
        return loss + penalty

    result = minimize(
        objective,
        equal,
        method="SLSQP",
        bounds=[(config.minimum_fusion_weight, 1.0) for _ in range(model_count)],
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1},
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not result.success:
        raise RuntimeError(f"Fusion optimization failed: {result.message}")
    weights = np.asarray(result.x, dtype=float)
    if np.any(weights < 0) or not np.isclose(weights.sum(), 1, atol=1e-10):
        raise ValueError("Fusion weights violate constraints")
    return weights
