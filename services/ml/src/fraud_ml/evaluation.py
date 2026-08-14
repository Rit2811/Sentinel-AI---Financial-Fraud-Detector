from __future__ import annotations

import time

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_model(model, train_x, train_y, validation_x, validation_y) -> dict:
    started = time.perf_counter()
    model.fit(train_x, train_y)
    fit_seconds = time.perf_counter() - started
    started = time.perf_counter()
    scores = (
        model.predict_proba(validation_x)[:, 1]
        if hasattr(model, "predict_proba")
        else model.decision_function(validation_x)
    )
    score_seconds = time.perf_counter() - started
    threshold = 0.5 if hasattr(model, "predict_proba") else 0
    predicted = np.asarray(scores) >= threshold
    tn, fp, fn, tp = confusion_matrix(validation_y, predicted).ravel()
    return {
        "average_precision": average_precision_score(validation_y, scores),
        "roc_auc": roc_auc_score(validation_y, scores),
        "precision": precision_score(validation_y, predicted, zero_division=0),
        "recall": recall_score(validation_y, predicted, zero_division=0),
        "f1": f1_score(validation_y, predicted, zero_division=0),
        "f2": fbeta_score(validation_y, predicted, beta=2, zero_division=0),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "fit_seconds": fit_seconds,
        "score_seconds": score_seconds,
        "review_budgets": review_budget_metrics(validation_y, scores),
    }


def review_budget_metrics(target, scores, budgets=(100, 500, 1000)) -> dict:
    order = np.argsort(-np.asarray(scores))
    target_array = np.asarray(target)
    return {
        str(budget): {
            "fraud_found": int(target_array[order[:budget]].sum()),
            "precision": float(target_array[order[:budget]].mean()),
        }
        for budget in budgets
        if budget <= len(target_array)
    }
