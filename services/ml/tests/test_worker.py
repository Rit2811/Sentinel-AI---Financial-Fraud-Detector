# Optional worker clients must be checked before importing the worker module.
# ruff: noqa: E402
import copy
import concurrent.futures
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


def test_publisher_crash_replay_preserves_worker_history_decisions_and_actions(harness):
    worker, _ = harness
    # Clear unrelated pending fixture work only after the strict fixture guard.
    guard_fixture_urls(os.environ["TEST_DATABASE_URL"], os.environ["TEST_REDIS_URL"])
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='dead_letter' WHERE status IN ('pending','publishing')"
    )
    backend = Path(__file__).resolve().parents[3] / "backend"
    config = dict(
        name=worker.stream, batchSize=4, claimIdleMs=0, maxAttempts=5, retention=100
    )
    env = dict(
        os.environ,
        CRASH_STREAM_CONFIG=json.dumps(config),
        CRASH_STDOUT_BOUNDARY="1",
        CRASH_STDIN_START="1",
    )
    child = subprocess.Popen(
        ["node", "tests/publisherCrashChild.js"],
        cwd=backend,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    code = """import pg from 'pg';import{createClient}from'redis';
import{publishOutboxBatch}from'./src/stream/publisherWorker.js';
import{assertTestDatabase,requireTestDatabaseUrl,requireTestRedisUrl}from'./tests/databaseSafety.js';
const pool=new pg.Pool({connectionString:requireTestDatabaseUrl(process.env.TEST_DATABASE_URL)});
await assertTestDatabase(pool);
const redis=createClient({url:requireTestRedisUrl(process.env.TEST_REDIS_URL),socket:{reconnectStrategy:false}});
redis.on('error',()=>{});await redis.connect();
console.log('publisher_ready');await new Promise(resolve=>process.stdin.once('data',resolve));
await publishOutboxBatch({pool,redis,streamConfig:JSON.parse(process.env.CRASH_STREAM_CONFIG),log:{info(){},error(){}}});
redis.destroy();await pool.end();"""
    replacement = subprocess.Popen(
        ["node", "--input-type=module", "-e", code],
        cwd=backend,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reader = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        for publisher in (child, replacement):
            assert (
                reader.submit(publisher.stdout.readline).result(timeout=20).strip()
                == "publisher_ready"
            )
        # Independent publishers are ready before acceptance, just as in load
        # tests. Kill the active one and recover through the waiting replacement.
        events = [
            enqueue(worker, offset=i, amount=amount)[0]
            for i, amount in enumerate((1234, 2500, 3500))
        ]
        worker.redis.delete(worker.stream)
        worker.db.execute(
            "UPDATE authorization_event_outbox SET status='pending',published_at=NULL,stream_message_id=NULL WHERE event_id=ANY(%s::uuid[])",
            ([event["event_id"] for event in events],),
        )
        child.stdin.write("start\n")
        child.stdin.flush()
        assert (
            reader.submit(child.stdout.readline).result(timeout=5).strip()
            == "before_commit"
        )
        child.kill()
        child.communicate(timeout=5)
        replacement.stdin.write("recover\n")
        replacement.stdin.flush()
        _, stderr = replacement.communicate(timeout=5)
        assert replacement.returncode == 0, stderr
    finally:
        for publisher in (child, replacement):
            if publisher.poll() is None:
                publisher.kill()
                publisher.communicate(timeout=5)
        reader.shutdown(wait=True)
    delivered = [
        json.loads(fields["envelope"])["event_id"]
        for _, fields in worker.redis.xrange(worker.stream)
    ]
    assert delivered == [event["event_id"] for event in events] * 2
    worker.cycle()
    worker.cycle()
    offline = FeatureStream()
    for event in events:
        assert state(worker, event)["status"] == "scored"
        stored = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {k: stored[k] for k in FEATURE_ORDER} == offline.transform(event)
    for table in (
        "scoring_history",
        "scoring_feature_snapshots",
        "scoring_predictions",
        "scoring_results",
        "simulated_executions",
    ):
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s", (worker.run_id,)
            ).fetchone()["n"]
            == 3
        )
    assert {
        row["state"]
        for row in worker.db.execute(
            "SELECT state FROM simulated_executions WHERE run_id=%s", (worker.run_id,)
        )
    } == {"allowed", "pending_review", "rejected"}


def test_first_inference_checkpoint_is_atomic_with_private_prediction(
    harness, monkeypatch
):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    event_id = event["event_id"]
    original = worker.scorer.score
    observed = []

    def score(features):
        assert worker.db.info.transaction_status == psycopg.pq.TransactionStatus.INTRANS
        with psycopg.connect(
            os.environ["TEST_DATABASE_URL"], row_factory=dict_row
        ) as peer:
            job = peer.execute(
                "SELECT status,attempts FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
                (worker.run_id, event_id),
            ).fetchone()
            assert job is None
            for table in ("scoring_history", "scoring_feature_snapshots"):
                assert (
                    peer.execute(
                        f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                        (worker.run_id, event_id),
                    ).fetchone()["n"]
                    == 0
                )
        observed.append(features)
        return original(features)

    monkeypatch.setattr(worker.scorer, "score", score)
    monkeypatch.setattr(
        worker,
        "prepare_pending",
        lambda _: pytest.fail("New published jobs need no second preparation commit"),
    )
    worker.drain()
    assert len(observed) == 1
    assert state(worker, event)["status"] == "scored"
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], row_factory=dict_row) as peer:
        for table in (
            "scoring_history",
            "scoring_feature_snapshots",
            "scoring_predictions",
        ):
            assert (
                peer.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                    (worker.run_id, event_id),
                ).fetchone()["n"]
                == 1
            )
    worker.drain()
    assert len(observed) == 1


def test_first_preparation_failure_rolls_back_checkpoint(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    event_id = event["event_id"]
    name = "reject_prepare_" + uuid4().hex
    worker.db.execute("""CREATE FUNCTION pg_temp.reject_first_prepare() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'first preparation rejected'; END $$""")
    worker.db.execute(f"""CREATE TRIGGER {name} BEFORE UPDATE ON scoring_jobs
        FOR EACH ROW WHEN (NEW.run_id='{worker.run_id}'::uuid AND NEW.status='scoring')
        EXECUTE FUNCTION pg_temp.reject_first_prepare()""")
    try:
        with pytest.raises(
            psycopg.errors.RaiseException, match="first preparation rejected"
        ):
            worker.drain()
        for table in (
            "scoring_jobs",
            "scoring_history",
            "scoring_feature_snapshots",
            "simulated_executions",
        ):
            assert (
                worker.db.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                    (worker.run_id, event_id),
                ).fetchone()["n"]
                == 0
            )
    finally:
        worker.db.execute(f"DROP TRIGGER {name} ON scoring_jobs")
    worker.drain()
    for table in ("scoring_jobs", "scoring_history", "scoring_feature_snapshots"):
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                (worker.run_id, event_id),
            ).fetchone()["n"]
            == 1
        )


def test_combined_commit_failure_rolls_back_history_and_prediction(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    name = "reject_combined_" + uuid4().hex
    worker.db.execute("""CREATE FUNCTION pg_temp.reject_combined_commit() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'combined commit rejected'; END $$""")
    worker.db.execute(f"""CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON scoring_predictions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.run_id='{worker.run_id}'::uuid)
        EXECUTE FUNCTION pg_temp.reject_combined_commit()""")
    try:
        with pytest.raises(
            psycopg.errors.RaiseException, match="combined commit rejected"
        ):
            worker.drain()
        for table in (
            "scoring_jobs",
            "scoring_history",
            "scoring_feature_snapshots",
            "scoring_predictions",
            "scoring_results",
            "simulated_executions",
        ):
            assert (
                worker.db.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                    (worker.run_id, event["event_id"]),
                ).fetchone()["n"]
                == 0
            )
    finally:
        worker.db.execute(f"DROP TRIGGER {name} ON scoring_predictions")
    worker.cycle()
    assert state(worker, event)["status"] == "scored"
    for table in ("scoring_history", "scoring_predictions", "simulated_executions"):
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s AND event_id=%s",
                (worker.run_id, event["event_id"]),
            ).fetchone()["n"]
            == 1
        )


def test_batch_predictions_are_committed_before_execution(harness, monkeypatch):
    worker, _ = harness
    events = [enqueue(worker, offset=i)[0] for i in range(2)]
    original = worker.finalize_batch
    witnessed = []

    def finalize(event_ids):
        with psycopg.connect(
            os.environ["TEST_DATABASE_URL"], row_factory=dict_row
        ) as peer:
            rows = peer.execute(
                "SELECT event_id,xmin::text AS xid FROM scoring_predictions WHERE run_id=%s",
                (worker.run_id,),
            ).fetchall()
            assert len(rows) == 2
            assert len({row["xid"] for row in rows}) == 1
            assert {str(row["event_id"]) for row in rows} == {
                event["event_id"] for event in events
            }
        witnessed.extend(event_ids)
        original(event_ids)

    monkeypatch.setattr(worker, "finalize_batch", finalize)
    worker.drain()
    assert len(witnessed) == 2
    for event in events:
        assert state(worker, event)["status"] == "scored"


def test_delayed_batch_prediction_commit_cannot_execute(harness):
    worker, _ = harness
    name = "delay_batch_" + uuid4().hex
    worker.db.execute("""CREATE FUNCTION pg_temp.delay_batch_commit() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(1.1); RETURN NULL; END $$""")
    worker.db.execute(f"""CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON scoring_predictions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.run_id='{worker.run_id}'::uuid)
        EXECUTE FUNCTION pg_temp.delay_batch_commit()""")
    try:
        events = [enqueue(worker, offset=i)[0] for i in range(2)]
        worker.drain()
        assert all(state(worker, event)["status"] == "expired" for event in events)
        for table, expected in [
            ("scoring_predictions", 2),
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


@pytest.mark.parametrize("batch", [False, True])
def test_same_transaction_prediction_cannot_execute(harness, batch):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    row = worker.db.execute(
        "SELECT e.*,o.envelope,e.created_at AS accepted_at FROM authorization_events e JOIN authorization_event_outbox o USING(event_id) WHERE event_id=%s",
        (event["event_id"],),
    ).fetchone()
    worker.assign(row)
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
            if batch:
                worker.finalize_batch([event["event_id"]])
            else:
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
def harness(request):
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
        db,
        transport,
        FixtureScorer(),
        run_id,
        "f" * 64,
        mode="fixture",
        stream=stream,
        diagnostic_deadline_ms=getattr(request, "param", None),
    )
    try:
        yield worker, pg_url
    finally:
        if not worker.db.closed:
            worker.close()
        transport.delete(stream)


@pytest.mark.parametrize("harness", [2000], indirect=True)
def test_diagnostic_two_second_run_keeps_identity_and_late_effect_guard(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    time.sleep(1.1)
    worker.drain()
    assert state(worker, event)["status"] == "scored"
    run = worker.db.execute(
        "SELECT deadline_ms,diagnostic_only FROM scoring_runs WHERE run_id=%s",
        (worker.run_id,),
    ).fetchone()
    assert run == {"deadline_ms": 2000, "diagnostic_only": True}
    job = state(worker, event)
    assert (job["deadline_at"] - job["created_at"]).total_seconds() == 2
    late, _, _ = enqueue(worker, offset=1)
    time.sleep(2.1)
    worker.drain()
    assert state(worker, late)["status"] == "expired"
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s AND event_id=%s",
            (worker.run_id, late["event_id"]),
        ).fetchone()["n"]
        == 0
    )
    worker.drain()
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_history WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 2
    )


def test_regular_run_cannot_take_two_second_deadline(harness):
    worker, _ = harness
    with pytest.raises(psycopg.errors.CheckViolation):
        worker.db.execute(
            "INSERT INTO scoring_runs(run_id,mode,bundle_sha256,policy_version,feature_version,deadline_ms) VALUES (%s,'fixture',%s,'FIXTURE_POLICY','sparkov-pit-v1',2000)",
            (str(uuid4()), "f" * 64),
        )


@pytest.mark.parametrize("harness", [2000], indirect=True)
def test_diagnostic_job_cannot_change_run_deadline(harness):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    row = worker.db.execute(
        "SELECT e.*,o.envelope,e.created_at AS accepted_at FROM authorization_events e JOIN authorization_event_outbox o USING(event_id) WHERE event_id=%s",
        (event["event_id"],),
    ).fetchone()
    worker.deadline_ms = 1000
    with pytest.raises(psycopg.errors.RaiseException, match="Diagnostic deadline"):
        worker.assign(row)
    worker.deadline_ms = 2000
    worker.assign(row)
    assert (
        state(worker, event)["deadline_at"] - state(worker, event)["created_at"]
    ).total_seconds() == 2


@pytest.mark.parametrize("harness", [2000], indirect=True)
def test_diagnostic_run_cannot_restart_as_approved_regular_run(harness):
    worker, url = harness
    worker.close()
    db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    try:
        with pytest.raises(ValueError, match="identity cannot change"):
            ScoringWorker(
                db,
                worker.redis,
                FixtureScorer(),
                worker.run_id,
                worker.package_pin,
                mode="fixture",
                stream=worker.stream,
            )
    finally:
        db.close()


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
    assert worker.drain() == 0
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_jobs WHERE run_id=%s", (worker.run_id,)
        ).fetchone()["n"]
        == 0
    )
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


def test_unpublished_predecessor_cannot_be_overtaken(harness):
    worker, _ = harness
    first, _, _ = enqueue(worker)
    second, _, _ = enqueue(worker, offset=1)
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='pending' WHERE event_id=%s",
        (first["event_id"],),
    )
    assert worker.drain() == 0
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='published' WHERE event_id=%s",
        (first["event_id"],),
    )
    assert worker.drain() == 2
    offline = FeatureStream()
    for event in (first, second):
        row = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {key: row[key] for key in FEATURE_ORDER} == offline.transform(event)


def test_terminal_delivery_only_reads_durable_state_before_ack(harness, monkeypatch):
    worker, url = harness
    event, _, _ = enqueue(worker)
    worker.drain()
    messages = worker.redis.xreadgroup(
        worker.group, "terminal-read", {worker.stream: ">"}
    )[0][1]
    original, commands = worker.db.execute, []

    def execute(query, *args, **kwargs):
        commands.append(str(query))
        return original(query, *args, **kwargs)

    monkeypatch.setattr(worker.db, "execute", execute)

    def acknowledge(*args):
        with psycopg.connect(url, row_factory=dict_row) as peer:
            assert (
                peer.execute(
                    "SELECT count(*) AS n FROM simulated_executions WHERE run_id=%s",
                    (worker.run_id,),
                ).fetchone()["n"]
                == 1
            )
        return 1

    monkeypatch.setattr(worker.redis, "xack", acknowledge)
    worker.delivery_batch(messages)
    assert len(commands) == 1 and commands[0].lstrip().startswith("SELECT")
    assert state(worker, event)["status"] == "scored"


def test_delivery_cannot_acknowledge_inside_uncommitted_transaction(
    harness, monkeypatch
):
    worker, _ = harness
    monkeypatch.setattr(
        worker.redis,
        "xack",
        lambda *_: pytest.fail("Uncommitted work must not be acknowledged"),
    )
    with worker.db.transaction():
        with pytest.raises(ValueError, match="durable boundary"):
            worker.delivery_batch([("1-0", {"envelope": "invalid"})])


def test_implicit_finalization_commit_deadline_rolls_back_all_effects(harness):
    worker, _ = harness
    name = "a_delay_finalization_" + uuid4().hex
    worker.db.execute(
        "CREATE FUNCTION pg_temp.delay_finalization() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(1.1); RETURN NULL; END $$"
    )
    worker.db.execute(
        f"CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON scoring_results DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.run_id='{worker.run_id}'::uuid) EXECUTE FUNCTION pg_temp.delay_finalization()"
    )
    try:
        event, _, _ = enqueue(worker)
        worker.drain()
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
        worker.db.execute(f"DROP TRIGGER {name} ON scoring_results")


def test_checkpoint_writer_bounds_and_run_identity_are_enforced(harness):
    worker, _ = harness
    for rows, deadline, message in [
        ([], 1000, "one to four"),
        ([{}] * 5, 1000, "one to four"),
        ([{}], 2000, "immutable run"),
    ]:
        with pytest.raises(psycopg.errors.RaiseException, match=message):
            worker.db.execute(
                "SELECT * FROM prepare_scoring_checkpoints(%s,%s,%s,'sparkov-pit-v1',%s,%s)",
                (
                    worker.run_id,
                    worker.package_pin,
                    worker.scorer.policy["policy_version"],
                    deadline,
                    Jsonb(rows),
                ),
            )
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_jobs WHERE run_id=%s", (worker.run_id,)
        ).fetchone()["n"]
        == 0
    )


def test_checkpoint_writer_has_no_public_execute_privilege(harness):
    worker, _ = harness
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid='public.prepare_scoring_checkpoints(uuid,text,text,text,integer,jsonb)'::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE'"
        ).fetchone()["n"]
        == 0
    )


def test_uncertain_implicit_finalization_reply_recovers_without_duplicate_effects(
    harness, monkeypatch
):
    worker, url = harness
    event, _, _ = enqueue(worker)
    original = worker.db.execute

    def lose_reply(query, *args, **kwargs):
        result = original(query, *args, **kwargs)
        if "INSERT INTO scoring_results" in str(query):
            raise psycopg.OperationalError("Lost implicit commit reply")
        return result

    monkeypatch.setattr(worker.db, "execute", lose_reply)
    with pytest.raises(psycopg.OperationalError, match="implicit commit reply"):
        worker.drain()
    monkeypatch.setattr(worker.db, "execute", original)
    worker.close()
    resumed = ScoringWorker(
        psycopg.connect(url, autocommit=True, row_factory=dict_row),
        worker.redis,
        FixtureScorer(),
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
    )
    try:
        monkeypatch.setattr(
            resumed.scorer,
            "score",
            lambda _: pytest.fail("Committed result must not be rescored"),
        )
        resumed.cycle()
        assert state(resumed, event)["status"] == "scored"
        assert resumed.redis.xpending(resumed.stream, resumed.group)["pending"] == 0
        for table in (
            "scoring_history",
            "scoring_predictions",
            "scoring_results",
            "simulated_executions",
        ):
            assert (
                resumed.db.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE run_id=%s",
                    (resumed.run_id,),
                ).fetchone()["n"]
                == 1
            )
    finally:
        resumed.close()


def test_delivery_batch_ack_loss_preserves_durable_audits(harness, monkeypatch):
    worker, url = harness
    for _ in range(2):
        worker.redis.xadd(worker.stream, {"envelope": "invalid"})
    messages = worker.redis.xreadgroup(
        worker.group, "batch-recovery", {worker.stream: ">"}, count=2
    )[0][1]
    original = worker.redis.xack

    def lose_ack(*_):
        with psycopg.connect(url, row_factory=dict_row) as peer:
            assert (
                peer.execute(
                    "SELECT count(*) AS n FROM scoring_delivery_failures WHERE run_id=%s",
                    (worker.run_id,),
                ).fetchone()["n"]
                == 2
            )
        raise redis.ConnectionError("lost acknowledgement")

    monkeypatch.setattr(worker.redis, "xack", lose_ack)
    with pytest.raises(redis.ConnectionError):
        worker.delivery_batch(messages)
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 2
    monkeypatch.setattr(worker.redis, "xack", original)
    worker.delivery_batch(messages)
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM scoring_delivery_failures WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()["n"]
        == 2
    )


def test_delivery_batch_failed_commit_never_acknowledges(harness, monkeypatch):
    worker, _ = harness
    name = "batch_commit_" + uuid4().hex
    worker.db.execute(
        f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit commit rejected'; END $$"
    )
    worker.db.execute(
        f"CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON scoring_delivery_failures DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {name}()"
    )
    monkeypatch.setattr(
        worker.redis,
        "xack",
        lambda *_: pytest.fail("Failed audit commit must not acknowledge"),
    )
    try:
        with pytest.raises(
            psycopg.errors.RaiseException, match="audit commit rejected"
        ):
            worker.delivery_batch(
                [("1-0", {"envelope": "invalid"}), ("2-0", {"envelope": "invalid"})]
            )
        assert (
            worker.db.execute(
                "SELECT count(*) AS n FROM scoring_delivery_failures WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == 0
        )
    finally:
        worker.db.execute(f"DROP TRIGGER {name} ON scoring_delivery_failures")
        worker.db.execute(f"DROP FUNCTION {name}()")


def test_application_gate_requires_authorization_without_test_access(tmp_path):
    with pytest.raises(ValueError, match="final-test"):
        verify_activation(None, None, PIN, {})
    file = tmp_path / "fake.json"
    file.write_text('{"status":"PASS"}')
    with pytest.raises(ValueError):
        verify_activation(file, "0" * 64, PIN, {})


def test_startup_stream_recovery_precedes_readiness(harness):
    worker, _ = harness
    for _ in range(120):
        worker.redis.xadd(worker.stream, {"envelope": "invalid"})
    for expected in (50, 100, 120):
        worker._ready_heartbeat_at = 0
        worker.cycle()
        row = worker.db.execute(
            "SELECT ready,error_code FROM scoring_worker_health WHERE run_id=%s",
            (worker.run_id,),
        ).fetchone()
        assert row["ready"] is (expected == 120)
        assert (
            worker.db.execute(
                "SELECT count(*) AS n FROM scoring_delivery_failures WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == expected
        )
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0


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


def test_prediction_deadline_race_recovers_without_worker_restart(harness, monkeypatch):
    worker, _ = harness
    event, _, _ = enqueue(worker)
    original = worker.db.execute
    delayed = [False]

    def cross_deadline(query, *args, **kwargs):
        if "INSERT INTO scoring_predictions" in query and not delayed[0]:
            delayed[0] = True
            time.sleep(1.05)
        return original(query, *args, **kwargs)

    monkeypatch.setattr(worker.db, "execute", cross_deadline)
    worker.cycle()
    assert delayed[0]
    assert state(worker, event)["status"] == "expired"
    assert worker.owns_lock and not worker.db.closed
    for table in ("scoring_history", "scoring_feature_snapshots"):
        assert (
            original(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == 1
        )
    for table in ("scoring_results", "simulated_executions"):
        assert (
            original(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s",
                (worker.run_id,),
            ).fetchone()["n"]
            == 0
        )
    monkeypatch.setattr(worker.db, "execute", original)
    second, _, _ = enqueue(worker, offset=1)
    worker.cycle()
    assert state(worker, second)["status"] == "scored"
    assert (
        original(
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


def test_bounded_batch_same_card_equal_times_and_windows_match_reference(harness):
    worker, _ = harness
    offline = FeatureStream()
    events = [
        enqueue(worker, offset=offset, amount=amount)[0]
        for offset, amount in ((0, 1234), (0, 2500), (3600, 3500), (86400, 4500))
    ]
    worker.drain()
    for sequence, event in enumerate(events):
        snapshot = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {name: snapshot[name] for name in FEATURE_ORDER} == offline.transform(
            event
        )
        assert snapshot["history_sequence"] == sequence
        assert state(worker, event)["status"] == "scored"
    worker.drain()
    for table in (
        "scoring_history",
        "scoring_feature_snapshots",
        "scoring_results",
        "simulated_executions",
    ):
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s", (worker.run_id,)
            ).fetchone()["n"]
            == 4
        )


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
        ["docker", "restart", "sentinel-test-redis-1"],
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
