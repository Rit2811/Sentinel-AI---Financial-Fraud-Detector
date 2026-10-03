"""Prepare private local configuration after model and workload gates pass."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path
from uuid import uuid4

from .serving import FrozenScorer, sha256
from .worker import verify_activation


def check_workload(path, package_pin, tps, minimum_seconds):
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        report.get("bundle_sha256") != package_pin
        or report.get("tps") != tps
        or report.get("requested_seconds", 0) < minimum_seconds
        or report.get("offered_transactions_per_second", 0) < tps * 0.99
        or report.get("all_attempts_timely_scored") is not True
        or report.get("commit_deadline_verification") != "postcommit-v1"
        or report.get("reserved_test_accessed") is not False
        or report.get("execution_checks", {}).get("invalid_or_late") != 0
        or report.get("parity_scored_rows") != report.get("attempted")
        or report.get("execution_checks", {}).get("total") != report.get("attempted")
        or report.get("published_outbox") != report.get("attempted")
        or report.get("durable_status_counts") != {"scored": report.get("attempted")}
        or report.get("durable_decision_latency_ms", {}).get("count")
        != report.get("attempted")
        or report.get("durable_decision_latency_ms", {}).get("over_1000") != 0
        or not 0
        <= report.get("durable_decision_latency_ms", {}).get("maximum", -1)
        <= 1000
        or report.get("failures")
        or not report.get("worker_image_id")
        or not report.get("backend_image_id")
    ):
        raise ValueError("Passing complete Docker workload evidence required")
    return report


def refresh_runtime_evidence(metadata, record, normal_path, peak_path, peak):
    updated = record | {
        "normal_report": str(normal_path.resolve()),
        "normal_report_sha256": sha256(normal_path),
        "peak_report": str(peak_path.resolve()),
        "peak_report_sha256": sha256(peak_path),
        "worker_image_id": peak["worker_image_id"],
        "backend_image_id": peak["backend_image_id"],
    }
    if updated == record:
        return False
    previous = metadata.read_bytes()
    if json.loads(previous) != record:
        raise ValueError("Runtime metadata changed during qualification")
    stamp = str(uuid4())
    backup = metadata.with_name(f"application-before-requalification-{stamp}.json")
    temporary = metadata.with_name(f"application-requalification-{stamp}.tmp")
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(previous)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(updated, stream, indent=2)
        if metadata.read_bytes() != previous:
            raise ValueError("Runtime metadata changed during qualification")
        os.replace(temporary, metadata)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    parser.add_argument("--gate-report-sha256", required=True)
    parser.add_argument("--normal-report", type=Path, required=True)
    parser.add_argument("--peak-report", type=Path, required=True)
    args = parser.parse_args(argv)
    scorer = FrozenScorer(args.bundle, args.bundle_sha256)
    scorer.verify_references()
    verify_activation(
        args.gate_report, args.gate_report_sha256, args.bundle_sha256, scorer.policy
    )
    normal = check_workload(args.normal_report, args.bundle_sha256, 1, 60)
    peak = check_workload(args.peak_report, args.bundle_sha256, 5, 600)
    for key, image in (
        ("worker_image_id", "sentinel-ai-scoring-worker:task6"),
        ("backend_image_id", "sentinel-ai-api:task4"),
    ):
        current = subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip()
        if current != normal[key] or current != peak[key]:
            raise ValueError("Deployment image differs from measured image")
    ml_root = Path(__file__).resolve().parents[2]
    repo_root = ml_root.parents[1]
    environment = repo_root / ".env.task6.local"
    metadata = ml_root / "artifacts" / "runtime" / "application.json"
    if environment.exists() or metadata.exists():
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if (
            record["bundle_sha256"] != args.bundle_sha256
            or record["gate_report_sha256"] != args.gate_report_sha256
            or record["environment_sha256"] != sha256(environment)
        ):
            raise ValueError(
                "Existing runtime configuration differs; preserve its run identity"
            )
        refresh_runtime_evidence(
            metadata, record, args.normal_report, args.peak_report, peak
        )
        print(
            json.dumps(
                {
                    "environment": str(environment),
                    "run_id": record["run_id"],
                    "reused": True,
                }
            )
        )
        return
    run_id = str(uuid4())
    values = {
        "SCORING_RUN_ID": run_id,
        "SCORING_BUNDLE_SHA256": args.bundle_sha256,
        "SCORING_BUNDLE_DIR": args.bundle.resolve().as_posix(),
        "SCORING_GATE_REPORT_SHA256": args.gate_report_sha256,
        "SCORING_GATE_DIR": args.gate_report.resolve().parent.as_posix(),
        "STREAM_POLL_MS": "50",
        "RESULT_API_TOKEN": secrets.token_urlsafe(32),
        "REVIEW_API_TOKEN": secrets.token_urlsafe(32),
        "REVIEWER_ID": "project_owner",
    }
    metadata.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(environment, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "# Private local credentials and durable run identity. Keep out of Git.\n"
        )
        stream.write(
            "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
        )
    record = {
        "run_id": run_id,
        "bundle_sha256": args.bundle_sha256,
        "gate_report_sha256": args.gate_report_sha256,
        "environment_sha256": sha256(environment),
        "normal_report": str(args.normal_report.resolve()),
        "normal_report_sha256": sha256(args.normal_report),
        "peak_report": str(args.peak_report.resolve()),
        "peak_report_sha256": sha256(args.peak_report),
        "worker_image_id": peak["worker_image_id"],
        "backend_image_id": peak["backend_image_id"],
        "reviewer_identity": "project_owner",
    }
    with metadata.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    print(
        json.dumps({"environment": str(environment), "run_id": run_id, "reused": False})
    )


if __name__ == "__main__":
    main()
