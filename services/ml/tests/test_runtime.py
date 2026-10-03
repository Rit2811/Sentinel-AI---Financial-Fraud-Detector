import json

import pytest

from fraud_ml.runtime import check_workload


def evidence():
    return {
        "bundle_sha256": "f" * 64,
        "tps": 5,
        "requested_seconds": 600,
        "attempted": 3000,
        "offered_transactions_per_second": 5,
        "all_attempts_timely_scored": True,
        "commit_deadline_verification": "postcommit-v1",
        "reserved_test_accessed": False,
        "execution_checks": {"total": 3000, "invalid_or_late": 0},
        "parity_scored_rows": 3000,
        "published_outbox": 3000,
        "durable_status_counts": {"scored": 3000},
        "durable_decision_latency_ms": {"count": 3000, "over_1000": 0, "maximum": 900},
        "failures": [],
        "worker_image_id": "worker-fixture",
        "backend_image_id": "backend-fixture",
    }


def test_runtime_requires_complete_peak_evidence(tmp_path):
    path = tmp_path / "load.json"
    report = evidence()
    path.write_text(json.dumps(report))
    assert check_workload(path, "f" * 64, 5, 600) == report
    report["requested_seconds"] = 599
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)


def test_expiry_cannot_be_overridden_by_summary_pass(tmp_path):
    path = tmp_path / "load.json"
    report = evidence()
    report["durable_status_counts"] = {"scored": 2999, "expired": 1}
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)


def test_runtime_rejects_other_package(tmp_path):
    path = tmp_path / "load.json"
    path.write_text(json.dumps(evidence()))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "a" * 64, 5, 600)


def test_runtime_rejects_a_client_that_did_not_offer_peak_rate(tmp_path):
    path = tmp_path / "load.json"
    report = evidence()
    report["offered_transactions_per_second"] = 1.67
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)


def test_runtime_rejects_late_durable_decisions(tmp_path):
    path = tmp_path / "load.json"
    report = evidence()
    report["durable_decision_latency_ms"]["maximum"] = 1001
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)


def test_runtime_rejects_precommit_only_evidence(tmp_path):
    path = tmp_path / "load.json"
    report = evidence()
    del report["commit_deadline_verification"]
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)
