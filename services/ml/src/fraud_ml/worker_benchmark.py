"""Isolated label-free HTTP/outbox/Redis/frozen-RF benchmark; never final-test data."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import json
import os
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import numpy as np
import psycopg
from psycopg.rows import dict_row
import redis
from threadpoolctl import threadpool_limits

from .features import FEATURE_ORDER, FeatureStream
from .ensemble.reporting import code_record
from .serving import FrozenScorer
from .worker import guard_fixture_urls


def call(url, method="GET", body=None, headers=None):
    request = Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return response.status, json.load(response)


@contextmanager
def keep_host_awake():
    if sys.platform != "win32":
        yield
        return
    set_state = ctypes.WinDLL("kernel32", use_last_error=True).SetThreadExecutionState
    set_state.argtypes = [ctypes.c_uint]
    set_state.restype = ctypes.c_uint
    previous = set_state(0x80000001)
    if not previous:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        set_state(previous)


def producer_lag_seconds(start, index, tps):
    lag = max(0, time.perf_counter() - start - index / tps)
    if lag > 5:
        raise RuntimeError("Workload producer paused for more than five seconds")
    return lag


def durable_latency_report(db, run_id, event_ids=None):
    values = [
        float(row["milliseconds"])
        for row in db.execute(
            """SELECT extract(epoch FROM (greatest(r.decision_at,x.executed_at)-j.created_at))*1000 AS milliseconds
            FROM scoring_jobs j JOIN scoring_results r USING(run_id,event_id)
            JOIN simulated_executions x USING(run_id,event_id)
            JOIN scoring_predictions p USING(run_id,event_id)
            JOIN scoring_runs s USING(run_id)
            WHERE j.run_id=%s AND s.durability_contract='postcommit-v1'
              AND (%s::uuid[] IS NULL OR j.event_id=ANY(%s::uuid[]))""",
            (run_id, event_ids, event_ids),
        ).fetchall()
    ]
    return {
        "p50": float(np.percentile(values, 50)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
        "p99": float(np.percentile(values, 99)) if values else None,
        "maximum": max(values, default=None),
        "minimum": min(values, default=None),
        "over_1000": sum(t > 1000 for t in values),
        "count": len(values),
        "basis": "Postcommit-v1: acceptance to server witness of earlier synchronously committed prediction; includes later pre-COMMIT execution timestamp",
    }


def profile_summary(path):
    stages = {}
    queue = []
    records = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        batch = (
            row.get("records", [])
            if row.get("kind") == "stage_profile_batch"
            else [row]
        )
        for row in batch:
            if row.get("kind") != "stage_timing":
                continue
            records += 1
            stages.setdefault(row["stage"], []).append(row["elapsed_ms"])
            if "process_cpu_ms" in row:
                stages.setdefault(row["stage"] + "_process_cpu", []).append(
                    row["process_cpu_ms"]
                )
            if "queue_ms" in row:
                queue.append(row["queue_ms"])
    if queue:
        stages["accepted_to_assignment_queue"] = queue
    return dict(
        records=records,
        stages={
            name: dict(
                count=len(values),
                p50=float(np.percentile(values, 50)),
                p95=float(np.percentile(values, 95)),
                maximum=max(values),
            )
            for name, values in stages.items()
        },
        basis="Opt-in monotonic stage timings include transaction-context commit acknowledgement; non-blocking diagnostic logs can drop records",
    )


@keep_host_awake()
@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--tps", type=int, choices=(1, 5), required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument(
        "--worker-image",
        help="Trusted local worker image; use the isolated test network",
    )
    parser.add_argument(
        "--backend-image",
        help="Run API and publisher on the same isolated Docker network",
    )
    parser.add_argument("--docker-controller", action="store_true")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args(argv)
    if args.docker_controller and not (args.worker_image and args.backend_image):
        parser.error("Docker controller requires both isolated service images")
    image_id = None
    if args.worker_image:
        image_id = subprocess.check_output(
            ["docker", "image", "inspect", args.worker_image, "--format", "{{.Id}}"],
            text=True,
        ).strip()
    backend_image_id = None
    docker_resources = None
    if args.backend_image:
        backend_image_id = subprocess.check_output(
            ["docker", "image", "inspect", args.backend_image, "--format", "{{.Id}}"],
            text=True,
        ).strip()
    if args.worker_image or args.backend_image:
        docker_resources = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "info",
                    "--format",
                    '{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}',
                ],
                text=True,
            )
        )
    provenance = code_record()
    if not 1 <= args.seconds <= 600:
        parser.error("Benchmark duration must be 1..600 seconds")
    pg_url, redis_url = os.environ["TEST_DATABASE_URL"], os.environ["TEST_REDIS_URL"]
    guard_fixture_urls(pg_url, redis_url)
    run_id, stream, token = (
        str(uuid4()),
        f"task6-test:{uuid4()}",
        uuid4().hex + uuid4().hex,
    )
    output = Path("reports/task6-worker") / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    output.mkdir(parents=True, exist_ok=False)
    db = psycopg.connect(pg_url, autocommit=True, row_factory=dict_row)
    backend = Path(__file__).resolve().parents[4] / "backend"
    env = {
        **os.environ,
        "POSTGRES_URL": pg_url,
        "REDIS_URL": redis_url,
        "STREAM_NAME": stream,
        "SCORING_STREAM": stream,
        "SCORING_DIAGNOSTICS": "0",
        "SCORING_PROFILE": "1" if args.profile else "0",
        "RESULT_API_TOKEN": token,
        "SCORING_RUN_ID": run_id,
        "STREAM_POLL_MS": "50",
    }
    api_code = "import {createApp} from './src/app.js';const s=createApp({log:{info(){},error(){}}}).listen(0,'127.0.0.1',()=>console.log(s.address().port));"
    backend_containers = []
    api = publisher = None
    container_port = None
    if args.backend_image:

        def start_backend(name, command, published_port=False):
            launch = [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
                "--log-opt",
                "mode=non-blocking",
                "--log-opt",
                "max-buffer-size=1m",
                "--log-opt",
                "mode=non-blocking",
                "--log-opt",
                "max-buffer-size=1m",
                "--network",
                "sentinel-task4-test_default",
            ]
            if published_port:
                launch.extend(["-p", "127.0.0.1::8000"])
            for name_env, value in {
                "POSTGRES_URL": "postgresql://sentinel:sentinel_test_only@sentinel-task4-test-postgres-1:5432/sentinel_task4_test",
                "REDIS_URL": "redis://:sentinel_test_only@sentinel-task4-test-redis-1:6379/0",
                "STREAM_NAME": stream,
                "STREAM_POLL_MS": "50",
                "RESULT_API_TOKEN": token,
                "SCORING_RUN_ID": run_id,
            }.items():
                launch.extend(["-e", f"{name_env}={value}"])
            subprocess.run(
                launch + [backend_image_id, *command],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            backend_containers.append(name)

        try:
            api_name = f"task6-fixture-api-{run_id}"
            start_backend(api_name, ["node", "src/server.js"], True)
            container_port = int(
                subprocess.check_output(
                    ["docker", "port", api_name, "8000/tcp"], text=True
                )
                .strip()
                .rsplit(":", 1)[1]
            )
            start_backend(
                f"task6-fixture-publisher-{run_id}", ["node", "src/stream/publisher.js"]
            )
        except Exception:
            for name in backend_containers:
                subprocess.run(
                    ["docker", "stop", "--time", "3", name],
                    capture_output=True,
                    timeout=30,
                )
            db.close()
            raise
    else:
        api = subprocess.Popen(
            ["node", "--input-type=module", "-e", api_code],
            cwd=backend,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        publisher = subprocess.Popen(
            ["node", "src/stream/publisher.js"],
            cwd=backend,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    failures, samples, queue_samples = [], [], []
    worker_log = (output / "worker.log").open("w", encoding="utf-8")
    container_name = f"task6-fixture-worker-{run_id}"
    worker_command = [
        sys.executable,
        "-m",
        "fraud_ml.worker",
        "--fixture",
        "--bundle",
        str(args.bundle.resolve()),
        "--bundle-sha256",
        args.bundle_sha256,
        "--run-id",
        run_id,
    ]
    if args.worker_image:
        worker_command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--log-opt",
            "mode=non-blocking",
            "--log-opt",
            "max-buffer-size=1m",
            "--log-opt",
            "mode=non-blocking",
            "--log-opt",
            "max-buffer-size=1m",
            "--network",
            "sentinel-task4-test_default",
            "--mount",
            f"type=bind,source={args.bundle.resolve()},target=/model,readonly",
            "-e",
            "POSTGRES_URL=postgresql://sentinel:sentinel_test_only@sentinel-task4-test-postgres-1:5432/sentinel_task4_test",
            "-e",
            "REDIS_URL=redis://:sentinel_test_only@sentinel-task4-test-redis-1:6379/0",
            "-e",
            f"SCORING_STREAM={stream}",
            "-e",
            "SCORING_DIAGNOSTICS=0",
            "-e",
            f"SCORING_PROFILE={int(args.profile)}",
            image_id,
            "--fixture",
            "--bundle",
            "/model",
            "--bundle-sha256",
            args.bundle_sha256,
            "--run-id",
            run_id,
        ]
    worker = subprocess.Popen(
        worker_command,
        env=env,
        stdout=worker_log,
        stderr=worker_log,
    )

    def stop_worker():
        if worker.poll() is None:
            if args.worker_image:
                subprocess.run(
                    ["docker", "stop", "--time", "3", container_name],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            else:
                worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if not args.worker_image:
                    raise
                # The container is stopped; a stuck attached Docker client is not work.
                worker.terminate()
                worker.wait(timeout=10)

    future_results = []
    events = []
    attempted_events = []
    schedule_lags = []
    controller_name = None
    try:
        port = container_port if container_port else int(api.stdout.readline().strip())
        base = f"http://127.0.0.1:{port}"
        startup_deadline = time.monotonic() + 120
        while True:
            try:
                call(base + "/health")
                break
            except (HTTPError, OSError):
                if time.monotonic() >= startup_deadline:
                    raise RuntimeError("Fixture API failed startup")
                time.sleep(0.1)
        while True:
            ready = db.execute(
                """SELECT s.started_at FROM scoring_runs s JOIN scoring_worker_health h USING(run_id)
                WHERE s.run_id=%s AND h.ready AND NOT h.blocked
                AND h.heartbeat_at>clock_timestamp()-interval '5 seconds'""",
                (run_id,),
            ).fetchone()
            if ready:
                started_at = ready["started_at"]
                break
            if worker.poll() is not None or time.monotonic() >= startup_deadline:
                raise RuntimeError(
                    "Fixture worker failed startup; inspect private worker.log"
                )
            time.sleep(0.1)

        if args.docker_controller:
            controller_name = f"task6-fixture-controller-{run_id}"
            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                controller_name,
                "--network",
                "sentinel-task4-test_default",
                "--entrypoint",
                "/app/.venv/bin/python",
                "--mount",
                f"type=bind,source={args.bundle.resolve()},target=/model,readonly",
                "--mount",
                f"type=bind,source={output.resolve()},target=/output",
                "-e",
                "TEST_DATABASE_URL=postgresql://sentinel:sentinel_test_only@sentinel-task4-test-postgres-1:5432/sentinel_task4_test",
                "-e",
                "TEST_REDIS_URL=redis://:sentinel_test_only@sentinel-task4-test-redis-1:6379/0",
                "-e",
                f"RESULT_API_TOKEN={token}",
                image_id,
                "-m",
                "fraud_ml.connected_benchmark",
                "--bundle",
                "/model",
                "--bundle-sha256",
                args.bundle_sha256,
                "--run-id",
                run_id,
                "--base",
                f"http://{api_name}:8000",
                "--tps",
                str(args.tps),
                "--seconds",
                str(args.seconds),
            ]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=args.seconds + 240
            )
            (output / "controller.log").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode:
                raise RuntimeError(
                    "Isolated controller failed; inspect private controller.log"
                )
            stop_worker()
            worker_log.close()
            report_path = output / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for line in (
                (output / "worker.log").read_text(encoding="utf-8").splitlines()
            ):
                if line.startswith('{"status": "unavailable"'):
                    report["failures"].append({"kind": "worker_dependency_unavailable"})
            report["environment"]["container_logging"] = (
                "non-blocking; 1 MiB diagnostic buffer; durable database audit"
            )
            report.update(
                {
                    "code": provenance,
                    "worker_image_id": image_id,
                    "backend_image_id": backend_image_id,
                    "status": "ISOLATED_FIXTURE_BENCHMARK_NOT_ACTIVATION",
                }
            )
            report["environment"]["docker_resources"] = docker_resources
            report["environment"]["container_logging"] = (
                "non-blocking; 1 MiB diagnostic buffer; durable database audit"
            )
            report["stage_profile"] = profile_summary(output / "worker.log")
            report["environment"]["stage_profiling"] = args.profile
            report["commit_deadline_verification"] = "postcommit-v1"
            report["all_attempts_timely_scored"] &= not report["failures"]
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "report": str(report_path),
                        "counts": report["terminal_counts"],
                        "durable_latency": report["durable_decision_latency_ms"],
                        "failures": len(report["failures"]),
                        "timely": report["all_attempts_timely_scored"],
                    }
                ),
                flush=True,
            )
            return

        def observe(event_id, submitted):
            deadline = time.perf_counter() + 5
            while time.perf_counter() < deadline:
                try:
                    _, result = call(
                        f"{base}/api/v1/transactions/{event_id}/result",
                        headers={"Authorization": f"Bearer {token}"},
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
                    lag = producer_lag_seconds(start, index, args.tps)
                except RuntimeError:
                    failures.append({"kind": "producer_pause", "attempts_sent": index})
                    break
                event = {
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
                    "card_token": "card_" + f"{index % 20:064x}",
                    "merchant_id": "merchant_" + "b" * 64,
                    "merchant_category": "grocery_pos"
                    if index % 3
                    else "fixture_unseen_category",
                    "time_basis": "source_wall_clock_as_utc",
                    "currency_basis": "simulation_assumption",
                }
                submitted = time.perf_counter()
                attempted_events.append(event)
                schedule_lags.append(lag)
                try:
                    status, response = call(
                        base + "/api/v1/authorization-events",
                        "POST",
                        event,
                        {"Idempotency-Key": str(uuid4())},
                    )
                    if status != 202 or response.get("outcome") != "accepted":
                        failures.append({"kind": "ingestion", "status": status})
                    else:
                        events.append(event)
                        future_results.append(
                            observers.submit(observe, event["event_id"], submitted)
                        )
                except (HTTPError, OSError) as error:
                    failures.append({"kind": "ingestion", "type": type(error).__name__})
                if index % (args.tps * 10) == 0:
                    with db.cursor() as monitor:
                        q = monitor.execute(
                            """SELECT count(*) AS pending,coalesce(max(extract(epoch FROM clock_timestamp()-e.created_at)),0) AS oldest
                          FROM authorization_events e LEFT JOIN scoring_jobs j ON j.event_id=e.event_id AND j.run_id=%s
                          WHERE e.created_at >= %s AND (j.event_id IS NULL OR j.status NOT IN ('scored','expired','failed'))""",
                            (run_id, started_at),
                        ).fetchone()
                        queue_samples.append(
                            {
                                "at_seconds": index / args.tps,
                                "pending": q["pending"],
                                "oldest_seconds": float(q["oldest"]),
                            }
                        )
            production_seconds = time.perf_counter() - start
            time.sleep(max(0, start + args.seconds - time.perf_counter()))
            samples = [future.result() for future in future_results]
        elapsed = time.perf_counter() - start
        if worker.poll() is not None:
            failures.append({"kind": "worker_exit", "returncode": worker.returncode})
        else:
            stop_worker()
        worker_log.close()
        for line in (output / "worker.log").read_text(encoding="utf-8").splitlines():
            if line.startswith('{"status": "unavailable"'):
                failures.append({"kind": "worker_dependency_unavailable"})
        scorer = FrozenScorer(args.bundle, args.bundle_sha256)
        scorer.verify_references()
        offline = FeatureStream()
        parity = 0
        reference_rows = []
        sample_by_id = {sample["event_id"]: sample for sample in samples}
        canonical = db.execute(
            """SELECT sanitized_payload FROM authorization_events
            WHERE event_id=ANY(%s::uuid[]) ORDER BY created_at,event_id""",
            ([event["event_id"] for event in attempted_events],),
        ).fetchall()
        # A lost HTTP response cannot remove a committed attempt from feature history.
        accepted_events = [row["sanitized_payload"] for row in canonical]
        for event in accepted_events:
            try:
                features = offline.transform(event)
            except ValueError:
                failures.append(
                    {"kind": "canonical_history_order", "event_id": event["event_id"]}
                )
                continue
            row = db.execute(
                """SELECT f.*,r.probability,r.action,j.created_at AS accepted_at FROM scoring_feature_snapshots f
              JOIN scoring_jobs j USING(run_id,event_id)
              LEFT JOIN scoring_results r USING(run_id,event_id) WHERE run_id=%s AND event_id=%s""",
                (run_id, event["event_id"]),
            ).fetchone()
            if not row or {k: row[k] for k in FEATURE_ORDER} != features:
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
                reference_rows.append((event["event_id"], features, row))
        if reference_rows:
            probabilities, actions = scorer.score([f for _, f, _ in reference_rows])
            for index, (event_id, _, row) in enumerate(reference_rows):
                if (
                    not np.isclose(
                        row["probability"], probabilities[index], atol=1e-12, rtol=1e-12
                    )
                    or row["action"] != actions[index]
                ):
                    failures.append({"kind": "score_parity", "event_id": event_id})
                else:
                    parity += 1
        counts = {
            name: sum(s["status"] == name for s in samples)
            for name in ("scored", "expired", "failed", "observation_timeout")
        }
        latency = [s["http_observed_ms"] for s in samples if s["status"] == "scored"]
        acceptance_latency = [
            s["acceptance_to_observed_ms"]
            for s in samples
            if s["status"] == "scored" and "acceptance_to_observed_ms" in s
        ]
        published = db.execute(
            "SELECT count(*) AS n FROM authorization_event_outbox o JOIN scoring_jobs j USING(event_id) WHERE j.run_id=%s AND o.status='published'",
            (run_id,),
        ).fetchone()["n"]
        durable_latency = durable_latency_report(db, run_id)
        report = {
            "durable_decision_latency_ms": durable_latency,
            "execution_checks": db.execute(
                """SELECT count(*) AS total,
                  count(*) FILTER (WHERE j.status<>'scored' OR x.executed_at>j.deadline_at) AS invalid_or_late
                FROM simulated_executions x JOIN scoring_jobs j USING(run_id,event_id)
                WHERE j.run_id=%s""",
                (run_id,),
            ).fetchone(),
            "durable_status_counts": {
                r["status"]: r["n"]
                for r in db.execute(
                    "SELECT status,count(*) AS n FROM scoring_jobs WHERE run_id=%s GROUP BY status",
                    (run_id,),
                ).fetchall()
            },
            "code": provenance,
            "worker_image_id": image_id,
            "backend_image_id": backend_image_id,
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "logical_cpus": os.cpu_count(),
                "model_threads": 1,
                "docker_resources": docker_resources,
                "psycopg": psycopg.__version__,
                "redis": redis.__version__,
                "database": "isolated tmpfs PostgreSQL 16.4",
                "redis_server": "isolated Redis 7.2.5",
                "publisher_poll_ms": 50,
                "consumer_block_ms": 50,
                "result_poll_ms": 100,
                "per_cycle_diagnostics": False,
                "worker_topology": "isolated Docker test network"
                if args.worker_image
                else "independent host Python CLI process",
                "monitor_connection": "persistent; no per-sample connection setup",
                "backend_topology": "isolated Docker test network"
                if args.backend_image
                else "Windows host Node processes",
            },
            "status": "ISOLATED_FIXTURE_BENCHMARK_NOT_ACTIVATION",
            "run_id": run_id,
            "bundle_sha256": args.bundle_sha256,
            "tps": args.tps,
            "requested_seconds": args.seconds,
            "elapsed_seconds": elapsed,
            "attempted": args.tps * args.seconds,
            "accepted": len(accepted_events),
            "client_confirmed_accepted": len(events),
            "accepted_without_confirmed_response": len(accepted_events) - len(events),
            "production_seconds": production_seconds,
            "offered_transactions_per_second": len(attempted_events)
            / max(args.seconds, production_seconds),
            "producer_schedule_max_lag_ms": max(schedule_lags, default=0) * 1000,
            "terminal_counts": counts,
            "scored_per_second": counts["scored"] / elapsed,
            "published_outbox": published,
            "http_observed_latency_ms": {
                "p50": float(np.percentile(latency, 50)) if latency else None,
                "p95": float(np.percentile(latency, 95)) if latency else None,
                "maximum": max(latency, default=None),
                "over_1000": sum(t > 1000 for t in latency),
            },
            "server_acceptance_to_http_visibility_ms": {
                "p50": float(np.percentile(acceptance_latency, 50))
                if acceptance_latency
                else None,
                "p95": float(np.percentile(acceptance_latency, 95))
                if acceptance_latency
                else None,
                "maximum": max(acceptance_latency, default=None),
                "over_1000": sum(t > 1000 for t in acceptance_latency),
                "basis": "Stored server received_at to client observation of committed result; includes polling and response delay; clocks are UTC and topology is recorded",
            },
            "latency_basis": "HTTP submission until an authenticated GET observes durable terminal storage; includes polling overhead",
            "queue_samples": queue_samples,
            "queue_maximum": max((q["pending"] for q in queue_samples), default=0),
            "parity_scored_rows": parity,
            "failures": failures,
            "samples": samples,
            "all_attempts_timely_scored": counts["scored"] == args.tps * args.seconds
            and not failures
            and durable_latency["count"] == counts["scored"]
            and durable_latency["minimum"] is not None
            and 0 <= durable_latency["minimum"] <= durable_latency["maximum"] <= 1000,
            "reserved_test_accessed": False,
            "data": "generated label-free fixtures; not a fraud-quality evaluation",
        }
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "report": str(output / "report.json"),
                    "counts": counts,
                    "latency": report["http_observed_latency_ms"],
                    "acceptance_latency": report[
                        "server_acceptance_to_http_visibility_ms"
                    ],
                    "failures": len(failures),
                }
            ),
            flush=True,
        )
    finally:
        if controller_name:
            subprocess.run(
                ["docker", "rm", "--force", controller_name],
                capture_output=True,
                timeout=30,
            )
        try:
            stop_worker()
        finally:
            for child in (publisher, api):
                if child is not None and child.poll() is None:
                    child.terminate()
                    child.wait(timeout=10)
            for name in backend_containers:
                logs = subprocess.run(
                    ["docker", "logs", name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (output / f"{name}.log").write_text(
                    logs.stdout + logs.stderr, encoding="utf-8"
                )
                logs = subprocess.run(
                    ["docker", "logs", name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (output / f"{name}.log").write_text(
                    logs.stdout + logs.stderr, encoding="utf-8"
                )
                subprocess.run(
                    ["docker", "stop", "--time", "3", name],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            worker_log.close()
            db.close()


if __name__ == "__main__":
    main()
