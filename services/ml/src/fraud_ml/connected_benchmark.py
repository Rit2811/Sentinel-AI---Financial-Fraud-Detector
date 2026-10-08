"""Generated HTTP workloads with isolated defaults and explicit application guards."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import subprocess
import time
import threading
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from uuid import UUID, uuid4
from urllib.parse import urlparse

import numpy as np
import psycopg
from psycopg.rows import dict_row
from threadpoolctl import threadpool_limits

from .features import FEATURE_ORDER, FeatureStream
from .serving import FrozenScorer, verify_manifest
from .worker import guard_fixture_urls
from .database import (
    database_target_sha256,
    database_connection,
    application_database_matches,
)
from .worker_benchmark import (
    call,
    durable_latency_report,
    keep_host_awake,
    producer_lag_seconds,
)


def latency_summary(values):
    return {
        "count": len(values),
        "minimum": min(values, default=None),
        "p50": float(np.percentile(values, 50)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
        "p99": float(np.percentile(values, 99)) if values else None,
        "maximum": max(values, default=None),
        "over_1000": sum(value > 1000 for value in values),
    }


def paced_due(start, index, tps, previous):
    """Missed slots extend the window instead of causing a catch-up burst."""
    return (
        max(start + index / tps, previous + 1 / tps) if previous is not None else start
    )


def clock_measurements(db):
    samples = []
    for _ in range(4):
        start_wall = time.time() * 1000
        tick = time.perf_counter()
        server = float(
            db.execute(
                "SELECT extract(epoch FROM clock_timestamp())*1000 AS wall_ms"
            ).fetchone()["wall_ms"]
        )
        rtt = (time.perf_counter() - tick) * 1000
        samples.append(
            {
                "rtt_ms": rtt,
                "midpoint_offset_ms": server - start_wall - rtt / 2,
                "uncertainty_ms": rtt / 2,
            }
        )
    return samples


def clocks_consistent(samples):
    # Timestamps are not corrected: reject a material offset beyond RTT uncertainty.
    return bool(samples) and all(
        abs(row["midpoint_offset_ms"]) <= row["uncertainty_ms"] + 25 for row in samples
    )


def generated_event(index, namespace=None):
    return {
        "schema_version": "2.0",
        "data_origin": "sparkov_replay",
        "event_id": str(uuid4()),
        "authorization_id": str(uuid4()),
        "occurred_at": (
            datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=index // 2)
        )
        .isoformat()
        .replace("+00:00", "Z"),
        "amount_minor": 1234 + (index % 100) * 37,
        "currency": "USD",
        "card_token": "card_"
        + (
            hashlib.sha256(f"{namespace}:{index % 20}".encode()).hexdigest()
            if namespace
            else f"{index % 20:064x}"
        ),
        "merchant_id": "merchant_" + "b" * 64,
        "merchant_category": "grocery_pos" if index % 3 else "fixture_unseen_category",
        "time_basis": "source_wall_clock_as_utc",
        "currency_basis": "simulation_assumption",
    }


def guard_application_urls(
    pg_url, redis_url, docker_client=False, external_target=None
):
    pg, rd = urlparse(pg_url), urlparse(redis_url)
    if external_target:
        database_connection({"POSTGRES_URL": pg_url})
        if (
            not docker_client
            or database_target_sha256(pg_url) != external_target
            or not (pg.hostname or "").endswith(".pooler.supabase.com")
            or pg.port != 5432
            or pg.path != "/postgres"
            or pg.fragment
            or rd.hostname not in ("redis", "sentinel-ai-redis-1")
            or rd.port != 6379
            or rd.path != "/0"
            or rd.query
            or rd.fragment
        ):
            raise ValueError("Application measurement requires the pinned cloud target")
        return
    if docker_client:
        target_matches = (
            pg.hostname in ("postgres", "sentinel-ai-postgres-1")
            and pg.port == 5432
            and rd.hostname in ("redis", "sentinel-ai-redis-1")
            and rd.port == 6379
        )
    else:
        target_matches = (
            pg.hostname == "127.0.0.1"
            and pg.port == 15432
            and rd.hostname == "127.0.0.1"
            and rd.port == 16379
        )
    if (
        not target_matches
        or pg.path != "/sentinel"
        or pg.query
        or pg.fragment
        or rd.path != "/0"
        or rd.query
        or rd.fragment
    ):
        raise ValueError(
            "Application measurement requires confirmed loopback sentinel target"
        )


@keep_host_awake()
@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument(
        "--tps",
        type=int,
        choices=(1, 2, 3, 4, 5),
        required=True,
        help="Rates 2-4 are diagnostic only; activation still requires 1 and 5 TPS",
    )
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--application", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--application-docker-client", action="store_true")
    parser.add_argument("--profile-database-waits", action="store_true")
    parser.add_argument("--runtime-metadata", type=Path)
    parser.add_argument("--diagnostic-deadline-ms", type=int, choices=(2000,))
    parser.add_argument("--external-database-target-sha256")
    parser.add_argument("--local-database-target-sha256")
    args = parser.parse_args(argv)
    if args.local_database_target_sha256 and (
        not args.application_docker_client
        or args.diagnostic_deadline_ms
        or args.external_database_target_sha256
    ):
        raise ValueError("Local target pin requires a one-second application client")
    run_id = str(UUID(args.run_id))
    deadline_ms = args.diagnostic_deadline_ms or 1000
    if args.application_docker_client and not args.application:
        raise ValueError("Docker application client requires explicit application mode")
    if args.external_database_target_sha256 and (
        not args.application_docker_client or args.diagnostic_deadline_ms
    ):
        raise ValueError("Cloud measurement requires a one-second application client")
    if (
        args.base
        != (
            (
                "http://sentinel-ai-api-1:8000"
                if args.application_docker_client
                else "http://127.0.0.1:18000"
            )
            if args.application
            else f"http://sentinel-load-api-{run_id}:8000"
        )
        or not 1 <= args.seconds <= 600
    ):
        raise ValueError(
            "Only the named isolated API and bounded workload are permitted"
        )
    if args.application:
        if args.output is None:
            raise ValueError("Application report path required")
        pg, rd = os.environ["POSTGRES_URL"], os.environ["REDIS_URL"]
        guard_application_urls(
            pg, rd, args.application_docker_client, args.external_database_target_sha256
        )
        if (
            args.local_database_target_sha256
            and database_target_sha256(pg) != args.local_database_target_sha256
        ):
            raise ValueError("Local target identity mismatch")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump({"status": "STARTING", "run_id": run_id}, stream)
    else:
        pg, rd = os.environ["TEST_DATABASE_URL"], os.environ["TEST_REDIS_URL"]
        guard_fixture_urls(pg, rd)
    verify_manifest(args.bundle, args.bundle_sha256)
    token = os.environ["RESULT_API_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    with psycopg.connect(pg, autocommit=True, row_factory=dict_row) as db:
        if args.local_database_target_sha256 and not application_database_matches(
            db, args.local_database_target_sha256
        ):
            raise ValueError("Connected local application differs from its target pin")
        db.execute("SET extra_float_digits=3")
        clock_before = clock_measurements(db)
        if not clocks_consistent(clock_before):
            if args.output:
                args.output.write_text(
                    json.dumps(
                        {
                            "status": "BLOCKED_CLOCK_SKEW",
                            "run_id": run_id,
                            "clock_before": clock_before,
                            "traffic_sent": 0,
                            "activation_authorized": False,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            raise ValueError("Clock skew prevents a valid workload measurement")
        run = db.execute(
            """SELECT s.*,h.ready,h.blocked FROM scoring_runs s
            JOIN scoring_worker_health h USING(run_id) WHERE run_id=%s
            AND h.heartbeat_at>clock_timestamp()-interval '5 seconds'""",
            (run_id,),
        ).fetchone()
        if (
            not run
            or run["mode"] != ("application" if args.application else "fixture")
            or run["bundle_sha256"] != args.bundle_sha256
            or not run["ready"]
            or run["blocked"]
            or run["durability_contract"] != "postcommit-v1"
            or (args.application and not run["gate_report_sha256"])
            or run["deadline_ms"] != deadline_ms
            or run["diagnostic_only"] != (args.diagnostic_deadline_ms is not None)
        ):
            raise ValueError("Matching ready fixture worker required")
        namespace = str(uuid4()) if args.application else None
        deployment = {}
        if args.application:
            metadata = json.loads(
                (
                    args.runtime_metadata
                    or (
                        Path(__file__).resolve().parents[2]
                        / "artifacts/runtime/application.json"
                    )
                ).read_text(encoding="utf-8")
            )
            if (
                metadata["run_id"] != run_id
                or metadata["bundle_sha256"] != args.bundle_sha256
            ):
                raise ValueError("Application runtime identity mismatch")
            for container, key in [
                ("sentinel-ai-scoring-worker-1", "worker_image_id"),
                ("sentinel-ai-api-1", "backend_image_id"),
                ("sentinel-ai-publisher-1", "backend_image_id"),
            ]:
                image_id = (
                    os.environ.get("VERIFIED_" + key.upper())
                    if args.application_docker_client
                    else subprocess.check_output(
                        ["docker", "inspect", container, "--format", "{{.Image}}"],
                        text=True,
                    ).strip()
                )
                if image_id != metadata[key]:
                    raise ValueError(
                        "Application deployment differs from approved workload images"
                    )
                deployment[key] = image_id
        failures, attempts, confirmed, futures, samples, queues, lags = (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        )

        wait_samples = Counter()
        wait_stop = threading.Event()
        wait_errors, blocked_samples, probe_durations = [], [], []
        wal_before = (
            db.execute(
                "SELECT wal_records,wal_bytes::text,wal_write,wal_sync,wal_write_time,wal_sync_time FROM pg_stat_wal"
            ).fetchone()
            if args.profile_database_waits
            else {}
        )

        def sample_database_waits():
            try:
                with psycopg.connect(
                    pg,
                    autocommit=True,
                    row_factory=dict_row,
                    connect_timeout=3,
                    options="-c statement_timeout=1000 -c lock_timeout=1000",
                ) as probe:
                    while not wait_stop.wait(0.05):
                        tick = time.perf_counter()
                        rows = probe.execute(
                            "SELECT coalesce(wait_event_type,'CPU') AS type, coalesce(wait_event,'Running') AS event,cardinality(pg_blocking_pids(pid)) AS blockers FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND state='active'"
                        ).fetchall()
                        probe_durations.append((time.perf_counter() - tick) * 1000)
                        for row in rows:
                            wait_samples[row["type"] + ":" + row["event"]] += 1
                        if any(row["blockers"] for row in rows):
                            blocked_samples.append(
                                {
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "blocked_backends": sum(
                                        bool(row["blockers"]) for row in rows
                                    ),
                                }
                            )
            except psycopg.Error as error:
                wait_errors.append(type(error).__name__)

        wait_thread = threading.Thread(target=sample_database_waits, daemon=True)
        if args.profile_database_waits:
            wait_thread.start()

        def observe(event_id, submitted):
            until = time.perf_counter() + 5
            while time.perf_counter() < until:
                try:
                    _, result = call(
                        f"{args.base}/api/v1/transactions/{event_id}/result",
                        headers=headers,
                    )
                    if result["status"] in ("scored", "expired", "failed"):
                        return {
                            "event_id": event_id,
                            "status": result["status"],
                            "observed_at": datetime.now(UTC).isoformat(),
                            "http_observed_ms": (time.perf_counter() - submitted)
                            * 1000,
                        }
                except (HTTPError, OSError):
                    pass
                time.sleep(0.1)
            return {
                "event_id": event_id,
                "status": "observation_timeout",
                "observed_at": datetime.now(UTC).isoformat(),
                "http_observed_ms": (time.perf_counter() - submitted) * 1000,
            }

        arrival_records = []
        card_locks = [threading.Lock() for _ in range(20)]
        send_lock = threading.Lock()
        last_sent = [None]

        def send_and_observe(index, event):
            with card_locks[index % 20]:
                with send_lock:
                    if last_sent[0] is not None:
                        time.sleep(
                            max(0, last_sent[0] + 1 / args.tps - time.perf_counter())
                        )
                    submitted = time.perf_counter()
                    last_sent[0] = submitted
                record = dict(
                    event_id=event["event_id"],
                    send_at_seconds=submitted - start,
                    send_at=datetime.now(UTC).isoformat(),
                )
                arrival_records.append(record)
                try:
                    status, response = call(
                        args.base + "/api/v1/authorization-events",
                        "POST",
                        event,
                        {"Idempotency-Key": str(uuid4())},
                    )
                    record["ingestion_response_ms"] = (
                        time.perf_counter() - submitted
                    ) * 1000
                    if status != 202 or response.get("outcome") != "accepted":
                        failures.append({"kind": "ingestion", "status": status})
                        return None
                    confirmed.append(event)
                except (HTTPError, OSError) as error:
                    failures.append({"kind": "ingestion", "type": type(error).__name__})
                    return None
            return observe(event["event_id"], submitted)

        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as observers:
            start = time.perf_counter()
            previous = None
            for index in range(args.tps * args.seconds):
                time.sleep(
                    max(
                        0,
                        paced_due(start, index, args.tps, previous)
                        - time.perf_counter(),
                    )
                )
                try:
                    lags.append(producer_lag_seconds(start, index, args.tps))
                except RuntimeError:
                    failures.append({"kind": "producer_pause", "attempts_sent": index})
                    break
                event = generated_event(index, namespace)
                attempts.append(event)
                previous = time.perf_counter()
                futures.append(observers.submit(send_and_observe, index, event))
                if index % (args.tps * 10) == 0:
                    q = db.execute(
                        """SELECT count(*) AS pending,coalesce(max(extract(epoch FROM clock_timestamp()-e.created_at)),0) AS oldest
                        FROM authorization_events e LEFT JOIN scoring_jobs j ON j.event_id=e.event_id AND j.run_id=%s
                        WHERE e.event_id=ANY(%s::uuid[]) AND (j.event_id IS NULL OR j.status NOT IN ('scored','expired','failed'))""",
                        (run_id, [event["event_id"] for event in attempts]),
                    ).fetchone()
                    queues.append(
                        {
                            "at_seconds": index / args.tps,
                            "pending": q["pending"],
                            "oldest_seconds": float(q["oldest"]),
                        }
                    )
            production_seconds = time.perf_counter() - start
            time.sleep(max(0, start + args.seconds - time.perf_counter()))
            samples = [
                result for future in futures if (result := future.result()) is not None
            ]
        elapsed = time.perf_counter() - start
        wait_stop.set()
        if args.profile_database_waits:
            wait_thread.join(timeout=5)
            if wait_thread.is_alive():
                wait_errors.append("probe_did_not_stop")
        clock_after = clock_measurements(db)
        if not clocks_consistent(clock_after):
            failures.append({"kind": "clock_inconsistency", "phase": "after_traffic"})
        wal_after = (
            db.execute(
                "SELECT wal_records,wal_bytes::text,wal_write,wal_sync,wal_write_time,wal_sync_time FROM pg_stat_wal"
            ).fetchone()
            if args.profile_database_waits
            else {}
        )
        # The reference model is needed only after traffic; avoid a second live RF.
        scorer = FrozenScorer(args.bundle, args.bundle_sha256)
        scorer.verify_references()
        canonical = db.execute(
            "SELECT sanitized_payload FROM authorization_events WHERE event_id=ANY(%s::uuid[]) ORDER BY created_at,event_id",
            ([event["event_id"] for event in attempts],),
        ).fetchall()
        offline, reference_rows = FeatureStream(), []
        sample_by_id = {sample["event_id"]: sample for sample in samples}
        for canonical_row in canonical:
            event = canonical_row["sanitized_payload"]
            features = offline.transform(event)
            row = db.execute(
                """SELECT f.*,r.probability,r.action,j.created_at AS accepted_at FROM scoring_feature_snapshots f
                JOIN scoring_jobs j USING(run_id,event_id) LEFT JOIN scoring_results r USING(run_id,event_id)
                WHERE run_id=%s AND event_id=%s""",
                (run_id, event["event_id"]),
            ).fetchone()
            if not row or {name: row[name] for name in FEATURE_ORDER} != features:
                failures.append(
                    {"kind": "feature_parity", "event_id": event["event_id"]}
                )
                continue
            sample = sample_by_id.get(event["event_id"])
            if sample:
                sample["acceptance_to_observed_ms"] = (
                    datetime.fromisoformat(sample["observed_at"]) - row["accepted_at"]
                ).total_seconds() * 1000
                if sample["acceptance_to_observed_ms"] < 0:
                    failures.append({"kind": "clock_inconsistency"})
            if row["probability"] is not None:
                reference_rows.append((features, row))
        parity = 0
        if reference_rows:
            probabilities, actions = scorer.score(
                [features for features, _ in reference_rows]
            )
            for (_, row), probability, action in zip(
                reference_rows, probabilities, actions, strict=True
            ):
                if (
                    not np.isclose(
                        row["probability"], probability, atol=1e-12, rtol=1e-12
                    )
                    or row["action"] != action
                ):
                    failures.append(
                        {"kind": "score_parity", "event_id": row["event_id"]}
                    )
                else:
                    parity += 1
        counts = {
            state: sum(sample["status"] == state for sample in samples)
            for state in ("scored", "expired", "failed", "observation_timeout")
        }
        event_ids = [event["event_id"] for event in attempts]
        arrivals = db.execute(
            """SELECT event_id::text,min(received_at) AS accepted_at
            FROM ingestion_attempts WHERE outcome='accepted' AND event_id=ANY(%s::uuid[])
            GROUP BY event_id ORDER BY accepted_at,event_id""",
            (event_ids,),
        ).fetchall()
        server_intervals = [
            (b["accepted_at"] - a["accepted_at"]).total_seconds() * 1000
            for a, b in zip(arrivals, arrivals[1:])
        ]
        send_times = sorted(r["send_at_seconds"] for r in arrival_records)
        send_intervals = [(b - a) * 1000 for a, b in zip(send_times, send_times[1:])]
        durable = durable_latency_report(db, run_id, event_ids)
        stored = {
            row["status"]: row["n"]
            for row in db.execute(
                "SELECT status,count(*) AS n FROM scoring_jobs WHERE run_id=%s AND event_id=ANY(%s::uuid[]) GROUP BY status",
                (run_id, event_ids),
            ).fetchall()
        }
        executions = db.execute(
            """SELECT count(*) AS total,count(*) FILTER(WHERE j.status<>'scored' OR x.executed_at>j.deadline_at) AS invalid_or_late
            FROM simulated_executions x JOIN scoring_jobs j USING(run_id,event_id) WHERE j.run_id=%s AND j.event_id=ANY(%s::uuid[])""",
            (run_id, event_ids),
        ).fetchone()
        event_timings = [
            dict(row)
            for row in db.execute(
                """SELECT j.event_id::text,j.status,extract(epoch FROM (f.created_at-j.created_at))*1000 AS snapshot_witness_ms,
              extract(epoch FROM (o.published_at-j.created_at))*1000 AS publication_precommit_witness_ms,
              extract(epoch FROM (j.updated_at-j.created_at))*1000 AS terminal_precommit_witness_ms,
              extract(epoch FROM (p.inference_started_at-j.created_at))*1000 AS inference_start_ms,
              p.inference_ms,extract(epoch FROM (j.deadline_at-j.created_at))*1000 AS deadline_ms
            FROM scoring_jobs j JOIN scoring_feature_snapshots f USING(run_id,event_id)
            JOIN authorization_event_outbox o USING(event_id) LEFT JOIN scoring_predictions p USING(run_id,event_id)
            WHERE j.run_id=%s AND j.event_id=ANY(%s::uuid[])""",
                (run_id, event_ids),
            ).fetchall()
        ]
        event_timings = [
            {k: float(v) if hasattr(v, "as_tuple") else v for k, v in row.items()}
            for row in event_timings
        ]
        published = db.execute(
            "SELECT count(*) AS n FROM authorization_event_outbox o JOIN scoring_jobs j USING(event_id) WHERE j.run_id=%s AND j.event_id=ANY(%s::uuid[]) AND o.status='published'",
            (run_id, event_ids),
        ).fetchone()["n"]
        target = args.tps * args.seconds
        report = {
            "run_id": run_id,
            "clock_before": clock_before,
            "clock_after": clock_after,
            "clock_checks_passed": clocks_consistent(clock_before)
            and clocks_consistent(clock_after),
            "bundle_sha256": args.bundle_sha256,
            **deployment,
            "offline_reference_model_loaded_after_traffic": True,
            "tps": args.tps,
            "requested_seconds": args.seconds,
            "elapsed_seconds": elapsed,
            "production_seconds": production_seconds,
            "attempted": target,
            "accepted": len(canonical),
            "client_confirmed_accepted": len(confirmed),
            "accepted_without_confirmed_response": len(canonical) - len(confirmed),
            "offered_transactions_per_second": len(attempts)
            / max(
                args.seconds,
                production_seconds,
                (send_times[-1] + 1 / args.tps) if send_times else args.seconds,
            ),
            "producer_schedule_max_lag_ms": max(lags, default=0) * 1000,
            "pacing": {
                "policy": "Independent HTTP sends; no catch-up slots; per-card send lock",
                "expected_interval_ms": 1000 / args.tps,
                "send_intervals_ms": latency_summary(send_intervals),
                "server_acceptance_intervals_ms": latency_summary(server_intervals),
                "send_intervals_below_half_target": sum(
                    x < 500 / args.tps for x in send_intervals
                ),
                "server_intervals_below_half_target": sum(
                    x < 500 / args.tps for x in server_intervals
                ),
                "ingestion_response_ms": latency_summary(
                    [
                        r["ingestion_response_ms"]
                        for r in arrival_records
                        if "ingestion_response_ms" in r
                    ]
                ),
            },
            "arrival_records": arrival_records,
            "server_acceptance_records": [
                {"event_id": r["event_id"], "accepted_at": r["accepted_at"].isoformat()}
                for r in arrivals
            ],
            "terminal_counts": counts,
            "durable_status_counts": stored,
            "execution_checks": executions,
            "published_outbox": published,
            "durable_decision_latency_ms": durable,
            "parity_scored_rows": parity,
            "scored_per_second": counts["scored"] / elapsed,
            "http_observed_latency_ms": latency_summary(
                [
                    sample["http_observed_ms"]
                    for sample in samples
                    if sample["status"] == "scored"
                ]
            ),
            "server_acceptance_to_http_visibility_ms": latency_summary(
                [
                    sample["acceptance_to_observed_ms"]
                    for sample in samples
                    if sample["status"] == "scored"
                    and "acceptance_to_observed_ms" in sample
                ]
            ),
            "queue_samples": queues,
            "database_active_wait_samples": dict(wait_samples),
            "database_probe_errors": wait_errors,
            "database_blocked_samples": blocked_samples,
            "database_probe_query_ms": latency_summary(probe_durations),
            "database_wal_delta": {
                key: float(wal_after[key]) - float(wal_before[key])
                for key in wal_before
            },
            "database_io_timing_enabled": db.execute("SHOW track_io_timing").fetchone()[
                "track_io_timing"
            ]
            if args.profile_database_waits
            else None,
            "database_wal_io_timing_enabled": db.execute(
                "SHOW track_wal_io_timing"
            ).fetchone()["track_wal_io_timing"]
            if args.profile_database_waits
            else None,
            "event_database_timings": event_timings,
            "deadline_ms": deadline_ms,
            "diagnostic_only": args.diagnostic_deadline_ms is not None,
            "queue_maximum": max((q["pending"] for q in queues), default=0),
            "failures": failures,
            "samples": samples,
            "all_attempts_timely_scored": counts["scored"] == target
            and not failures
            and parity == target
            and stored == {"scored": target}
            and executions == {"total": target, "invalid_or_late": 0}
            and durable["count"] == target
            and durable["minimum"] is not None
            and 0 <= durable["minimum"] <= durable["maximum"] <= deadline_ms
            and not wait_errors,
            "reserved_test_accessed": False,
            "commit_deadline_verification": "postcommit-v1",
            "measurement_mode": "application" if args.application else "fixture",
            "identity_namespace": namespace,
            "data": "generated label-free fixtures; not a fraud-quality evaluation",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "model_threads": 1,
                "database": (
                    "actual Supabase Session pooler PostgreSQL "
                    + db.execute("SHOW server_version").fetchone()["server_version"]
                    if args.external_database_target_sha256
                    else (
                        "actual sentinel persistent PostgreSQL "
                        + db.execute("SHOW server_version").fetchone()["server_version"]
                        if args.application
                        else "isolated tmpfs PostgreSQL 16.4"
                    )
                ),
                "redis_server": "actual application Redis 7.2.5 AOF"
                if args.application
                else "isolated Redis 7.2.5",
                "publisher_poll_ms": 50,
                "consumer_block_ms": 50,
                "result_poll_ms": 100,
                "per_cycle_diagnostics": False,
                "controller_topology": (
                    "actual application Docker network"
                    if args.application_docker_client
                    else "Windows localhost HTTP"
                )
                if args.application
                else "isolated Docker test network",
                "worker_topology": "application Docker network"
                if args.application
                else "isolated Docker test network",
                "backend_topology": "application Docker network"
                if args.application
                else "isolated Docker test network",
            },
        }
        (args.output if args.application else Path("/output/report.json")).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        if args.application:
            print(
                json.dumps(
                    {
                        "report": str(args.output),
                        "counts": counts,
                        "durable_latency": durable,
                        "failures": len(failures),
                        "timely": report["all_attempts_timely_scored"],
                    }
                )
            )


if __name__ == "__main__":
    main()
