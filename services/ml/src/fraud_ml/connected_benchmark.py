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
from .worker_benchmark import (
    call,
    durable_latency_report,
    keep_host_awake,
    producer_lag_seconds,
)


def latency_summary(values):
    return {
        "p50": float(np.percentile(values, 50)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
        "maximum": max(values, default=None),
        "over_1000": sum(value > 1000 for value in values),
    }


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


def guard_application_urls(pg_url, redis_url, docker_client=False):
    pg, rd = urlparse(pg_url), urlparse(redis_url)
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
    parser.add_argument("--tps", type=int, choices=(1, 5), required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--application", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--application-docker-client", action="store_true")
    parser.add_argument("--runtime-metadata", type=Path)
    args = parser.parse_args(argv)
    run_id = str(UUID(args.run_id))
    if args.application_docker_client and not args.application:
        raise ValueError("Docker application client requires explicit application mode")
    if (
        args.base
        != (
            (
                "http://sentinel-ai-api-1:8000"
                if args.application_docker_client
                else "http://127.0.0.1:18000"
            )
            if args.application
            else f"http://task6-fixture-api-{run_id}:8000"
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
        guard_application_urls(pg, rd, args.application_docker_client)
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as observers:
            start = time.perf_counter()
            for index in range(args.tps * args.seconds):
                time.sleep(max(0, start + index / args.tps - time.perf_counter()))
                try:
                    lags.append(producer_lag_seconds(start, index, args.tps))
                except RuntimeError:
                    failures.append({"kind": "producer_pause", "attempts_sent": index})
                    break
                event = generated_event(index, namespace)
                attempts.append(event)
                submitted = time.perf_counter()
                try:
                    status, response = call(
                        args.base + "/api/v1/authorization-events",
                        "POST",
                        event,
                        {"Idempotency-Key": str(uuid4())},
                    )
                    if status != 202 or response.get("outcome") != "accepted":
                        failures.append({"kind": "ingestion", "status": status})
                    else:
                        confirmed.append(event)
                        futures.append(
                            observers.submit(observe, event["event_id"], submitted)
                        )
                except (HTTPError, OSError) as error:
                    failures.append({"kind": "ingestion", "type": type(error).__name__})
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
            samples = [future.result() for future in futures]
        elapsed = time.perf_counter() - start
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
        published = db.execute(
            "SELECT count(*) AS n FROM authorization_event_outbox o JOIN scoring_jobs j USING(event_id) WHERE j.run_id=%s AND j.event_id=ANY(%s::uuid[]) AND o.status='published'",
            (run_id, event_ids),
        ).fetchone()["n"]
        target = args.tps * args.seconds
        report = {
            "run_id": run_id,
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
            / max(args.seconds, production_seconds),
            "producer_schedule_max_lag_ms": max(lags, default=0) * 1000,
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
            and 0 <= durable["minimum"] <= durable["maximum"] <= 1000,
            "reserved_test_accessed": False,
            "commit_deadline_verification": "postcommit-v1",
            "measurement_mode": "application" if args.application else "fixture",
            "identity_namespace": namespace,
            "data": "generated label-free fixtures; not a fraud-quality evaluation",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "model_threads": 1,
                "database": "actual sentinel persistent PostgreSQL 16.4"
                if args.application
                else "isolated tmpfs PostgreSQL 16.4",
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
