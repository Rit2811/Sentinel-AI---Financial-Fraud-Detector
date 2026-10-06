import json

import pytest

from fraud_ml.runtime import (
    application_environment,
    check_workload,
    check_deployment_workloads,
)


def test_new_runtime_environment_uses_its_purpose_not_a_task_number(tmp_path):
    assert application_environment(tmp_path) == tmp_path / ".env.application.local"


def test_legacy_environment_remains_compatible_without_modifying_it(tmp_path):
    legacy = tmp_path / ".env.task6.local"
    legacy.write_text("original-private-configuration")
    assert application_environment(tmp_path) == legacy
    preferred = tmp_path / ".env.application.local"
    preferred.write_text("preferred-private-configuration")
    assert application_environment(tmp_path) == preferred
    assert legacy.read_text() == "original-private-configuration"


def evidence():
    return {
        "bundle_sha256": "f" * 64,
        "tps": 5,
        "requested_seconds": 600,
        "attempted": 3000,
        "accepted": 3000,
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


def test_unqualified_image_diagnostic_cannot_activate(tmp_path):
    report = evidence()
    report["diagnostic_only"] = True
    path = tmp_path / "diagnostic.json"
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


@pytest.mark.parametrize("required_tps,seconds", [(1, 600), (5, 600)])
def test_diagnostic_rate_cannot_satisfy_activation_gate(
    tmp_path, required_tps, seconds
):
    report = evidence()
    report.update(tps=3, offered_transactions_per_second=3)
    path = tmp_path / "diagnostic.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, required_tps, seconds)


@pytest.mark.parametrize("seconds", [30, 60, 599])
def test_normal_activation_requires_ten_minutes(tmp_path, seconds):
    report = evidence()
    report.update(tps=1, requested_seconds=seconds, attempted=seconds, accepted=seconds)
    path = tmp_path / "normal.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 1, 600)


@pytest.mark.parametrize("field,value", [("accepted", 2999), ("attempted", 2999)])
def test_runtime_requires_full_offered_and_accepted_count(tmp_path, field, value):
    report = evidence()
    report[field] = value
    path = tmp_path / "load.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="workload"):
        check_workload(path, "f" * 64, 5, 600)


def test_cloud_qualification_requires_recorded_clock_checks(tmp_path):
    report = evidence()
    report["database_target_sha256"] = "c" * 64
    path = tmp_path / "cloud.json"
    for recorded in (None, False):
        report["clock_checks_passed"] = recorded
        path.write_text(json.dumps(report))
        with pytest.raises(ValueError, match="workload"):
            check_workload(path, "f" * 64, 5, 600)
    report["clock_checks_passed"] = True
    path.write_text(json.dumps(report))
    assert check_workload(path, "f" * 64, 5, 600) == report


@pytest.mark.parametrize(
    "mismatch",
    [None, "run_id", "database_target_sha256", "worker_image_id", "backend_image_id"],
)
def test_cloud_normal_and_peak_must_bind_to_same_deployment(tmp_path, mismatch):
    peak = evidence() | {
        "run_id": "selected-run",
        "database_target_sha256": "c" * 64,
        "clock_checks_passed": True,
    }
    normal = peak | {
        "tps": 1,
        "offered_transactions_per_second": 1,
        "attempted": 600,
        "accepted": 600,
        "execution_checks": {"total": 600, "invalid_or_late": 0},
        "parity_scored_rows": 600,
        "published_outbox": 600,
        "durable_status_counts": {"scored": 600},
        "durable_decision_latency_ms": {"count": 600, "over_1000": 0, "maximum": 900},
    }
    if mismatch:
        peak[mismatch] = "other-deployment"
    n, p = tmp_path / "normal.json", tmp_path / "peak.json"
    n.write_text(json.dumps(normal))
    p.write_text(json.dumps(peak))
    if mismatch:
        with pytest.raises(ValueError, match="deployment"):
            check_deployment_workloads(n, p, "f" * 64, "selected-run", "c" * 64)
    else:
        assert check_deployment_workloads(n, p, "f" * 64, "selected-run", "c" * 64) == (
            normal,
            peak,
        )
