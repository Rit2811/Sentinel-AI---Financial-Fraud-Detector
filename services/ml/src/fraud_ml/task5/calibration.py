from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from fraud_ml.models import build_models, reduce_knn_majority
from fraud_ml.task5.config import MODEL_ORDER, Task5Config


@dataclass
class ScoreCalibrator:
    method: str
    estimator: object

    def predict(self, raw_scores) -> np.ndarray:
        values = np.asarray(raw_scores, dtype=float)
        if self.method == "sigmoid":
            return self.estimator.predict_proba(values.reshape(-1, 1))[:, 1]
        return self.estimator.predict(values)


@dataclass
class CalibratedModel:
    name: str
    base_model: object
    calibrator: ScoreCalibrator
    training_probabilities: np.ndarray
    validation_raw_scores: np.ndarray
    validation_probabilities: np.ndarray
    evidence: dict


def fit_calibrated_models(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    validation_x: pd.DataFrame,
    validation_y: pd.Series,
    config: Task5Config,
) -> dict[str, CalibratedModel]:
    results = {}
    for name in MODEL_ORDER:
        results[name] = _fit_one(
            name, train_x, train_y, validation_x, validation_y, config
        )
    return results


def _fit_one(name, train_x, train_y, validation_x, validation_y, config):
    splitter = StratifiedKFold(
        n_splits=config.folds, shuffle=True, random_state=config.seed
    )
    oof_raw = np.empty(len(train_y), dtype=float)
    fold_evidence = []
    for fold, (fit_indices, score_indices) in enumerate(
        splitter.split(train_x, train_y), start=1
    ):
        fold_x = train_x.iloc[fit_indices]
        fold_y = train_y.iloc[fit_indices]
        if name == "knn":
            fold_x, fold_y = reduce_knn_majority(
                fold_x, fold_y, seed=config.seed + fold
            )
        model = build_models(config.seed)[name]
        model.fit(fold_x, fold_y)
        oof_raw[score_indices] = raw_scores(model, train_x.iloc[score_indices])
        fold_evidence.append(
            {
                "fold": fold,
                "fit_rows": int(len(fit_indices)),
                "score_rows": int(len(score_indices)),
                "fit_fraud": int(fold_y.sum()),
                "score_fraud": int(train_y.iloc[score_indices].sum()),
                "overlap_rows": int(
                    len(set(fit_indices.tolist()) & set(score_indices.tolist()))
                ),
            }
        )

    candidate_methods = ["sigmoid"]
    if min(item["fit_fraud"] for item in fold_evidence) >= (
        config.isotonic_minority_per_fold
    ):
        candidate_methods.append("isotonic")

    candidates = {}
    candidate_probabilities = {}
    for method in candidate_methods:
        probabilities = cross_fitted_calibration(oof_raw, train_y, method, config)
        candidate_probabilities[method] = probabilities
        candidates[method] = probability_metrics(
            train_y, probabilities, config.calibration_bins
        )

    selected_method = min(
        candidate_methods,
        key=lambda method: (
            candidates[method]["log_loss"],
            candidates[method]["brier_score"],
            candidates[method]["expected_calibration_error"],
            method,
        ),
    )
    calibrator = fit_calibrator(oof_raw, train_y, selected_method)

    final_x, final_y = train_x, train_y
    if name == "knn":
        final_x, final_y = reduce_knn_majority(train_x, train_y, seed=config.seed)
    base_model = build_models(config.seed)[name]
    started = time.perf_counter()
    base_model.fit(final_x, final_y)
    fit_seconds = time.perf_counter() - started
    started = time.perf_counter()
    validation_raw = raw_scores(base_model, validation_x)
    validation_probabilities = calibrator.predict(validation_raw)
    score_seconds = time.perf_counter() - started
    assert_probability_bounds(validation_probabilities, config)

    before = ranking_metrics(validation_y, validation_raw)
    after = probability_metrics(
        validation_y, validation_probabilities, config.calibration_bins
    )
    after.update(calibration_line(validation_y, validation_probabilities))
    return CalibratedModel(
        name=name,
        base_model=base_model,
        calibrator=calibrator,
        training_probabilities=candidate_probabilities[selected_method],
        validation_raw_scores=validation_raw,
        validation_probabilities=validation_probabilities,
        evidence={
            "selected_method": selected_method,
            "candidate_training_oof_metrics": candidates,
            "validation_before_calibration": before,
            "validation_after_calibration": after,
            "folds": fold_evidence,
            "oof_rows": int(len(oof_raw)),
            "oof_finite": bool(np.isfinite(oof_raw).all()),
            "fit_seconds": fit_seconds,
            "validation_score_seconds": score_seconds,
            "final_fit_rows": int(len(final_y)),
            "final_fit_fraud": int(final_y.sum()),
        },
    )


def raw_scores(model, features) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(features)[:, 1], dtype=float)
    return np.asarray(model.decision_function(features), dtype=float)


def cross_fitted_calibration(raw, target, method, config) -> np.ndarray:
    raw = np.asarray(raw, dtype=float)
    target = np.asarray(target, dtype=int)
    probabilities = np.empty(len(target), dtype=float)
    splitter = StratifiedKFold(
        n_splits=config.folds,
        shuffle=True,
        random_state=config.seed + 10_000,
    )
    for fit_indices, score_indices in splitter.split(raw.reshape(-1, 1), target):
        calibrator = fit_calibrator(raw[fit_indices], target[fit_indices], method)
        probabilities[score_indices] = calibrator.predict(raw[score_indices])
    assert_probability_bounds(probabilities, config)
    return probabilities


def fit_calibrator(raw, target, method) -> ScoreCalibrator:
    raw = np.asarray(raw, dtype=float)
    target = np.asarray(target, dtype=int)
    if method == "sigmoid":
        estimator = LogisticRegression(C=1_000_000, max_iter=1000, random_state=42)
        estimator.fit(raw.reshape(-1, 1), target)
    elif method == "isotonic":
        estimator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        estimator.fit(raw, target)
    else:
        raise ValueError(f"Unsupported calibration method: {method}")
    return ScoreCalibrator(method=method, estimator=estimator)


def ranking_metrics(target, scores) -> dict:
    return {
        "average_precision": float(average_precision_score(target, scores)),
        "roc_auc": float(roc_auc_score(target, scores)),
    }


def probability_metrics(target, probabilities, bins) -> dict:
    probabilities = np.asarray(probabilities, dtype=float)
    metrics = ranking_metrics(target, probabilities)
    reliability = reliability_table(target, probabilities, bins)
    metrics.update(
        {
            "brier_score": float(brier_score_loss(target, probabilities)),
            "log_loss": float(log_loss(target, probabilities, labels=[0, 1])),
            "expected_calibration_error": float(
                sum(
                    row["fraction"] * abs(row["mean_probability"] - row["fraud_rate"])
                    for row in reliability
                )
            ),
            "reliability_bins": reliability,
            "minimum_probability": float(probabilities.min()),
            "maximum_probability": float(probabilities.max()),
            "probability_stddev": float(probabilities.std()),
        }
    )
    return metrics


def reliability_table(target, probabilities, bins) -> list[dict]:
    target = np.asarray(target, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    indices = np.minimum(np.digitize(probabilities, edges[1:-1]), bins - 1)
    rows = []
    for index in range(bins):
        selected = indices == index
        count = int(selected.sum())
        rows.append(
            {
                "bin": index,
                "lower": float(edges[index]),
                "upper": float(edges[index + 1]),
                "count": count,
                "fraction": float(count / len(target)),
                "mean_probability": (
                    float(probabilities[selected].mean()) if count else 0.0
                ),
                "fraud_rate": float(target[selected].mean()) if count else 0.0,
            }
        )
    return rows


def calibration_line(target, probabilities) -> dict:
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-8, 1 - 1e-8)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    diagnostic = LogisticRegression(C=1_000_000, max_iter=1000, random_state=42)
    diagnostic.fit(logits, target)
    return {
        "calibration_intercept": float(diagnostic.intercept_[0]),
        "calibration_slope": float(diagnostic.coef_[0, 0]),
    }


def assert_probability_bounds(probabilities, config) -> None:
    values = np.asarray(probabilities, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Calibrated probabilities must be finite")
    if values.min() < -config.probability_tolerance:
        raise ValueError("Calibrated probability below zero")
    if values.max() > 1 + config.probability_tolerance:
        raise ValueError("Calibrated probability above one")
