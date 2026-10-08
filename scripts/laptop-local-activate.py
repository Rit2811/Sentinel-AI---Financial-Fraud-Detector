"""Release an explicitly approved local hold without rewriting qualification evidence."""

import argparse
import importlib.util
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from fraud_ml.application_smoke import request
from fraud_ml.deployment_binding import environment_digest, verify_local_binding
from fraud_ml.runtime import check_deployment_workloads
from fraud_ml.serving import sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "local_driver", ROOT / "scripts/laptop-local.py"
)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
ART = driver.ART
OUT = driver.OUT
RUNTIME = ROOT / "services/ml/artifacts/runtime"
ORIGINAL = RUNTIME / "application.json"
QUALIFIED = RUNTIME / "laptop-local-qualified.json"
VERIFIED = RUNTIME / "laptop-local-verified.json"
HELD_BINDING = ART / "deployment-binding.json"
ACTIVE_BINDING = ART / "deployment-binding-active.json"
ACTIVE = RUNTIME / "laptop-local-active.json"
APPROVAL = ART / "activation-approval.json"
HELD_ENV = ART / "environment-qualified-held.env"


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def release(message):
    if not message.strip():
        raise ValueError("An explicit owner approval is required")
    if any(path.exists() for path in (ACTIVE, APPROVAL, ACTIVE_BINDING, HELD_ENV)):
        raise ValueError("Existing activation evidence must not be overwritten")
    held, _ = verify_local_binding(HELD_BINDING, driver.inspect, ORIGINAL)
    qualified = json.loads(QUALIFIED.read_text())
    technical = json.loads(VERIFIED.read_text())
    assert technical["status"] == "TASK6_TECHNICAL_GATES_PASSED_ACTIVATION_HELD"
    assert technical["qualified_metadata_sha256"] == sha256(QUALIFIED)
    assert qualified["deployment_binding_sha256"] == sha256(HELD_BINDING)
    for path, pin in qualified["environment_files_sha256"].items():
        assert sha256(path) == pin
    for key in ("normal_report", "peak_report"):
        assert sha256(qualified[key]) == qualified[key + "_sha256"]
    check_deployment_workloads(
        Path(qualified["normal_report"]),
        Path(qualified["peak_report"]),
        qualified["bundle_sha256"],
        qualified["run_id"],
        qualified["database_target_sha256"],
    )
    evidence_paths = {
        "technical_gates": VERIFIED,
        "actions": Path(technical["actions_report"]),
        "restart": Path(technical["restart_verification"]),
        "backup_restore": Path(technical["backup_restore_verification"]),
        "readiness": Path(technical["readiness_verification"]),
    }
    driver.probe()
    approval = {
        "decision": "AUTHORIZE_LOCAL_ACTIVATION",
        "owner_message": message,
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "Release local Task 6 hold; no Task 7, model, SLA, cloud or Git changes",
        "run_id": held["run_id"],
        "database_target_sha256": held["database_target_sha256"],
        "qualified_metadata_sha256": sha256(QUALIFIED),
        "held_binding_sha256": sha256(HELD_BINDING),
        "evidence": {
            key: {"path": str(path), "sha256": sha256(path)}
            for key, path in evidence_paths.items()
        },
    }
    original_env = driver.ENV.read_bytes()
    assert original_env.count(b"SCORING_ACTIVATION_HOLD=1") == 1
    HELD_ENV.write_bytes(original_env)
    write(APPROVAL, approval)
    try:
        driver.ENV.write_bytes(
            original_env.replace(
                b"SCORING_ACTIVATION_HOLD=1", b"SCORING_ACTIVATION_HOLD=0"
            )
        )
        driver.run(
            driver.BASE + ["up", "-d", "--no-deps", "--no-build", "--wait", "api"]
        )
        api = driver.inspect("sentinel-ai-api-1")
        env = dict(
            value.split("=", 1) for value in api["Config"]["Env"] if "=" in value
        )
        binding = dict(
            held,
            status="QUALIFIED_ACTIVE",
            environment_sha256=sha256(driver.ENV),
            held_environment_file=str(HELD_ENV),
            environment_digests=dict(
                held["environment_digests"], api=environment_digest(env)
            ),
            activation_approval=str(APPROVAL),
            activation_approval_sha256=sha256(APPROVAL),
            qualified_metadata=str(QUALIFIED),
            qualified_metadata_sha256=sha256(QUALIFIED),
            held_binding=str(HELD_BINDING),
            held_binding_sha256=sha256(HELD_BINDING),
        )
        write(ACTIVE_BINDING, binding)
        verify_local_binding(
            ACTIVE_BINDING, driver.inspect, ORIGINAL, allow_active=True
        )
        until = time.monotonic() + 30
        while request("/ready/scoring")[0] != 200:
            if time.monotonic() >= until:
                raise RuntimeError("Activated scoring readiness failed")
            time.sleep(0.5)
        active = dict(
            qualified,
            status="ACTIVE_QUALIFIED",
            activation_authorized=True,
            activated_at=datetime.now(UTC).isoformat(),
            qualified_metadata=str(QUALIFIED),
            qualified_metadata_sha256=sha256(QUALIFIED),
            activation_approval=str(APPROVAL),
            activation_approval_sha256=sha256(APPROVAL),
            deployment_binding=str(ACTIVE_BINDING),
            deployment_binding_sha256=sha256(ACTIVE_BINDING),
            environment_files_sha256=dict(
                qualified["environment_files_sha256"],
                **{str(driver.ENV): sha256(driver.ENV)},
            ),
        )
        write(ACTIVE, active)
    except Exception:
        driver.ENV.write_bytes(original_env)
        driver.run(
            driver.BASE + ["up", "-d", "--no-deps", "--no-build", "--wait", "api"]
        )
        write(
            OUT / "activation-rollback.json",
            {
                "status": "ACTIVATION_FAILED_HOLD_RESTORED",
                "activation_hold": 1,
            },
        )
        raise
    print(
        json.dumps(
            {
                "status": "ACTIVE_QUALIFIED",
                "scoring_readiness_http": 200,
                "metadata": str(ACTIVE),
                "original_qualifications_preserved": True,
            }
        )
    )


def finalize(actions):
    actions = actions.resolve()
    verify_local_binding(ACTIVE_BINDING, driver.inspect, ORIGINAL, allow_active=True)
    assert request("/ready/scoring")[0] == 200
    report = json.loads(actions.read_text())
    assert report["status"] == "PASS" and report["activation_authorized"] is True
    assert report["restart_verified_at"]
    active = json.loads(ACTIVE.read_text())
    for key in (
        "run_id",
        "bundle_sha256",
        "worker_image_id",
        "backend_image_id",
        "database_target_sha256",
    ):
        assert report[key] == active[key]
    env = driver.values()
    driver.probe()
    with psycopg.connect(
        env["HOST_DATABASE_URL"], autocommit=True, row_factory=dict_row
    ) as db:
        db.execute("SET default_transaction_read_only=on")
        counts = {
            "events": db.execute(
                "SELECT count(*) AS total FROM authorization_events"
            ).fetchone()["total"],
            "outbox": db.execute(
                "SELECT status,count(*) AS total FROM authorization_event_outbox GROUP BY status"
            ).fetchall(),
            "jobs": db.execute(
                "SELECT status,count(*) AS total FROM scoring_jobs WHERE run_id=%s GROUP BY status",
                (env["SCORING_RUN_ID"],),
            ).fetchall(),
            "invalid_or_late": db.execute(
                "SELECT count(*) AS total FROM simulated_executions x JOIN scoring_jobs j USING(run_id,event_id) WHERE j.status<>'scored' OR x.executed_at>j.deadline_at"
            ).fetchone()["total"],
            "ledger": db.execute(
                "SELECT count(*) AS total FROM pgmigrations"
            ).fetchone()["total"],
        }
        duplicates = {
            table: db.execute(
                f"SELECT count(*) AS total FROM (SELECT run_id,event_id FROM {table} GROUP BY run_id,event_id HAVING count(*)>1) d"
            ).fetchone()["total"]
            for table in (
                "scoring_history",
                "scoring_feature_snapshots",
                "scoring_predictions",
                "scoring_results",
                "simulated_executions",
            )
        }
    assert counts["invalid_or_late"] == 0 and all(v == 0 for v in duplicates.values())
    assert counts["outbox"] == [{"status": "published", "total": counts["events"]}]
    inventory = json.loads(
        (
            ROOT / "services/ml/artifacts/laptop-handoff/transfer-manifest.json"
        ).read_text()
    )
    assert all(
        sha256(ROOT / file["path"]) == file["sha256"] for file in inventory["files"]
    )
    final = {
        "status": "TASK6_COMPLETE_ACTIVE",
        "completed_at": datetime.now(UTC).isoformat(),
        "task5": "COMPLETE",
        "task6": "COMPLETE",
        "task7": "NOT_STARTED",
        "activation_authorized": True,
        "activation_hold": 0,
        "scoring_readiness_http": 200,
        "active_metadata": str(ACTIVE),
        "active_metadata_sha256": sha256(ACTIVE),
        "activation_approval": str(APPROVAL),
        "activation_approval_sha256": sha256(APPROVAL),
        "technical_gates": str(VERIFIED),
        "technical_gates_sha256": sha256(VERIFIED),
        "active_actions_report": str(actions),
        "active_actions_report_sha256": sha256(actions),
        "counts": counts,
        "duplicate_effects": duplicates,
        "original_private_hashes_verified": len(inventory["files"]),
        "pending_manual_actions_blocking": [],
        "pending_manual_actions_nonblocking": [],
    }
    write(RUNTIME / "laptop-local-complete.json", final)
    write(OUT / "activation-final-state.json", final)
    print(json.dumps(final))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("release", "finalize"))
    parser.add_argument("--approval-message")
    parser.add_argument("--actions-report", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "release":
            if not args.approval_message:
                parser.error(
                    "release requires --approval-message from the owner's approval"
                )
            release(args.approval_message)
        else:
            if not args.actions_report:
                parser.error("finalize requires --actions-report")
            finalize(args.actions_report)
    except Exception as error:
        # Exception strings may contain URLs or secrets. Retain only the error class.
        import traceback

        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "exception_type": type(error).__name__,
                    "frames": [
                        {
                            "file": Path(frame.filename).name,
                            "line": frame.lineno,
                            "function": frame.name,
                        }
                        for frame in traceback.extract_tb(error.__traceback__)
                    ],
                }
            )
        )
        raise SystemExit(1)
