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


def application_environment(repo_root):
    preferred = repo_root / ".env.application.local"
    legacy = repo_root / ".env.task6.local"
    return preferred if preferred.exists() or not legacy.exists() else legacy


def check_workload(path, package_pin, tps, minimum_seconds):
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        report.get("diagnostic_only") is True
        or report.get("bundle_sha256") != package_pin
        or report.get("tps") != tps
        or report.get("requested_seconds", 0) < minimum_seconds
        or report.get("attempted") != tps * report.get("requested_seconds", 0)
        or report.get("accepted") != report.get("attempted")
        or (
            report.get("database_target_sha256")
            and report.get("clock_checks_passed") is not True
        )
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


def check_deployment_workloads(normal_path, peak_path, package_pin, run_id, target_pin):
    normal = check_workload(normal_path, package_pin, 1, 600)
    peak = check_workload(peak_path, package_pin, 5, 600)
    for report in (normal, peak):
        if (
            report.get("run_id") != run_id
            or report.get("database_target_sha256") != target_pin
        ):
            raise ValueError("Workload evidence belongs to another deployment")
    if any(normal[key] != peak[key] for key in ("worker_image_id", "backend_image_id")):
        raise ValueError("Normal and peak deployment images differ")
    if normal.get("pipeline_configuration") != peak.get("pipeline_configuration"):
        raise ValueError("Normal and peak pipeline configuration differs")
    return normal, peak


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    parser.add_argument("--gate-report-sha256", required=True)
    parser.add_argument("--normal-report", type=Path, required=True)
    parser.add_argument("--peak-report", type=Path, required=True)
    parser.add_argument("--worker-image", default="sentinel-ai-scoring-worker:replay")
    parser.add_argument("--backend-image", default="sentinel-ai-api:local")
    parser.add_argument("--deployment-run-id")
    parser.add_argument("--database-target-sha256")
    parser.add_argument("--deployment-environment", type=Path)
    parser.add_argument("--deployment-metadata", type=Path)
    parser.add_argument("--deployment-binding", type=Path)
    args = parser.parse_args(argv)
    scorer = FrozenScorer(args.bundle, args.bundle_sha256)
    scorer.verify_references()
    verify_activation(
        args.gate_report, args.gate_report_sha256, args.bundle_sha256, scorer.policy
    )
    normal = check_workload(args.normal_report, args.bundle_sha256, 1, 600)
    peak = check_workload(args.peak_report, args.bundle_sha256, 5, 600)
    for key, image in (
        ("worker_image_id", args.worker_image),
        ("backend_image_id", args.backend_image),
    ):
        current = subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip()
        if current != normal[key] or current != peak[key]:
            raise ValueError("Deployment image differs from measured image")
    ml_root = Path(__file__).resolve().parents[2]
    repo_root = ml_root.parents[1]
    environment = application_environment(repo_root)
    metadata = ml_root / "artifacts" / "runtime" / "application.json"
    if any(
        (
            args.deployment_run_id,
            args.database_target_sha256,
            args.deployment_environment,
            args.deployment_metadata,
        )
    ):
        if not all(
            (
                args.deployment_run_id,
                args.database_target_sha256,
                args.deployment_environment,
                args.deployment_metadata,
            )
        ):
            parser.error(
                "Cloud qualification requires run, target, environment and separate metadata"
            )
        check_deployment_workloads(
            args.normal_report,
            args.peak_report,
            args.bundle_sha256,
            args.deployment_run_id,
            args.database_target_sha256,
        )
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if (
            record["bundle_sha256"] != args.bundle_sha256
            or record["gate_report_sha256"] != args.gate_report_sha256
            or record["environment_sha256"] != sha256(environment)
        ):
            raise ValueError("Original runtime approval evidence changed")
        output = args.deployment_metadata.resolve()
        if output == metadata.resolve() or not output.is_relative_to(
            metadata.parent.resolve()
        ):
            raise ValueError(
                "Cloud metadata must remain separate in the private runtime directory"
            )
        from .application_benchmark import inspect_container, verify_external_target

        details = [
            inspect_container(name)
            for name in (
                "sentinel-ai-api-1",
                "sentinel-ai-publisher-1",
                "sentinel-ai-scoring-worker-1",
            )
        ]
        local_binding = None
        if args.deployment_binding:
            from .deployment_binding import verify_local_binding

            local_binding, _ = verify_local_binding(
                args.deployment_binding, inspect_container, metadata
            )
            if local_binding["database_target_sha256"] != args.database_target_sha256:
                raise ValueError("Qualification target differs from local binding")
        else:
            verify_external_target(
                details,
                args.database_target_sha256,
                repo_root / "secrets/supabase-root.crt",
            )
        api = dict(
            value.split("=", 1) for value in details[0]["Config"]["Env"] if "=" in value
        )
        command = details[2]["Config"]["Cmd"]
        if (
            api.get("SCORING_RUN_ID") != args.deployment_run_id
            or command[command.index("--run-id") + 1] != args.deployment_run_id
            or any(not detail["State"]["Running"] for detail in details)
            or details[0]["Image"] != peak["backend_image_id"]
            or details[1]["Image"] != peak["backend_image_id"]
            or details[2]["Image"] != peak["worker_image_id"]
        ):
            raise ValueError("Live deployment differs from qualified evidence")
        qualified = dict(
            record,
            status="LOAD_QUALIFIED",
            run_id=args.deployment_run_id,
            database_target_sha256=args.database_target_sha256,
            original_runtime_sha256=sha256(metadata),
            environment_files_sha256={
                str(environment.resolve()): sha256(environment),
                str(args.deployment_environment.resolve()): sha256(
                    args.deployment_environment
                ),
            },
            normal_report=str(args.normal_report.resolve()),
            normal_report_sha256=sha256(args.normal_report),
            peak_report=str(args.peak_report.resolve()),
            peak_report_sha256=sha256(args.peak_report),
            worker_image_id=peak["worker_image_id"],
            backend_image_id=peak["backend_image_id"],
            activation_authorized=False,
            pipeline_configuration=peak.get("pipeline_configuration"),
        )
        if local_binding:
            qualified.update(
                deployment_layout=local_binding["layout"],
                deployment_binding=str(args.deployment_binding.resolve()),
                deployment_binding_sha256=sha256(args.deployment_binding),
                reviewer_identity=api["REVIEWER_ID"],
            )
        with output.open("x", encoding="utf-8") as stream:
            json.dump(qualified, stream, indent=2)
        print(
            json.dumps(
                {
                    "metadata": str(output),
                    "status": "LOAD_QUALIFIED",
                    "activation_authorized": False,
                }
            )
        )
        return
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
