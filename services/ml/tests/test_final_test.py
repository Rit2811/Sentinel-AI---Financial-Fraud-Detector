import json

import pytest

from fraud_ml.final_test import policy_metrics, verify_authorization, wilson


def test_final_evaluation_rejects_missing_exact_authorization(tmp_path):
    path = tmp_path / "approval.json"
    path.write_text(json.dumps({"bundle_sha256": "a" * 64}))
    with pytest.raises(ValueError, match="authorization"):
        verify_authorization(path, "a" * 64)


def test_wilson_contains_observed_rate():
    lower, upper = wilson(201, 257797)
    assert 0.000679 < lower < 201 / 257797 < upper < 0.000896


def test_acceptance_uses_observed_limits_not_aspirational_target():
    policy = dict(
        normal_transactions_per_second=1,
        peak_transactions_per_second=5,
        staffed_hours_per_day=8,
        minimum_fraud_routed_rate=0.9,
        maximum_false_block_rate=0.001,
        maximum_reviews_per_hour=20,
        maximum_reviews_per_staffed_day=160,
    )
    counts = dict(
        fraud=1000,
        legitimate=100000,
        fraud_review=10,
        fraud_block=900,
        legitimate_review=10,
        legitimate_block=90,
    )
    metrics, checks = policy_metrics(counts, policy)
    assert all(checks.values()) and metrics["fraud_routed_rate"] == 0.91
    counts["legitimate_block"] = 101
    assert not policy_metrics(counts, policy)[1]["legitimate_false_blocks"]
