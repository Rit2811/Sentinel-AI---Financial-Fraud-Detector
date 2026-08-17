from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
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


def precision_recall_evidence(
    target,
    scores,
    budgets=(100, 500, 1000),
    maximum_curve_points=201,
) -> dict:
    target = np.asarray(target, dtype=int)
    scores = np.asarray(scores, dtype=float)
    precision, recall, thresholds = precision_recall_curve(target, scores)
    all_points = [
        {
            "threshold": float(thresholds[index]),
            "precision": float(precision[index]),
            "recall": float(recall[index]),
        }
        for index in range(len(thresholds))
    ]
    all_points.append(
        {
            "threshold": None,
            "precision": float(precision[-1]),
            "recall": float(recall[-1]),
        }
    )
    if len(all_points) > maximum_curve_points:
        selected = np.unique(
            np.linspace(0, len(all_points) - 1, maximum_curve_points, dtype=int)
        )
        curve = [all_points[index] for index in selected]
    else:
        curve = all_points

    order = np.argsort(-scores, kind="stable")
    fraud_total = int(target.sum())
    budget_rows = {}
    for budget in budgets:
        if budget > len(target):
            continue
        selected_target = target[order[:budget]]
        fraud_found = int(selected_target.sum())
        budget_rows[str(budget)] = {
            "reviewed": int(budget),
            "fraud_found": fraud_found,
            "precision": float(fraud_found / budget),
            "recall": float(fraud_found / fraud_total) if fraud_total else 0.0,
            "false_positives": int(budget - fraud_found),
        }
    return {
        "curve": curve,
        "curve_source_points": int(len(all_points)),
        "curve_maximum_reported_points": int(maximum_curve_points),
        "bounded_review_budgets": budget_rows,
    }


def fixed_rate_policy_evidence(target, scores, action_rate=0.01) -> dict:
    target = np.asarray(target, dtype=int)
    scores = np.asarray(scores, dtype=float)
    threshold = threshold_for_rate(scores, action_rate)
    actioned = scores >= threshold
    fraud_total = int(target.sum())
    fraud_found = int(target[actioned].sum())
    action_count = int(actioned.sum())
    return {
        "action_rate_target": float(action_rate),
        "threshold": float(threshold),
        "action_count": action_count,
        "action_rate_actual": float(action_count / len(target)),
        "precision": float(fraud_found / action_count) if action_count else 0.0,
        "recall": float(fraud_found / fraud_total) if fraud_total else 0.0,
    }


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


def profile_definitions() -> dict:
    return {
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


def named_profiles(tradeoffs: list[dict]) -> dict:
    profiles = {}
    definitions = profile_definitions()
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
