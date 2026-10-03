import numpy as np

from fraud_ml.ensemble.options import assess, constraint_thresholds


REQUIREMENTS = {
    "normal_transactions_per_second": 1,
    "peak_transactions_per_second": 5,
    "maximum_reviews_per_hour": 20,
    "maximum_reviews_per_staffed_day": 160,
    "staffed_hours_per_day": 8,
    "maximum_false_block_rate": 0.001,
    "minimum_fraud_routed_rate": 0.9,
    "preferred_fraud_routed_rate": 0.95,
}


def test_peak_review_load_is_not_hidden_by_normal_load():
    row = assess(
        {"review_rate": 0.002, "false_block_rate": 0.0009, "fraud_routed_rate": 0.96},
        REQUIREMENTS,
    )
    assert row["estimated_normal_reviews_per_hour"] == 7.2
    assert row["estimated_peak_reviews_per_hour"] == 36
    assert row["violations"] == ["peak_review_hour"]


def test_inclusive_operating_limits_are_provisional_not_approval():
    row = assess(
        {"review_rate": 0, "false_block_rate": 0.001, "fraud_routed_rate": 0.9},
        REQUIREMENTS,
    )
    assert row["feasibility"] == "PROVISIONAL_TARGETS_MET"
    assert row["preferred_capture_met"] is False


def test_constraint_cutoffs_preserve_score_ties_and_review_count_budget():
    labels = np.array([0] * 1000 + [1] * 20)
    scores = np.r_[np.linspace(0, 0.5, 1000), np.linspace(0.1, 0.9, 20)]
    r, b = constraint_thresholds(labels, scores, REQUIREMENTS)
    block = scores >= b
    review = (scores >= r) & ~block
    assert ((labels == 0) & block).sum() <= 1
    assert review.sum() <= np.floor(len(labels) * 20 / 18000)
