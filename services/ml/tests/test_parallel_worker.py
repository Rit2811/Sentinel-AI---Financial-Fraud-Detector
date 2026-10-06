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

from fraud_ml.features import FEATURE_ORDER, FeatureStream
from fraud_ml.serving import FrozenScorer
from fraud_ml.worker import ScoringWorker, guard_fixture_urls
from test_worker import BUNDLE, PIN, FixtureScorer, enqueue, state


@pytest.fixture
def parallel_harness(request):
    pg, rd = os.getenv("TEST_DATABASE_URL"), os.getenv("TEST_REDIS_URL")
    if not pg or not rd:
        pytest.skip("Explicit isolated fixtures required")
    guard_fixture_urls(pg, rd)

    def connect():
        return psycopg.connect(
            pg, autocommit=True, row_factory=dict_row, connect_timeout=3
        )

    transport = redis.Redis.from_url(rd, decode_responses=True, socket_timeout=3)
    frozen = getattr(request, "param", None) == "frozen"
    if frozen and not BUNDLE.exists():
        pytest.skip("Trusted frozen artifact unavailable")
    scorer = FrozenScorer(BUNDLE, PIN) if frozen else FixtureScorer()
    if frozen:
        scorer.verify_references()
    worker = ScoringWorker(
        connect(),
        transport,
        scorer,
        str(uuid4()),
        PIN if frozen else "f" * 64,
        mode="fixture",
        stream="task6-test:" + str(uuid4()),
        concurrent_sessions=2,
        connection_factory=connect,
    )
    try:
        yield worker, pg, connect
    finally:
        worker.close()
        transport.delete(worker.stream)


def settle(worker, events):
    until = time.monotonic() + 5
    while time.monotonic() < until:
        worker.cycle()
        if (
            all(
                (row := state(worker, event))
                and row["status"] in ("scored", "failed", "expired")
                for event in events
            )
            and not worker.parallel.active
        ):
            return
        time.sleep(0.005)
    pytest.fail("Parallel attempts did not settle")


def test_different_cards_overlap_without_parallel_history_for_one_card(
    parallel_harness, monkeypatch
):
    worker, _, _ = parallel_harness
    barrier = threading.Barrier(2)
    original = worker.scorer.score
    observed = []

    def score(features):
        observed.append(threading.get_ident())
        barrier.wait(timeout=0.5)
        return original(features)

    monkeypatch.setattr(worker.scorer, "score", score)
    events = [
        enqueue(worker, offset=0, card="a" * 64)[0],
        enqueue(worker, offset=0, card="b" * 64)[0],
    ]
    settle(worker, events)
    assert len(set(observed)) == 2
    assert all(state(worker, event)["status"] == "scored" for event in events)


def test_parallel_same_card_ties_windows_duplicates_match_canonical_reference(
    parallel_harness,
):
    worker, _, _ = parallel_harness
    events = []
    for offset in (0, 0, 3600, 86400):
        for card in ("a" * 64, "b" * 64):
            events.append(enqueue(worker, offset=offset, card=card)[0])
    settle(worker, events)
    stream = FeatureStream()
    for event in events:
        row = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        assert {key: row[key] for key in FEATURE_ORDER} == stream.transform(event)
    for event in events:
        envelope = worker.db.execute(
            "SELECT envelope FROM authorization_event_outbox WHERE event_id=%s",
            (event["event_id"],),
        ).fetchone()["envelope"]
        worker.redis.xadd(worker.stream, {"envelope": json.dumps(envelope)})
    settle(worker, events)
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


def test_parallel_out_of_order_stops_all_later_admission(parallel_harness):
    worker, _, _ = parallel_harness
    first = enqueue(worker, offset=10)[0]
    settle(worker, [first])
    bad = enqueue(worker, offset=9)[0]
    later = enqueue(worker, offset=11, card="b" * 64)[0]
    settle(worker, [bad])
    assert state(worker, bad)["status"] == "failed"
    assert state(worker, later) is None
    assert worker.db.execute(
        "SELECT blocked FROM scoring_worker_health WHERE run_id=%s", (worker.run_id,)
    ).fetchone()["blocked"]


def test_parallel_close_keeps_run_fence_until_sessions_finish(
    parallel_harness, monkeypatch
):
    worker, url, _ = parallel_harness
    entered, release = threading.Event(), threading.Event()
    original = worker.scorer.score

    def score(features):
        entered.set()
        assert release.wait(0.7)
        return original(features)

    monkeypatch.setattr(worker.scorer, "score", score)
    event = enqueue(worker)[0]
    worker.drain()
    assert entered.wait(0.5)
    closed = threading.Thread(target=worker.close)
    closed.start()
    try:
        with psycopg.connect(url, autocommit=True, row_factory=dict_row) as peer:
            assert not peer.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s,7)) AS held",
                (worker.run_id,),
            ).fetchone()["held"]
    finally:
        release.set()
        closed.join(timeout=2)
    assert not closed.is_alive()
    with psycopg.connect(url, row_factory=dict_row) as peer:
        assert (
            peer.execute(
                "SELECT status FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
                (worker.run_id, event["event_id"]),
            ).fetchone()["status"]
            == "scored"
        )


@pytest.mark.parametrize("parallel_harness", ["frozen"], indirect=True)
def test_parallel_frozen_model_exact_parity(parallel_harness):
    worker, _, _ = parallel_harness
    if not BUNDLE.exists():
        pytest.skip("Trusted frozen artifact unavailable")
    frozen = worker.scorer
    # Each session uses the same immutable model instance, not a new fit or ensemble.
    for session in list(worker.parallel.slots.queue):
        assert session.scorer is frozen
    events = [
        enqueue(worker, card=("a" if i % 2 else "b") * 64, offset=i)[0]
        for i in range(4)
    ]
    settle(worker, events)
    vectors = []
    rows = []
    for event in events:
        f = worker.db.execute(
            "SELECT * FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
            (worker.run_id, event["event_id"]),
        ).fetchone()
        vectors.append({key: f[key] for key in FEATURE_ORDER})
        rows.append(
            worker.db.execute(
                "SELECT probability,action FROM scoring_results WHERE run_id=%s AND event_id=%s",
                (worker.run_id, event["event_id"]),
            ).fetchone()
        )
    probabilities, actions = frozen.score(vectors)
    for row, p, a in zip(rows, probabilities, actions, strict=True):
        assert (
            row is not None
            and np.isclose(row["probability"], p, atol=1e-12, rtol=1e-12)
            and row["action"] == a
        )


def test_parallel_expiry_preserves_history_without_any_execution(
    parallel_harness, monkeypatch
):
    worker, _, _ = parallel_harness
    events = [enqueue(worker, card=card, offset=0)[0] for card in ("a" * 64, "b" * 64)]
    time.sleep(1.05)
    monkeypatch.setattr(
        worker.scorer, "score", lambda _: pytest.fail("Expired attempts must not infer")
    )
    settle(worker, events)
    assert all(state(worker, event)["status"] == "expired" for event in events)
    for table, expected in [
        ("scoring_history", 2),
        ("scoring_results", 0),
        ("simulated_executions", 0),
    ]:
        assert (
            worker.db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE run_id=%s", (worker.run_id,)
            ).fetchone()["n"]
            == expected
        )


def test_parallel_uncertain_finalization_reply_recovers_once(
    parallel_harness, monkeypatch
):
    worker, _, connect = parallel_harness
    connection = worker.parallel.connections[0]
    original = connection.execute

    def lose_reply(query, *args, **kwargs):
        result = original(query, *args, **kwargs)
        if "INSERT INTO scoring_results" in str(query):
            raise psycopg.OperationalError("Lost committed response")
        return result

    monkeypatch.setattr(connection, "execute", lose_reply)
    event = enqueue(worker)[0]
    with pytest.raises(psycopg.OperationalError, match="committed response"):
        until = time.monotonic() + 2
        while time.monotonic() < until:
            worker.cycle()
            time.sleep(0.005)
        pytest.fail("Expected uncertain commit injection")
    worker.close()
    resumed = ScoringWorker(
        connect(),
        worker.redis,
        FixtureScorer(),
        worker.run_id,
        worker.package_pin,
        mode="fixture",
        stream=worker.stream,
        concurrent_sessions=2,
        connection_factory=connect,
    )
    try:
        monkeypatch.setattr(
            resumed.scorer,
            "score",
            lambda _: pytest.fail("Durable completed work must not rescore"),
        )
        settle(resumed, [event])
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


def test_parallel_database_history_survives_stream_loss(parallel_harness):
    worker, _, _ = parallel_harness
    first = enqueue(worker, offset=0)[0]
    settle(worker, [first])
    worker.redis.delete(worker.stream)
    second = enqueue(worker, offset=1)[0]
    settle(worker, [second])
    vector = worker.db.execute(
        "SELECT prior_count_24h FROM scoring_feature_snapshots WHERE run_id=%s AND event_id=%s",
        (worker.run_id, second["event_id"]),
    ).fetchone()
    assert vector["prior_count_24h"] == 1
    assert state(worker, second)["status"] == "scored"
