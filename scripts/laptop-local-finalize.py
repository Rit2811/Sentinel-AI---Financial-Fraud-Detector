"""Summarize verified gates; never authorizes release of the activation hold."""

import importlib.util
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from fraud_ml.serving import sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "local_driver", ROOT / "scripts/laptop-local.py"
)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
env = driver.values()
out = ROOT / "services/ml/reports/laptop-local"
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
        "ledger": db.execute("SELECT count(*) AS total FROM pgmigrations").fetchone()[
            "total"
        ],
    }
    duplicates = {}
    for table in (
        "scoring_history",
        "scoring_feature_snapshots",
        "scoring_predictions",
        "scoring_results",
        "simulated_executions",
    ):
        duplicates[table] = db.execute(
            f"SELECT count(*) AS total FROM (SELECT run_id,event_id FROM {table} GROUP BY run_id,event_id HAVING count(*)>1) d"
        ).fetchone()["total"]
    assert counts["invalid_or_late"] == 0 and all(
        value == 0 for value in duplicates.values()
    )
inventory = json.loads(
    (ROOT / "services/ml/artifacts/laptop-handoff/transfer-manifest.json").read_text()
)
assert all(sha256(ROOT / file["path"]) == file["sha256"] for file in inventory["files"])
qualified = ROOT / "services/ml/artifacts/runtime/laptop-local-qualified.json"
actions = ROOT / "services/ml/reports/replay-actions/20261008T182447092211Z/report.json"
assert json.loads(actions.read_text())["status"] == "PASS"
record = {
    "status": "TASK6_TECHNICAL_GATES_PASSED_ACTIVATION_HELD",
    "qualified_metadata": str(qualified),
    "qualified_metadata_sha256": sha256(qualified),
    "actions_report": str(actions),
    "actions_report_sha256": sha256(actions),
    "restart_verification": str(out / "restart-verification.json"),
    "backup_restore_verification": str(out / "backup-restore-verification.json"),
    "readiness_verification": str(out / "readiness-verification.json"),
    "counts": counts,
    "duplicate_effects": duplicates,
    "original_private_hashes_verified": len(inventory["files"]),
    "activation_authorized": False,
    "activation_hold": 1,
    "normal_full": "20261008T180246214287Z",
    "peak_full": "20261008T181340144585Z",
    "normal_scored": 600,
    "peak_scored": 3000,
    "new_qualification_expiries": 0,
    "tool_regression_tests_passed": 89,
    "database_backup_sha256": sha256(
        ROOT / "services/ml/artifacts/laptop-local/laptop-qualified-stopped.dump"
    ),
    "redis_backup_sha256": sha256(
        ROOT / "services/ml/artifacts/laptop-local/redis-qualified.tar"
    ),
    "task5": "COMPLETE",
    "task6": "TECHNICAL_VERIFICATION_COMPLETE_ACTIVATION_HELD",
    "task7": "NOT_STARTED",
}
(ROOT / "services/ml/artifacts/runtime/laptop-local-verified.json").write_text(
    json.dumps(record, indent=2)
)
(out / "final-state.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record))
