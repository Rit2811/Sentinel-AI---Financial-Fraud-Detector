from __future__ import annotations

import time

import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import log_loss

from fraud_ml.ensemble.calibration import (
    chronological_stability_metrics,
    probability_metrics,
)
from fraud_ml.ensemble.config import EnsembleConfig, FEATURE_ORDER, MODEL_ORDER
from fraud_ml.ensemble.policy import fixed_rate_policy_evidence


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


def eligibility_report(models, validation_x, validation_y, config) -> dict:
    prevalence = float(np.mean(validation_y))
    baseline_log_loss = float(
        log_loss(
            validation_y,
            np.full(len(validation_y), prevalence),
            labels=[0, 1],
        )
    )
    report = {}
    for name in MODEL_ORDER:
        probabilities = models[name].validation_probabilities
        metrics = probability_metrics(
            validation_y, probabilities, config.calibration_bins
        )
        checks = {
            "finite_and_bounded": bool(
                np.isfinite(probabilities).all()
                and probabilities.min() >= 0
                and probabilities.max() <= 1
            ),
            "ranking_above_no_skill": metrics["average_precision"] > prevalence,
            "non_degenerate": metrics["probability_stddev"] > 1e-8,
            "calibration_better_than_constant": (
                metrics["log_loss"] < baseline_log_loss
            ),
            "feature_contract_compatible": (
                list(validation_x.columns) == list(FEATURE_ORDER)
                and list(getattr(models[name].base_model, "feature_names_in_", ()))
                == list(FEATURE_ORDER)
            ),
            "row_contract_compatible": len(probabilities) == len(validation_y),
            "runtime_recorded": (
                models[name].evidence["validation_score_seconds"] >= 0
            ),
        }
        report[name] = {
            "eligible": all(checks.values()),
            "checks": checks,
            "validation_average_precision": metrics["average_precision"],
            "no_skill_average_precision": prevalence,
            "validation_log_loss": metrics["log_loss"],
            "constant_probability_log_loss": baseline_log_loss,
            "diagnostics": {
                "ranking_regression": float(
                    models[name].evidence["validation_before_calibration"][
                        "average_precision"
                    ]
                    - metrics["average_precision"]
                ),
                "ranking_regression_within_advisory_tolerance": (
                    metrics["average_precision"]
                    >= models[name].evidence["validation_before_calibration"][
                        "average_precision"
                    ]
                    - config.ranking_regression_tolerance
                ),
            },
            "observed_feature_order": list(
                getattr(models[name].base_model, "feature_names_in_", ())
            ),
        }
    return report


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


def fusion_analysis(
    models,
    training_y,
    validation_x,
    validation_y,
    config: EnsembleConfig,
) -> dict:
    eligibility = eligibility_report(models, validation_x, validation_y, config)
    ineligible = [name for name, item in eligibility.items() if not item["eligible"]]
    if ineligible:
        raise ValueError(f"Ineligible fusion members: {', '.join(ineligible)}")

    training = calibrated_matrix(models, "training")
    validation = calibrated_matrix(models, "validation")
    equal_weights = np.full(len(MODEL_ORDER), 1 / len(MODEL_ORDER))
    weighted_weights = optimize_weights(training, training_y, config)
    started = time.perf_counter()
    equal_scores = validation @ equal_weights
    equal_score_seconds = time.perf_counter() - started
    started = time.perf_counter()
    weighted_scores = validation @ weighted_weights
    weighted_score_seconds = time.perf_counter() - started
    equal_metrics = probability_metrics(
        validation_y, equal_scores, config.calibration_bins
    )
    weighted_metrics = probability_metrics(
        validation_y, weighted_scores, config.calibration_bins
    )
    equal_selection_evidence = fusion_selection_evidence(
        validation_y,
        equal_scores,
        equal_metrics,
        equal_weights,
        equal_score_seconds,
    )
    weighted_selection_evidence = fusion_selection_evidence(
        validation_y,
        weighted_scores,
        weighted_metrics,
        weighted_weights,
        weighted_score_seconds,
    )
    selected_name = select_fusion(
        equal_selection_evidence,
        weighted_selection_evidence,
        config,
    )
    selected_scores = (
        weighted_scores if selected_name == "weighted_soft_vote" else equal_scores
    )
    selected_weights = (
        weighted_weights if selected_name == "weighted_soft_vote" else equal_weights
    )

    base_metrics = {
        name: probability_metrics(
            validation_y,
            models[name].validation_probabilities,
            config.calibration_bins,
        )
        for name in MODEL_ORDER
    }
    leave_one_out = {}
    for excluded_index, excluded_name in enumerate(MODEL_ORDER):
        retained = [
            index for index in range(len(MODEL_ORDER)) if index != excluded_index
        ]
        weights = selected_weights[retained]
        weights = weights / weights.sum()
        scores = validation[:, retained] @ weights
        leave_one_out[excluded_name] = probability_metrics(
            validation_y, scores, config.calibration_bins
        )

    strongest_single = max(
        MODEL_ORDER,
        key=lambda name: (
            base_metrics[name]["average_precision"],
            -base_metrics[name]["log_loss"],
        ),
    )
    correlations = np.corrcoef(validation, rowvar=False)
    pairwise = {}
    disagreement = {}
    for left_index, left_name in enumerate(MODEL_ORDER):
        for right_index in range(left_index + 1, len(MODEL_ORDER)):
            right_name = MODEL_ORDER[right_index]
            key = f"{left_name}__{right_name}"
            pairwise[key] = float(correlations[left_index, right_index])
            disagreement[key] = {
                "mean_absolute_probability_difference": float(
                    np.mean(
                        np.abs(validation[:, left_index] - validation[:, right_index])
                    )
                ),
                "maximum_absolute_probability_difference": float(
                    np.max(
                        np.abs(validation[:, left_index] - validation[:, right_index])
                    )
                ),
            }

    return {
        "eligibility": eligibility,
        "equal_weight": {
            "weights": dict(zip(MODEL_ORDER, equal_weights.tolist(), strict=True)),
            "metrics": equal_metrics,
            "selection_evidence": equal_selection_evidence,
        },
        "weighted_soft_vote": {
            "weights": dict(zip(MODEL_ORDER, weighted_weights.tolist(), strict=True)),
            "metrics": weighted_metrics,
            "regularization": config.fusion_regularization,
            "minimum_weight": config.minimum_fusion_weight,
            "selection_evidence": weighted_selection_evidence,
        },
        "selected_fusion": selected_name,
        "selected_weights": dict(
            zip(MODEL_ORDER, selected_weights.tolist(), strict=True)
        ),
        "base_model_metrics": base_metrics,
        "strongest_single_model": strongest_single,
        "leave_one_model_out": leave_one_out,
        "pairwise_score_correlation": pairwise,
        "pairwise_disagreement": disagreement,
        "selected_scores": selected_scores,
        "base_validation_matrix": validation,
    }


def fusion_selection_evidence(
    validation_y,
    scores,
    metrics,
    weights,
    score_seconds,
) -> dict:
    return {
        "ranking": {
            "average_precision": metrics["average_precision"],
            "roc_auc": metrics["roc_auc"],
        },
        "calibration": {
            "log_loss": metrics["log_loss"],
            "brier_score": metrics["brier_score"],
            "expected_calibration_error": metrics["expected_calibration_error"],
        },
        "policy_yield_at_one_percent": fixed_rate_policy_evidence(
            validation_y,
            scores,
            action_rate=0.01,
        ),
        "chronological_stability": chronological_stability_metrics(
            validation_y,
            scores,
        ),
        "runtime": {
            "batch_score_seconds": float(score_seconds),
            "estimated_seconds_per_row": float(score_seconds / len(scores)),
            "finite": bool(np.isfinite(score_seconds) and score_seconds >= 0),
        },
        "weight_stability": {
            "maximum_weight": float(np.max(weights)),
            "minimum_weight": float(np.min(weights)),
            "distance_from_equal": float(
                np.linalg.norm(weights - np.full(len(weights), 1 / len(weights)))
            ),
        },
    }


def select_fusion(equal, weighted, config: EnsembleConfig) -> str:
    equal_metrics = equal["ranking"] | equal["calibration"]
    weighted_metrics = weighted["ranking"] | weighted["calibration"]
    weighted_compatible = (
        weighted_metrics["average_precision"]
        >= equal_metrics["average_precision"]
        - config.fusion_average_precision_tolerance
        and weighted_metrics["log_loss"]
        <= equal_metrics["log_loss"] * (1 + config.fusion_log_loss_tolerance)
        and weighted["policy_yield_at_one_percent"]["recall"]
        >= equal["policy_yield_at_one_percent"]["recall"]
        - config.fusion_policy_recall_tolerance
        and weighted["chronological_stability"]["minimum_average_precision"]
        >= equal["chronological_stability"]["minimum_average_precision"]
        - config.fusion_stability_tolerance
        and weighted["runtime"]["finite"]
    )
    weighted_improves = (
        weighted_metrics["average_precision"] > equal_metrics["average_precision"]
        or weighted_metrics["log_loss"] < equal_metrics["log_loss"]
        or weighted["policy_yield_at_one_percent"]["recall"]
        > equal["policy_yield_at_one_percent"]["recall"]
    )
    return (
        "weighted_soft_vote"
        if weighted_compatible and weighted_improves
        else "equal_weight"
    )
