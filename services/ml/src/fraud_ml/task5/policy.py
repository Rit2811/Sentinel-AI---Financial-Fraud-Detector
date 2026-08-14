from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)


def threshold_tradeoffs(
    target,
    scores,
    amounts,
    action_rate_grid,
    block_rate_grid,
    decision_latency_ms,
) -> list[dict]:
    scores = np.asarray(scores, dtype=float)
    target = np.asarray(target, dtype=int)
    amounts = np.asarray(amounts, dtype=float)
    rows = []
    for action_rate in action_rate_grid:
        review_threshold = threshold_for_rate(scores, action_rate)
        for block_rate in block_rate_grid:
            if block_rate >= action_rate:
                continue
            block_threshold = threshold_for_rate(scores, block_rate)
            if review_threshold >= block_threshold:
                continue
            rows.append(
                decision_metrics(
                    target,
                    scores,
                    amounts,
                    review_threshold,
                    block_threshold,
                    decision_latency_ms,
                )
            )
    return rows


def threshold_for_rate(scores, rate) -> float:
    count = max(1, int(np.ceil(len(scores) * rate)))
    return float(np.sort(np.asarray(scores, dtype=float))[-count])


def decision_metrics(
    target,
    scores,
    amounts,
    review_threshold,
    block_threshold,
    decision_latency_ms,
) -> dict:
    block = scores >= block_threshold
    review = (scores >= review_threshold) & ~block
    action = block | review
    tn, fp, fn, tp = confusion_matrix(target, action, labels=[0, 1]).ravel()
    review_count = int(review.sum())
    block_count = int(block.sum())
    action_count = int(action.sum())
    fraud_total = int(target.sum())
    return {
        "review_threshold": float(review_threshold),
        "block_threshold": float(block_threshold),
        "rows": int(len(target)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "precision": float(precision_score(target, action, zero_division=0)),
        "recall": float(recall_score(target, action, zero_division=0)),
        "f1": float(f1_score(target, action, zero_division=0)),
        "f2": float(fbeta_score(target, action, beta=2, zero_division=0)),
        "review_count": review_count,
        "review_rate": float(review_count / len(target)),
        "review_yield": (float(target[review].mean()) if review_count else 0.0),
        "block_count": block_count,
        "block_rate": float(block_count / len(target)),
        "block_precision": (float(target[block].mean()) if block_count else 0.0),
        "block_fraud_recall": (
            float(target[block].sum() / fraud_total) if fraud_total else 0.0
        ),
        "action_count": action_count,
        "action_rate": float(action_count / len(target)),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "benchmark_fraud_amount_total": float(amounts[target == 1].sum()),
        "benchmark_fraud_amount_actioned": float(amounts[action & (target == 1)].sum()),
        "benchmark_fraud_amount_blocked": float(amounts[block & (target == 1)].sum()),
        "estimated_decision_latency_ms_per_row": float(decision_latency_ms),
    }


def named_profiles(tradeoffs: list[dict]) -> dict:
    definitions = {
        "Conservative Block": {
            "maximum_action_rate": 0.005,
            "minimum_block_precision": 0.90,
            "sort": lambda row: (
                row["block_precision"],
                row["precision"],
                row["recall"],
                -row["action_rate"],
            ),
        },
        "Balanced Demo": {
            "maximum_action_rate": 0.01,
            "minimum_block_precision": 0.75,
            "sort": lambda row: (
                row["f1"],
                row["f2"],
                row["precision"],
                -row["action_rate"],
            ),
        },
        "Recall First": {
            "maximum_action_rate": 0.02,
            "minimum_block_precision": 0.50,
            "sort": lambda row: (
                row["recall"],
                row["f2"],
                row["precision"],
                -row["action_rate"],
            ),
        },
    }
    profiles = {}
    for name, definition in definitions.items():
        eligible = [
            row
            for row in tradeoffs
            if row["action_rate"] <= definition["maximum_action_rate"] + 1e-12
            and row["block_precision"] >= definition["minimum_block_precision"]
        ]
        profiles[name] = {
            "constraints": {
                "maximum_action_rate": definition["maximum_action_rate"],
                "minimum_block_precision": definition["minimum_block_precision"],
            },
            "available": bool(eligible),
            "measured_policy": (
                max(eligible, key=definition["sort"]) if eligible else None
            ),
        }
    return profiles
