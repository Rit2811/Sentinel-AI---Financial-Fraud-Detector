"""Dataset-independent probability diagnostics; calibration fitting is retired."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


def score_distribution(values) -> dict:
    values = np.asarray(values, dtype=float)
    quantiles = np.quantile(values, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {
        "count": int(len(values)),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "mean": float(values.mean()),
        "stddev": float(values.std()),
        "quantiles": {
            key: float(value)
            for key, value in zip(
                ("p01", "p05", "p25", "p50", "p75", "p95", "p99"),
                quantiles,
                strict=True,
            )
        },
    }


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


def chronological_stability_metrics(target, probabilities, segments=5) -> dict:
    target = np.asarray(target, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    rows = []
    for index, selected in enumerate(np.array_split(np.arange(len(target)), segments)):
        segment_target = target[selected]
        segment_probabilities = probabilities[selected]
        if len(np.unique(segment_target)) < 2:
            rows.append(
                {
                    "segment": index + 1,
                    "rows": int(len(selected)),
                    "fraud": int(segment_target.sum()),
                    "average_precision": None,
                    "log_loss": None,
                }
            )
            continue
        rows.append(
            {
                "segment": index + 1,
                "rows": int(len(selected)),
                "fraud": int(segment_target.sum()),
                "average_precision": float(
                    average_precision_score(segment_target, segment_probabilities)
                ),
                "log_loss": float(
                    log_loss(
                        segment_target,
                        segment_probabilities,
                        labels=[0, 1],
                    )
                ),
            }
        )
    measured = [row for row in rows if row["average_precision"] is not None]
    return {
        "segments": rows,
        "measured_segments": int(len(measured)),
        "minimum_average_precision": float(
            min(row["average_precision"] for row in measured)
        ),
        "average_precision_stddev": float(
            np.std([row["average_precision"] for row in measured])
        ),
        "maximum_log_loss": float(max(row["log_loss"] for row in measured)),
    }


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
