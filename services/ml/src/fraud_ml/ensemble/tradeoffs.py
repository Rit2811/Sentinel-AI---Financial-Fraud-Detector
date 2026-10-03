"""Measured policy options, not approved operating constraints."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from .probability import checked_probability


def wilson_interval(successes, total):
    if not total:
        return None
    z = norm.ppf(0.975)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return [max(0.0, float(center - half)), min(1.0, float(center + half))]


def policy_table(target, probabilities, times, extra_thresholds=()):
    values = checked_probability(probabilities)
    labels = np.asarray(target)
    if labels.shape != values.shape or not np.isin(labels, [0, 1]).all():
        raise ValueError("Policy evidence requires aligned binary evaluation labels")
    if len(times) != len(values):
        raise ValueError("Policy evidence timestamps must align")
    order = np.argsort(values, kind="stable")
    sorted_scores, sorted_labels = values[order], labels[order]
    fraud_prefix = np.r_[0, np.cumsum(sorted_labels)]
    fraud_total, legitimate_total = int(labels.sum()), int((labels == 0).sum())
    thresholds = np.unique(
        np.r_[
            [0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1],
            np.quantile(values, [0, 0.5, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999, 1]),
            values[labels == 0].max(),
            np.nextafter(values[labels == 0].max(), 1),
            extra_thresholds,
        ]
    )
    # Cache above-threshold counts per hour/day; subtraction respects score ties.
    buckets = (
        times.dt.floor("h").astype("int64").to_numpy(),
        times.dt.floor("D").astype("int64").to_numpy(),
    )
    histograms = []
    for bucket in buckets:
        _, indices = np.unique(bucket, return_inverse=True)
        histograms.append(
            np.array(
                [
                    np.bincount(indices, weights=values >= threshold)
                    for threshold in thresholds
                ]
            )
        )
    positions = np.searchsorted(sorted_scores, thresholds, side="left")
    rows = []
    for i, r in enumerate(thresholds):
        for j in range(i + 1, len(thresholds)):
            b = thresholds[j]
            pass_total, below_block = int(positions[i]), int(positions[j])
            pass_fraud = int(fraud_prefix[pass_total])
            below_block_fraud = int(fraud_prefix[below_block])
            review_fraud = below_block_fraud - pass_fraud
            block_fraud = fraud_total - below_block_fraud
            review_total = below_block - pass_total
            block_total = len(labels) - below_block
            false_blocks = block_total - block_fraud
            rows.append(
                {
                    "r": float(r),
                    "b": float(b),
                    "pass_fraud": pass_fraud,
                    "pass_legitimate": pass_total - pass_fraud,
                    "review_fraud": review_fraud,
                    "review_legitimate": review_total - review_fraud,
                    "block_fraud": block_fraud,
                    "block_legitimate": false_blocks,
                    "fraud_pass_rate": pass_fraud / fraud_total,
                    "fraud_review_rate": review_fraud / fraud_total,
                    "fraud_block_rate": block_fraud / fraud_total,
                    "fraud_routed_rate": (review_fraud + block_fraud) / fraud_total,
                    "review_rate": review_total / len(labels),
                    "review_yield": review_fraud / review_total
                    if review_total
                    else None,
                    "block_precision": block_fraud / block_total
                    if block_total
                    else None,
                    "false_block_rate": false_blocks / legitimate_total,
                    "false_blocks_per_10000_legitimate": false_blocks
                    / legitimate_total
                    * 10000,
                    "false_block_rate_wilson95": wilson_interval(
                        false_blocks, legitimate_total
                    ),
                    "fraud_routed_rate_wilson95": wilson_interval(
                        review_fraud + block_fraud, fraud_total
                    ),
                    "replay_peak_reviews_per_hour": int(
                        (histograms[0][i] - histograms[0][j]).max()
                    ),
                    "replay_peak_reviews_per_day": int(
                        (histograms[1][i] - histograms[1][j]).max()
                    ),
                    "reviews_per_10000_attempts": review_total / len(labels) * 10000,
                    "owner_workload_estimate": None,
                    "feasibility": "NOT_ASSESSED_OWNER_LIMITS_MISSING",
                }
            )
    return rows
