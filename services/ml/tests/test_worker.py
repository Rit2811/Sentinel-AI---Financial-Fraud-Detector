# Optional worker clients must be checked before importing the worker module.
# ruff: noqa: E402
import copy
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

psycopg = pytest.importorskip("psycopg")
redis = pytest.importorskip("redis")
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fraud_ml.features import FEATURE_ORDER, FeatureStream
from fraud_ml.serving import FrozenScorer
from fraud_ml.worker import ScoringWorker, guard_fixture_urls, verify_activation

PIN = "1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696"
BUNDLE = Path("artifacts/frozen/random-forest/20261002T075558874195Z")


class FixtureScorer:
    policy = {"policy_version": "FIXTURE_POLICY"}
    r, b = 0.1, 0.25

    def score(self, features):
        p = np.array(
            [
                0.05 if f["amount"] < 20 else 0.15 if f["amount"] < 30 else 0.5
                for f in features
            ]
        )
        return p, np.where(p < self.r, "Pass", np.where(p < self.b, "Review", "Block"))


def test_delayed_prediction_commit_expires_without_execution(harness):
    worker, _ = harness
    name = "delay_prediction_" + uuid4().hex
    worker.db.execute("""CREATE FUNCTION pg_temp.delay_prediction_commit() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(1.1); RETURN NULL; END $$""")
    worker.db.execute(f"""CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON scoring_predictions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.run_id='{worker.run_id}'::uuid)
        EXECUTE FUNCTION pg_temp.delay_prediction_commit()""")
    try:
        event, _, _ = enqueue(worker)
        worker.cycle()
        assert state(worker, event)["status"] == "expired"
        for table, expected in [
            ("scoring_predictions", 1),
            ("scoring_results", 0),
            ("simulated_executions", 0),
        ]:
            assert (
                worker.db.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s",
                    (worker.run_id,),
                ).fetchone()["n"]
                == expected
            )
    finally:
        worker.db.execute(f"DROP TRIGGER {name} ON scoring_predictions")


def test_recovery_reuses_committed_prediction_without_reinference(harness, monkeypatch):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    original = worker.finalize_prediction
    monkeypatch.setattr(worker, "finalize_prediction", lambda _: None)
    worker.drain()
    assert state(worker, event)["status"] == "scoring"
    monkeypatch.setattr(worker, "finalize_prediction", original)
    monkeypatch.setattr(
        worker.scorer,
        "score",
        lambda _: pytest.fail("Committed prediction must not be rescored"),
    )
    worker.drain()
    assert state(worker, event)["status"] in ("scored", "expired")
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_predictions WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 1
    )


def test_same_transaction_prediction_cannot_execute(harness, monkeypatch):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    with monkeypatch.context() as patch:
        patch.setattr(worker, "score_batch", lambda _: None)
        worker.drain()
    with pytest.raises(psycopg.errors.RaiseException, match="Previously committed"):
        with worker.db.transaction():
            worker.db.execute(
                "UPDATE scoring_jobs SET status='scoring',attempts=1 WHERE run_id=%s",
                (worker.run_id,),
            )
            worker.db.execute(
                """INSERT INTO scoring_predictions
                SELECT run_id,event_id,0.05,'Pass',0.1,0.25,'below_review',
                    clock_timestamp(),clock_timestamp(),0,clock_timestamp()
                FROM scoring_jobs WHERE run_id=%s""",
                (worker.run_id,),
            )
            worker.db.execute(
                "INSERT INTO scoring_results SELECT * FROM scoring_predictions WHERE run_id=%s",
                (worker.run_id,),
            )
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )
    worker.cycle()
    assert state(worker, event)["status"] in ("scored", "expired")


@pytest.fixture
def harness():
    pg_url, redis_url = os.getenv("TEST_DATABASE_URL"), os.getenv("TEST_REDIS_URL")
    if not pg_url or not redis_url:
        pytest.skip("Explicit isolated PostgreSQL/Redis URLs required")
    guard_fixture_urls(pg_url, redis_url)
    db = psycopg.connect(
        pg_url, autocommit=True, row_factory=dict_row, connect_timeout=3
    )
    transport = redis.Redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3
    )
    run_id, stream = str(uuid4()), f"task6-test:{uuid4()}"
    worker = ScoringWorker(
        db, transport, FixtureScorer(), run_id, "f" * 64, mode="fixture", stream=stream
    )
    try:
        yield worker, pg_url
    finally:
        if not worker.db.closed:
            worker.close()
        transport.delete(stream)


def enqueue(worker, offset=0, amount=1234, card="a" * 64):
    event = {
        "schema_version": "2.0",
        "data_origin": "sparkov_replay",
        "event_id": str(uuid4()),
        "authorization_id": str(uuid4()),
        "occurred_at": (datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=offset))
        .isoformat()
        .replace("+00:00", "Z"),
        "amount_minor": amount,
        "currency": "USD",
        "card_token": "card_" + card,
        "merchant_id": "merchant_" + "b" * 64,
        "merchant_category": "grocery_pos",
        "time_basis": "source_wall_clock_as_utc",
        "currency_basis": "simulation_assumption",
    }
    envelope = {
        k: event[k]
        for k in (
            "event_id",
            "authorization_id",
            "occurred_at",
            "schema_version",
            "data_origin",
        )
    }
    envelope["correlation_id"] = str(uuid4())
    with worker.db.transaction():
        worker.db.execute(
            """INSERT INTO authorization_events (event_id,authorization_id,occurred_at,schema_version,data_origin,
          amount_minor,currency,card_token,merchant_id,merchant_category,time_basis,currency_basis,sanitized_payload)
          VALUES (%s,%s,%s,'2.0','sparkov_replay',%s,'USD',%s,%s,%s,%s,%s,%s)""",
            (
                event["event_id"],
                event["authorization_id"],
                event["occurred_at"],
                amount,
                event["card_token"],
                event["merchant_id"],
                event["merchant_category"],
                event["time_basis"],
                event["currency_basis"],
                Jsonb(event),
            ),
        )
        worker.db.execute(
            "INSERT INTO authorization_event_outbox(outbox_id,event_id,envelope) VALUES (%s,%s,%s)",
            (uuid4(), event["event_id"], Jsonb(envelope)),
        )
    message_id = worker.redis.xadd(worker.stream, {"envelope": json.dumps(envelope)})
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='published',stream_message_id=%s,published_at=clock_timestamp() WHERE event_id=%s",
        (message_id, event["event_id"]),
    )
    return event, message_id, envelope


def state(worker, event):
    return worker.db.execute(
        "SELECT * FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
        (worker.run_id, event["event_id"]),
    ).fetchone()


@pytest.mark.parametrize("waiting_for", ["publication", "retry"])
def test_waiting_jobs_do_not_busy_poll_and_resume_when_due(harness, waiting_for):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    row = worker.db.execute(
        """SELECT e.*,o.envelope,e.created_at AS accepted_at
        FROM authorization_events e JOIN authorization_event_outbox o USING(event_id)
        WHERE event_id=%s""",
        (event["event_id"],),
    ).fetchone()
    worker.assign(row)
    if waiting_for == "publication":
        worker.db.execute(
            "UPDATE authorization_event_outbox SET status='pending' WHERE event_id=%s",
            (event["event_id"],),
        )
    else:
        worker.db.execute(
            """UPDATE scoring_jobs SET status='unavailable',error_code='inference_unavailable',
            next_attempt_at=clock_timestamp()+interval '1 second' WHERE run_id=%s""",
            (worker.run_id,),
        )
    assert worker.drain() == 0
    assert state(worker, event)["attempts"] == 0
    if waiting_for == "publication":
        worker.db.execute(
            "UPDATE authorization_event_outbox SET status='published' WHERE event_id=%s",
            (event["event_id"],),
        )
    else:
        worker.db.execute(
            "UPDATE scoring_jobs SET next_attempt_at=clock_timestamp() WHERE run_id=%s",
            (worker.run_id,),
        )
    assert worker.drain() == 1
    assert state(worker, event)["status"] == "scored"


def test_unpublished_job_still_expires_durably(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='pending' WHERE event_id=%s",
        (event["event_id"],),
    )
    assert worker.drain() == 1
    assert worker.drain() == 0
    time.sleep(1.05)
    assert worker.drain() == 1
    assert state(worker, event)["status"] == "expired"
    assert state(worker, event)["attempts"] == 0
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )


def test_application_gate_requires_authorization_without_test_access(tmp_path):
    with pytest.raises(ValueError, match="final-test"):
        verify_activation(None, None, PIN, {})
    file = tmp_path / "fake.json"
    file.write_text('{"status":"PASS"}')
    with pytest.raises(ValueError):
        verify_activation(file, "0" * 64, PIN, {})


def test_fixture_guard_rejects_application_target():
    with pytest.raises(ValueError):
        guard_fixture_urls(
            "postgresql://localhost:15432/sentinel", "redis://localhost:16379/0"
        )


def test_fixture_guard_allows_only_exact_isolated_container_names():
    guard_fixture_urls(
        "postgresql://sentinel-task4-test-postgres-1:5432/sentinel_task4_test",
        "redis://sentinel-task4-test-redis-1:6379/0",
    )
    with pytest.raises(ValueError):
        guard_fixture_urls(
            "postgresql://postgres:5432/sentinel_task4_test", "redis://redis:6379/0"
        )


def test_three_actions_and_history_parity_across_ties(harness):
    worker, _ = harness
    offline = FeatureStream()
    for offset, amount in (
        (0, 1234),
        (0, 2500),
        (1, 3500),
        (3600, 1234),
        (86400, 1234),
    ):
        event, _, _ = enqueue(worker, offset, amount)
        worker.cycle()
        stored = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {k: stored[k] for k in FEATURE_ORDER} == offline.transform(event)
        assert state(worker, event)["status"] == "scored"
        assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0
    rows = worker.db.execute(
        "SELECT DISTINCT state FROM simulated_executions WHERE run_id=%s",
        (worker.run_id,),
    ).fetchall()
    assert {r["state"] for r in rows} == {"allowed", "pending_review", "rejected"}


def test_duplicate_and_ack_loss_have_one_durable_effect(harness, monkeypatch):
    worker, _ = harness
    event, _, envelope = enqueue(worker)
    original = worker.redis.xack

    def lost_ack(*args, **kwargs):
        raise redis.ConnectionError("fixture lost ACK")

    monkeypatch.setattr(worker.redis, "xack", lost_ack)
    with pytest.raises(redis.ConnectionError):
        worker.cycle()
    assert state(worker, event)["status"] == "scored"
    monkeypatch.setattr(worker.redis, "xack", original)
    worker.redis.xadd(worker.stream, {"envelope": json.dumps(envelope)})
    worker.cycle()
    for table in ("scoring_history", "scoring_results", "simulated_executions"):
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s", (worker.run_id,)
            ).fetchone()["n"]
            == 1
        )


def test_restart_after_snapshot_before_decision_restores_history(harness):
    worker, url = harness
    event, _, _ = enqueue(worker)
    row = worker.db.execute(
        "SELECT e.*,o.envelope,e.created_at AS accepted_at FROM authorization_events e JOIN authorization_event_outbox o USING(event_id) WHERE event_id=%s",
        (event["event_id"],),
    ).fetchone()
    worker.assign(row)
    worker.close()
    db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    resumed = ScoringWorker(
        db,
        worker.redis,
        FixtureScorer(),
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
    )
    try:
        resumed.cycle()
        assert state(resumed, event)["status"] == "scored"
        next_event, _, _ = enqueue(resumed, 1)
        resumed.cycle()
        row = db.execute(
            "SELECT prior_count_24h FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, next_event["event_id"]),
        ).fetchone()
        assert row["prior_count_24h"] == 1
    finally:
        resumed.close()


def test_redis_loss_reconciles_from_postgres(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    worker.redis.delete(worker.stream)
    worker.cycle()
    assert state(worker, event)["status"] == "scored"
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_history WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 1
    )


def test_late_inference_expires_without_action_and_still_contributes_history(harness):
    worker, _ = harness

    class Slow(FixtureScorer):
        def score(self, features):
            time.sleep(1.05)
            return super().score(features)

    worker.scorer = Slow()
    event, _, _ = enqueue(worker)
    worker.cycle()
    assert state(worker, event)["status"] == "expired"
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_results WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )
    worker.scorer = FixtureScorer()
    second, _, _ = enqueue(worker, 1)
    worker.cycle()
    assert (
        worker.db.execute(
            "SELECT prior_count_24h FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, second["event_id"]),
        ).fetchone()["prior_count_24h"]
        == 1
    )


def test_poison_payload_is_durably_rejected_before_ack(harness):
    worker, _ = harness
    worker.redis.xadd(
        worker.stream,
        {"envelope": json.dumps({"is_fraud": 1, "cc_num": "forbidden-fixture"})},
    )
    worker.cycle()
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0
    row = worker.db.execute(
        "SELECT * FROM scoring_delivery_failures WHERE run_id=%s", (worker.run_id,)
    ).fetchone()
    assert row["error_code"] == "invalid_envelope"
    assert "forbidden-fixture" not in str(row)


def test_out_of_order_event_blocks_run(harness):
    worker, _ = harness
    enqueue(worker, 10)
    worker.cycle()
    late, _, _ = enqueue(worker, 9)
    worker.cycle()
    assert state(worker, late)["status"] == "failed"
    row = worker.db.execute(
        "SELECT * FROM scoring_worker_health WHERE run_id=%s", (worker.run_id,)
    ).fetchone()
    assert row["blocked"] and not row["ready"]


def test_second_worker_cannot_take_active_run(harness):
    worker, url = harness
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as db:
        with pytest.raises(ValueError, match="owns"):
            ScoringWorker(
                db,
                worker.redis,
                FixtureScorer(),
                worker.run_id,
                worker.package_pin,
                mode="fixture",
                stream=worker.stream,
            )


def test_burst_batch_preserves_individual_history_and_decisions(harness, monkeypatch):
    worker, _ = harness
    first, _, _ = enqueue(worker, 0)
    second, _, _ = enqueue(worker, 1)
    score = worker.scorer.score
    batches = []

    def record_batch(features):
        batches.append(features)
        return score(features)

    monkeypatch.setattr(worker.scorer, "score", record_batch)
    worker.cycle()
    assert state(worker, first)["status"] == "scored"
    assert state(worker, second)["status"] == "scored"
    assert len(batches) == 1 and len(batches[0]) == 2
    assert [row["prior_count_24h"] for row in batches[0]] == [0, 1]


def test_batch_expiry_is_per_transaction_without_discarding_timely_peer(harness):
    worker, _ = harness

    class SlowBatch(FixtureScorer):
        def score(self, features):
            time.sleep(0.3)
            return super().score(features)

    worker.scorer = SlowBatch()
    first, _, _ = enqueue(worker, 0)
    time.sleep(0.8)
    second, _, _ = enqueue(worker, 1)
    worker.cycle()
    assert state(worker, first)["status"] == "expired"
    assert state(worker, second)["status"] == "scored"
    rows = worker.db.execute(
        "SELECT event_id FROM simulated_executions WHERE run_id=%s", (worker.run_id,)
    ).fetchall()
    assert [str(row["event_id"]) for row in rows] == [second["event_id"]]
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0


def test_real_frozen_rf_live_features_probability_parity(harness):
    if not BUNDLE.exists():
        pytest.skip("Local frozen RF required")
    worker, _ = harness
    scorer = FrozenScorer(BUNDLE, PIN)
    scorer.verify_references()
    # This run remains a FIXTURE namespace; no serving activation or final test.
    worker.scorer = copy.copy(scorer)
    worker.scorer.policy = {**scorer.policy, "policy_version": "FIXTURE_POLICY"}
    offline = FeatureStream()
    for offset in (0, 0, 1, 3600):
        event, _, _ = enqueue(worker, offset)
        worker.cycle()
        expected, actions = scorer.score([offline.transform(event)])
        row = worker.db.execute(
            "SELECT probability,action FROM scoring_results WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert row is not None
        assert row["probability"] == pytest.approx(expected[0], abs=1e-12)
        assert row["action"] == actions[0]


def test_missing_history_is_rebuilt_and_verified_before_readiness(harness):
    worker, url = harness
    event, _, _ = enqueue(worker)
    worker.cycle()
    # Deliberate corruption only in the explicitly isolated fixture database.
    worker.db.execute("ALTER TABLE scoring_history DISABLE TRIGGER USER")
    try:
        worker.db.execute(
            "DELETE FROM scoring_history WHERE run_id=%s", (worker.run_id,)
        )
    finally:
        worker.db.execute("ALTER TABLE scoring_history ENABLE TRIGGER USER")
    worker.close()
    db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    resumed = ScoringWorker(
        db,
        worker.redis,
        FixtureScorer(),
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
    )
    try:
        assert (
            db.execute(
                "SELECT count(*) AS n FROM scoring_history WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == 1
        )
        resumed.cycle()
        assert state(resumed, event)["status"] == "scored"
    finally:
        resumed.close()


@pytest.mark.parametrize("phase", ["before_commit", "after_commit_before_ack"])
def test_real_process_death_recovers_without_duplicate_effect(harness, phase):
    worker, url = harness
    worker.close()
    script = """
import json, os, sys
sys.path.insert(0, 'tests')
import psycopg, redis
from psycopg.rows import dict_row
from fraud_ml.worker import ScoringWorker
from test_worker import FixtureScorer, enqueue
db=psycopg.connect(os.environ['TEST_DATABASE_URL'],autocommit=True,row_factory=dict_row)
r=redis.Redis.from_url(os.environ['TEST_REDIS_URL'],decode_responses=True)
w=ScoringWorker(db,r,FixtureScorer(),sys.argv[1],'f'*64,mode='fixture',stream=sys.argv[2])
event,_,_=enqueue(w)
print(event['event_id'],flush=True)
if sys.argv[3]=='before_commit':
    w.scorer.score=lambda *_:os._exit(91)
else:
    w.redis.xack=lambda *_:os._exit(92)
w.cycle()
"""
    crashed = subprocess.run(
        [sys.executable, "-c", script, worker.run_id, worker.stream, phase],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert crashed.returncode == (91 if phase == "before_commit" else 92), (
        crashed.stderr
    )
    event_id = crashed.stdout.strip().splitlines()[-1]
    db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    resumed = ScoringWorker(
        db,
        worker.redis,
        FixtureScorer(),
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
    )
    try:
        resumed.cycle()
        row = state(resumed, {"event_id": event_id})
        assert row["status"] in ("scored", "expired")
        if phase == "after_commit_before_ack":
            assert row["status"] == "scored"
        for table in ("scoring_history", "scoring_feature_snapshots"):
            assert (
                db.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s",
                    (worker.run_id,),
                ).fetchone()["n"]
                == 1
            )
        assert (
            db.execute(
                "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            <= 1
        )
    finally:
        resumed.close()


def test_exhausted_inference_retries_are_durable_terminal_failure(harness):
    worker, _ = harness

    class Broken(FixtureScorer):
        def score(self, features):
            raise RuntimeError("fixture unavailable")

    worker.scorer = Broken()
    event, _, _ = enqueue(worker)
    for _ in range(3):
        worker.cycle()
        time.sleep(0.055)
    row = state(worker, event)
    assert row["status"] == "failed" and row["attempts"] == 3
    assert row["error_code"] == "inference_failed" and not row["retryable"]
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_results WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )


def test_database_connection_loss_after_commit_recovers(harness):
    worker, url = harness
    event, _, _ = enqueue(worker)
    worker.cycle()
    with psycopg.connect(url, autocommit=True) as control:
        control.execute(
            "SELECT pg_terminate_backend(%s)", (worker.db.info.backend_pid,)
        )
    with pytest.raises(psycopg.Error):
        worker.cycle()
    worker.db.close()
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as db:
        resumed = ScoringWorker(
            db,
            worker.redis,
            FixtureScorer(),
            worker.run_id,
            worker.package_pin,
            mode="fixture",
            stream=worker.stream,
        )
        resumed.cycle()
        assert state(resumed, event)["status"] == "scored"
        assert (
            db.execute(
                "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == 1
        )
        resumed.close()


@pytest.mark.skipif(
    os.getenv("TEST_REDIS_RESTART") != "1",
    reason="Explicit isolated Redis container restart opt-in required",
)
def test_real_redis_restart_expires_backlog_without_execution(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    result = subprocess.run(
        ["docker", "restart", "sentinel-task4-test-redis-1"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    time.sleep(1.05)
    for attempt in range(30):
        try:
            worker.cycle()
            break
        except redis.ConnectionError:
            if attempt == 29:
                raise
            time.sleep(0.1)
    assert state(worker, event)["status"] == "expired"
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )
    second, _, _ = enqueue(worker, 1)
    worker.cycle()
    assert (
        worker.db.execute(
            "SELECT prior_count_24h FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, second["event_id"]),
        ).fetchone()["prior_count_24h"]
        == 1
    )
