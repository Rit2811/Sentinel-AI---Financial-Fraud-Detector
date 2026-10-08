"""Frozen feature/score checks on explicitly isolated PostgreSQL/Redis only."""

import json
import os
import threading
import time
from uuid import uuid4

import numpy as np
import psycopg
import pytest
import redis
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fraud_ml.features import FEATURE_ORDER
from fraud_ml.serving import FrozenScorer
from fraud_ml.worker import ScoringWorker, guard_fixture_urls
from test_feature_contract import BUNDLE, PIN, contract_events, expected_features


@pytest.fixture(scope="module")
def live_scorer():
    scorer = FrozenScorer(BUNDLE, PIN)
    scorer.verify_references()
    return scorer


@pytest.fixture
def frozen_live(live_scorer):
    pg, rd = os.getenv("TEST_DATABASE_URL"), os.getenv("TEST_REDIS_URL")
    if not pg or not rd:
        pytest.skip("Explicit isolated PostgreSQL/Redis fixture URLs required")
    guard_fixture_urls(pg, rd)

    def connect():
        return psycopg.connect(
            pg, autocommit=True, row_factory=dict_row, connect_timeout=3
        )

    transport = redis.Redis.from_url(rd, decode_responses=True, socket_timeout=3)
    worker = ScoringWorker(
        connect(),
        transport,
        live_scorer,
        str(uuid4()),
        "1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696",
        mode="fixture",
        stream="task6-test:" + str(uuid4()),
        concurrent_sessions=2,
        connection_factory=connect,
    )
    context = {"worker": worker, "connect": connect, "redis": transport}
    try:
        yield context
    finally:
        context["worker"].close()
        transport.delete(worker.stream)
        transport.close()


def enqueue(worker, event):
    # The fixture guard and worker's current_database check precede every write.
    envelope = {
        name: event[name]
        for name in (
            "schema_version",
            "data_origin",
            "event_id",
            "authorization_id",
            "occurred_at",
        )
    }
    envelope["correlation_id"] = str(uuid4())
    with worker.db.transaction():
        worker.db.execute(
            """INSERT INTO authorization_events(event_id,authorization_id,occurred_at,
                schema_version,data_origin,amount_minor,currency,card_token,merchant_id,
                merchant_category,time_basis,currency_basis,sanitized_payload)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            tuple(
                event[name]
                for name in (
                    "event_id",
                    "authorization_id",
                    "occurred_at",
                    "schema_version",
                    "data_origin",
                    "amount_minor",
                    "currency",
                    "card_token",
                    "merchant_id",
                    "merchant_category",
                    "time_basis",
                    "currency_basis",
                )
            )
            + (Jsonb(event),),
        )
        worker.db.execute(
            "INSERT INTO authorization_event_outbox(outbox_id,event_id,envelope) VALUES(%s,%s,%s)",
            (uuid4(), event["event_id"], Jsonb(envelope)),
        )
    message = worker.redis.xadd(worker.stream, {"envelope": json.dumps(envelope)})
    worker.db.execute(
        "UPDATE authorization_event_outbox SET status='published',published_at=clock_timestamp(),stream_message_id=%s WHERE event_id=%s",
        (message, event["event_id"]),
    )
    return envelope


def settle(worker, events, *, acknowledgements=False):
    until = time.monotonic() + 5
    ids = [event["event_id"] for event in events]
    while time.monotonic() < until:
        worker.cycle()
        rows = worker.db.execute(
            "SELECT status FROM scoring_jobs WHERE run_id=%s AND event_id=ANY(%s::uuid[])",
            (worker.run_id, ids),
        ).fetchall()
        if (
            len(rows) == len(events)
            and all(row["status"] == "scored" for row in rows)
            and not worker.parallel.active
            and (
                not acknowledgements
                or all(
                    group["pending"] == 0 and group["lag"] == 0
                    for group in worker.redis.xinfo_groups(worker.stream)
                    if group["name"] == worker.group
                )
            )
        ):
            return
        if any(row["status"] in ("failed", "expired") for row in rows):
            pytest.fail(
                "Generated contract fixture did not score within the unchanged deadline"
            )
        time.sleep(0.005)
    pytest.fail("Generated contract fixture did not settle")


def check_vectors_and_scores(worker, events):
    expected = expected_features(events)
    probabilities, actions = worker.scorer.score(expected)
    rows = []
    for index, event in enumerate(events):
        row = worker.db.execute(
            "SELECT f.*,r.probability,r.action FROM scoring_feature_snapshots f JOIN scoring_results r USING(run_id,event_id) WHERE f.run_id=%s AND f.event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {name: row[name] for name in FEATURE_ORDER} == expected[index]
        assert row["history_sequence"] == sum(
            previous["card_token"] == event["card_token"] for previous in events[:index]
        )
        assert np.isclose(
            row["probability"], probabilities[index], atol=1e-12, rtol=1e-12
        )
        assert row["action"] == actions[index]
        rows.append(row)
    for table in (
        "scoring_history",
        "scoring_feature_snapshots",
        "scoring_predictions",
        "scoring_results",
        "simulated_executions",
    ):
        assert worker.db.execute(
            f"SELECT count(*) AS n FROM {table} WHERE run_id=%s", (worker.run_id,)
        ).fetchone()["n"] == len(events)
    assert (
        worker.db.execute(
            "SELECT count(*) AS n FROM simulated_executions x JOIN scoring_jobs j USING(run_id,event_id) WHERE x.run_id=%s AND (j.status<>'scored' OR x.executed_at>j.deadline_at)",
            (worker.run_id,),
        ).fetchone()["n"]
        == 0
    )
    return rows


@pytest.mark.parametrize("schedule", ["burst", "paced"])
def test_frozen_live_pacing_ties_windows_and_duplicate_parity(frozen_live, schedule):
    worker = frozen_live["worker"]
    events = contract_events(str(uuid4()))
    envelopes = []
    if schedule == "burst":
        for first in range(0, len(events), 4):
            group = events[first : first + 4]
            envelopes.extend(enqueue(worker, event) for event in group)
            settle(worker, events[: first + len(group)])
    else:
        for index, event in enumerate(events):
            envelopes.append(enqueue(worker, event))
            settle(worker, events[: index + 1])
            time.sleep(0.015)
    before = check_vectors_and_scores(worker, events)
    # Reverse duplicate Redis delivery cannot change authoritative DB history.
    for envelope in reversed(envelopes):
        worker.redis.xadd(worker.stream, {"envelope": json.dumps(envelope)})
    settle(worker, events, acknowledgements=True)
    assert check_vectors_and_scores(worker, events) == before
    assert worker.redis.xpending(worker.stream, worker.group)["pending"] == 0


def test_frozen_history_rebuild_precedes_readiness_and_scores_after_restart(
    frozen_live,
):
    worker = frozen_live["worker"]
    events = contract_events(str(uuid4()))
    for event in events[:5]:
        enqueue(worker, event)
        settle(worker, events[: events.index(event) + 1])
    before = check_vectors_and_scores(worker, events[:5])
    worker.close()
    with frozen_live["connect"]() as db:
        # Deliberate loss only in the guarded tmpfs fixture; snapshots remain intact.
        db.execute("ALTER TABLE scoring_history DISABLE TRIGGER USER")
        try:
            db.execute("DELETE FROM scoring_history WHERE run_id=%s", (worker.run_id,))
        finally:
            db.execute("ALTER TABLE scoring_history ENABLE TRIGGER USER")
    resumed = ScoringWorker(
        frozen_live["connect"](),
        frozen_live["redis"],
        worker.scorer,
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
        concurrent_sessions=2,
        connection_factory=frozen_live["connect"],
    )
    frozen_live["worker"] = resumed
    assert (
        resumed.db.execute(
            "SELECT count(*) AS n FROM scoring_history WHERE run_id=%s",
            (resumed.run_id,),
        ).fetchone()["n"]
        == 5
    )
    assert (
        resumed.db.execute(
            "SELECT ready FROM scoring_worker_health WHERE run_id=%s", (resumed.run_id,)
        ).fetchone()["ready"]
        is False
    )
    assert check_vectors_and_scores(resumed, events[:5]) == before
    for index, event in enumerate(events[5:], 5):
        enqueue(resumed, event)
        settle(resumed, events[: index + 1])
    check_vectors_and_scores(resumed, events)


def test_frozen_inference_retry_does_not_repeat_history_or_change_features(
    frozen_live, monkeypatch
):
    worker = frozen_live["worker"]
    events = contract_events(str(uuid4()))[:5]
    original = worker.scorer.score
    seen = []
    lock = threading.Lock()

    def fail_once(vectors):
        with lock:
            should_fail = not seen
            seen.append(vectors)
        if should_fail:
            raise RuntimeError("Generated fixture inference retry")
        return original(vectors)

    monkeypatch.setattr(worker.scorer, "score", fail_once)
    for event in events:
        enqueue(worker, event)
    settle(worker, events)
    monkeypatch.setattr(worker.scorer, "score", original)
    check_vectors_and_scores(worker, events)
    assert len(seen) >= 2
    # Each retried feature vector is identical to its first attempt's snapshot.
    assert seen[0] in seen[1:]
