"""Verify a separately attested local deployment without editing old approvals."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .database import database_target_sha256
from .serving import sha256


def environment_digest(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def verify_activation_lineage(binding):
    """Require the owner's separate approval and an unchanged held qualification."""
    for key in ("activation_approval", "qualified_metadata", "held_binding"):
        if sha256(binding[key]) != binding[key + "_sha256"]:
            raise ValueError("Activation lineage evidence changed")
    approval = json.loads(Path(binding["activation_approval"]).read_text())
    qualified = json.loads(Path(binding["qualified_metadata"]).read_text())
    held = json.loads(Path(binding["held_binding"]).read_text())
    if (
        approval.get("decision") != "AUTHORIZE_LOCAL_ACTIVATION"
        or approval.get("qualified_metadata_sha256")
        != binding["qualified_metadata_sha256"]
        or approval.get("held_binding_sha256") != binding["held_binding_sha256"]
        or qualified.get("status") != "LOAD_QUALIFIED"
        or qualified.get("activation_authorized") is not False
        or qualified.get("deployment_binding_sha256") != binding["held_binding_sha256"]
        or held.get("status") != "RESTORED_VERIFIED_HELD"
        or qualified.get("original_runtime_sha256") != held["original_runtime_sha256"]
        or qualified.get("backend_image_id") != held["images"]["api"]
        or qualified.get("worker_image_id") != held["images"]["scoring-worker"]
    ):
        raise ValueError("Owner-approved held qualification required for activation")
    for key in (
        "layout",
        "run_id",
        "database_target_sha256",
        "original_runtime_sha256",
        "environment_file",
        "restore_verification",
        "restore_verification_sha256",
        "images",
        "volumes",
    ):
        if binding[key] != held[key]:
            raise ValueError("Activation changed the qualified deployment")
    for key in ("run_id", "database_target_sha256"):
        if qualified[key] != binding[key] or approval[key] != binding[key]:
            raise ValueError("Activation qualification identity mismatch")
    for key in ("normal_report", "peak_report"):
        if sha256(qualified[key]) != qualified[key + "_sha256"]:
            raise ValueError("Original qualified workload evidence changed")
    evidence = approval["evidence"]
    for key in ("technical_gates", "actions", "restart", "backup_restore", "readiness"):
        item = evidence[key]
        if sha256(item["path"]) != item["sha256"]:
            raise ValueError("Activation prerequisite evidence changed")
        report = json.loads(Path(item["path"]).read_text(encoding="utf-8-sig"))
        if key == "technical_gates":
            if (
                report.get("status") != "TASK6_TECHNICAL_GATES_PASSED_ACTIVATION_HELD"
                or report.get("qualified_metadata_sha256")
                != binding["qualified_metadata_sha256"]
            ):
                raise ValueError("Complete technical gates required")
        elif key == "readiness":
            if report.get("qualifiedWorkerEligible") is not True:
                raise ValueError("Qualified worker readiness required")
        elif report.get("status") != "PASS":
            raise ValueError("Passing action/recovery evidence required")
    technical = json.loads(Path(evidence["technical_gates"]["path"]).read_text())
    for name, key in (
        ("actions", "actions_report"),
        ("restart", "restart_verification"),
        ("backup_restore", "backup_restore_verification"),
        ("readiness", "readiness_verification"),
    ):
        if evidence[name]["path"] != technical[key]:
            raise ValueError(
                "Activation evidence differs from verified technical gates"
            )
    if evidence["actions"]["sha256"] != technical["actions_report_sha256"]:
        raise ValueError("Verified action evidence changed")
    held_env = Path(binding["held_environment_file"]).read_bytes()
    if sha256(binding["held_environment_file"]) != held["environment_sha256"]:
        raise ValueError("Held private configuration evidence changed")
    if held_env.count(b"SCORING_ACTIVATION_HOLD=1") != 1 or (
        Path(binding["environment_file"]).read_bytes()
        != held_env.replace(b"SCORING_ACTIVATION_HOLD=1", b"SCORING_ACTIVATION_HOLD=0")
    ):
        raise ValueError("Only the approved activation flag may change")
    return held


def verify_local_binding(path, inspect, original_runtime, *, allow_active=False):
    binding = json.loads(Path(path).read_text(encoding="utf-8"))
    active = binding.get("status") == "QUALIFIED_ACTIVE"
    if (
        binding.get("layout") != "laptop-local-pg17"
        or binding.get("status")
        not in (
            ("RESTORED_VERIFIED_HELD", "QUALIFIED_ACTIVE")
            if allow_active
            else ("RESTORED_VERIFIED_HELD",)
        )
        or binding.get("original_runtime_sha256") != sha256(original_runtime)
        or binding.get("environment_sha256") != sha256(binding["environment_file"])
        or binding.get("restore_verification_sha256")
        != sha256(binding["restore_verification"])
    ):
        raise ValueError("Local deployment binding or original evidence changed")
    held = verify_activation_lineage(binding) if active else None
    restore = json.loads(Path(binding["restore_verification"]).read_text())
    if restore.get("status") != "PASS" or restore.get("tables_verified") != 18:
        raise ValueError("Complete persistent local restore proof required")
    details = {}
    for name in ("api", "publisher", "scoring-worker", "postgres", "redis"):
        item = inspect(f"sentinel-ai-{name}-1")
        if (
            not item["State"]["Running"]
            or "sentinel-ai_default" not in item["NetworkSettings"]["Networks"]
        ):
            raise ValueError("Bound local container/network unavailable")
        if item["Image"] != binding["images"][name]:
            raise ValueError("Bound local image changed")
        env = dict(
            value.split("=", 1) for value in item["Config"]["Env"] if "=" in value
        )
        if environment_digest(env) != binding["environment_digests"][name]:
            raise ValueError("Bound local effective configuration changed")
        if active:
            qualified_env = dict(env)
            if name == "api":
                qualified_env["SCORING_ACTIVATION_HOLD"] = "1"
            if environment_digest(qualified_env) != held["environment_digests"][name]:
                raise ValueError("Activation changed qualified effective configuration")
        if name in ("api", "publisher", "scoring-worker"):
            url = env["POSTGRES_URL"]
            parsed = urlsplit(url)
            if (
                parsed.hostname != "postgres"
                or parsed.port != 5432
                or parsed.path != "/sentinel"
                or parsed.query
                or parsed.fragment
                or database_target_sha256(url) != binding["database_target_sha256"]
            ):
                raise ValueError("Bound local database identity mismatch")
        if name in ("postgres", "redis"):
            volume = binding["volumes"][name]
            destination = "/var/lib/postgresql/data" if name == "postgres" else "/data"
            if (
                volume in ("sentinel-ai-postgres-data", "sentinel-ai-redis-data")
                or "test" in volume
            ):
                raise ValueError(
                    "Original or fixture volume cannot be the new application"
                )
            if not any(
                m.get("Type") == "volume"
                and m.get("Name") == volume
                and m["Destination"] == destination
                for m in item["Mounts"]
            ):
                raise ValueError("Bound persistent application volume mismatch")
        details[name] = item
    api = dict(
        value.split("=", 1) for value in details["api"]["Config"]["Env"] if "=" in value
    )
    if (
        api.get("SCORING_ACTIVATION_HOLD") != ("0" if active else "1")
        or api.get("SCORING_RUN_ID") != binding["run_id"]
    ):
        raise ValueError(
            "Local qualification requires its bound run and activation hold"
        )
    return binding, api
