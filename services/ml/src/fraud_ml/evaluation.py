from __future__ import annotations

import time
import warnings
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    precision_recall_curve,
    recall_score,
    roc_auc_score,
)

from .models import validate_features


def score_model(model, features) -> np.ndarray:
    validate_features(features)
    scores = (
        model.predict_proba(features)[:, 1]
        if hasattr(model, "predict_proba")
        else model.decision_function(features)
    )
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(features),) or not np.isfinite(scores).all():
        raise ValueError("Model returned invalid scores")
    return scores


def score_metrics(target, scores, threshold: float = 0.5) -> dict:
    labels, scores = np.asarray(target), np.asarray(scores, dtype=float)
    if (
        labels.ndim != 1
        or not len(labels)
        or scores.shape != labels.shape
        or not np.isin(labels, [0, 1]).all()
        or not np.isfinite(scores).all()
    ):
        raise ValueError("Metrics require aligned, finite scores and binary labels")
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    has_fraud = bool(np.any(labels == 1))
    ap = float(average_precision_score(labels, scores)) if has_fraud else None
    pr_auc = None
    if has_fraud:
        precision, recall, _ = precision_recall_curve(labels, scores)
        pr_auc = float(auc(recall, precision))
    return {
        "threshold": threshold,
        "average_precision": ap,
        "pr_auc": ap,
        "pr_auc_definition": "average precision (non-interpolated)",
        "pr_auc_trapezoidal": pr_auc,
        "roc_auc": float(roc_auc_score(labels, scores))
        if len(np.unique(labels)) == 2
        else None,
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1": float(f1_score(labels, predicted, zero_division=0)),
        "f2": float(fbeta_score(labels, predicted, beta=2, zero_division=0)),
        "false_positives": int(fp),
        "false_positive_rate": float(fp / (tn + fp)) if tn + fp else None,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "review_budgets": review_budget_metrics(labels, scores),
    }


def all_legitimate_metrics(target) -> dict:
    return score_metrics(target, np.zeros(len(target)))


def evaluate_model(
    model,
    train_x,
    train_y,
    validation_x,
    validation_y,
    *,
    validation_scores_path: Path | None = None,
) -> dict:
    validate_features(train_x)
    validate_features(validation_x)
    for features, labels in ((train_x, train_y), (validation_x, validation_y)):
        if features.empty:
            raise ValueError("Training and validation partitions must be nonempty")
        if len(features) != len(labels) or not features.index.equals(labels.index):
            raise ValueError("Features and labels must be aligned")
        if not labels.isin([0, 1]).all():
            raise ValueError("Labels must be binary")
    if set(train_y.unique()) != {0, 1}:
        raise ValueError("Training requires both classes")
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(train_x, train_y)
    evidence = {
        "fit_seconds": time.perf_counter() - started,
        "fit_warnings": [
            {"category": warning.category.__name__, "message": str(warning.message)}
            for warning in caught
        ],
    }
    classifier = model.named_steps.get("classifier")
    if hasattr(classifier, "n_iter_"):
        evidence["iterations"] = np.asarray(classifier.n_iter_).tolist()
    if any(issubclass(warning.category, ConvergenceWarning) for warning in caught):
        return {**evidence, "status": "failed_convergence"}

    started = time.perf_counter()
    scores = score_model(model, validation_x)
    score_seconds = time.perf_counter() - started
    sample = np.linspace(
        0, len(validation_x) - 1, min(30, len(validation_x)), dtype=int
    )
    single_seconds = []
    for position in sample:
        request = validation_x.iloc[[position]]
        started = time.perf_counter()
        score_model(model, request)
        single_seconds.append(time.perf_counter() - started)
    threshold = 0.5 if hasattr(model, "predict_proba") else 0.0
    metrics = score_metrics(validation_y, scores, threshold)
    if validation_scores_path is not None:
        validation_scores_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(validation_scores_path, scores, allow_pickle=False)
    return {
        **metrics,
        **evidence,
        "status": "completed_with_warnings" if caught else "completed",
        "score_kind": "uncalibrated_probability" if threshold == 0.5 else "margin",
        "score_seconds": score_seconds,
        "latency": {
            "bulk_rows": len(validation_x),
            "bulk_seconds": score_seconds,
            "bulk_seconds_per_row": score_seconds / len(validation_x),
            "single_request_rows": len(sample),
            "single_request_p50_ms": float(np.percentile(single_seconds, 50) * 1000),
            "single_request_p95_ms": float(np.percentile(single_seconds, 95) * 1000),
            "single_request_sampling": "evenly spaced validation rows, after bulk scoring",
            "scope": "in-process feature validation, preprocessing and model scoring",
        },
    }


def review_budget_metrics(target, scores, budgets=(100, 500, 1000)) -> dict:
    order = np.argsort(-np.asarray(scores), kind="stable")
    target_array = np.asarray(target)
    return {
        str(budget): {
            "fraud_found": int(target_array[order[:budget]].sum()),
            "precision": float(target_array[order[:budget]].mean()),
        }
        for budget in budgets
        if 0 < budget <= len(target_array)
    }
