"""Durable chronological replay scoring; application activation is fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import redis
from threadpoolctl import threadpool_limits

from .features import (
    FEATURE_ORDER,
    FEATURE_VERSION,
    features_from_prior,
    validate_event,
)
from .serving import FrozenScorer, sha256
from .database import application_database_matches

TERMINAL = {"scored", "expired", "failed"}


def dependency_failure(error):
    return {
        "status": "unavailable",
        "code": "dependency_unavailable",
        "error_type": type(error).__name__,
        "sqlstate": getattr(error, "sqlstate", None),
    }


class InferenceFailure(Exception):
    """Retry an uncommitted first assignment through the existing failure path."""


def warm_scorer(scorer):
    reference = json.loads(
        (scorer.root / "references.json").read_text(encoding="utf-8")
    )["score_cases"][0]["features"]
    # Initialize single-event and unknown-category paths without any history,
    # predictions, actions or labels. Frozen model/calibration are not mutated.
    for features in (
        reference,
        dict(reference, merchant_category="__unseen_serving_category__"),
        reference,
    ):
        scorer.score([dict(features)])


ENVELOPE_FIELDS = {
    "event_id",
    "authorization_id",
    "correlation_id",
    "schema_version",
    "data_origin",
    "occurred_at",
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def verify_activation(report_path, report_pin, package_pin, policy):
    if not report_path or not report_pin or sha256(report_path) != report_pin:
        raise ValueError("Passing final-test report and external checksum required")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if (
        report.get("status") != "PASS"
        or report.get("evaluation_kind") != "reserved_test"
        or report.get("bundle_sha256") != package_pin
        or report.get("policy_sha256") != digest(policy)
        or report.get("test_source_sha256")
        != "12d553ab19440c752d2531ee1af44bb64f12cc3d3839f1649f19e81c230545f0"
        or report.get("authorization", {}).get("bundle_sha256") != package_pin
        or not report.get("authorization", {}).get("owner_authorized_at")
    ):
        raise ValueError("Final-test report does not authorize this package")
    counts = report["counts"]
    fraud, legitimate = counts["fraud"], counts["legitimate"]
    if fraud != 2145 or fraud + legitimate != 555719:
        raise ValueError("Final-test coverage mismatch")
    for key in (
        "fraud_pass",
        "fraud_review",
        "fraud_block",
        "legitimate_pass",
        "legitimate_review",
        "legitimate_block",
    ):
        if type(counts.get(key)) is not int or counts[key] < 0:
            raise ValueError("Invalid final-test counts")
    if (
        sum(counts[f"fraud_{a}"] for a in ("pass", "review", "block")) != fraud
        or sum(counts[f"legitimate_{a}"] for a in ("pass", "review", "block"))
        != legitimate
    ):
        raise ValueError("Incomplete final-test decisions")
    review_rate = (counts["fraud_review"] + counts["legitimate_review"]) / (
        fraud + legitimate
    )
    if (
        (fraud - counts["fraud_pass"]) / fraud < policy["minimum_fraud_routed_rate"]
        or counts["legitimate_block"] / legitimate > policy["maximum_false_block_rate"]
        or review_rate * policy["peak_transactions_per_second"] * 3600
        > policy["maximum_reviews_per_hour"]
        or review_rate * policy["normal_transactions_per_second"] * 3600
        > policy["maximum_reviews_per_hour"]
        or review_rate
        * policy["normal_transactions_per_second"]
        * 3600
        * policy["staffed_hours_per_day"]
        > policy["maximum_reviews_per_staffed_day"]
    ):
        raise ValueError("Frozen policy failed agreed acceptance criteria")
    return report


def guard_fixture_urls(postgres_url, redis_url):
    pg, rd = urlparse(postgres_url), urlparse(redis_url)
    loopback = (
        pg.hostname in ("localhost", "127.0.0.1")
        and pg.port == 25432
        and rd.hostname in ("localhost", "127.0.0.1")
        and rd.port == 26379
    )
    isolated_containers = (
        pg.hostname == "sentinel-task4-test-postgres-1"
        and pg.port == 5432
        and rd.hostname == "sentinel-task4-test-redis-1"
        and rd.port == 6379
    )
    if (
        not (loopback or isolated_containers)
        or pg.path != "/sentinel_task4_test"
        or pg.query
        or rd.path != "/0"
        or rd.query
    ):
        raise ValueError(
            "Fixtures require the explicitly isolated loopback ports or test container names"
        )


class ScoringWorker:
    """One session lock owns the run; each card is always scored serially.

    PostgreSQL history/snapshots survive crashes; Redis is never feature state.
    Only monotonically chronological simulator input is supported. A late event
    blocks the run rather than silently corrupting already-issued decisions.
    """

    def __init__(
        self,
        connection,
        transport,
        scorer,
        run_id,
        package_pin,
        *,
        mode,
        stream,
        gate_report_pin=None,
        max_attempts=3,
        diagnostic_deadline_ms=None,
        database_target_pin=None,
        concurrent_sessions=1,
        connection_factory=None,
    ):
        self.db, self.redis, self.scorer = connection, transport, scorer
        self.run_id, self.package_pin = str(UUID(run_id)), package_pin
        self.mode, self.stream = mode, stream
        self.group = f"sentinel-scoring:{self.run_id}"
        self.max_attempts = max_attempts
        if diagnostic_deadline_ms not in (None, 2000):
            raise ValueError("Only the authorized two-second diagnostic is supported")
        self.diagnostic_only = diagnostic_deadline_ms is not None
        self.deadline_ms = diagnostic_deadline_ms or 1000
        self.owns_lock = False
        self.claim_cursor = "0-0"
        self._ready_heartbeat_at = 0.0
        self._stream_reconciled = False
        self._profile_records = []
        self.parallel = None
        if (
            concurrent_sessions not in (1, 2)
            or concurrent_sessions > 1
            and connection_factory is None
        ):
            raise ValueError(
                "Bounded scoring sessions require an explicit connection factory"
            )
        if mode not in ("fixture", "application") or max_attempts < 1:
            raise ValueError("Invalid worker configuration")
        identity = self.db.execute("SELECT current_database() AS name").fetchone()[
            "name"
        ]
        if mode == "fixture" and (
            identity != "sentinel_task4_test" or not stream.startswith("task6-test:")
        ):
            raise ValueError("Fixture worker cannot use application data or stream")
        if mode == "application" and (
            not application_database_matches(connection, database_target_pin)
            or not gate_report_pin
        ):
            raise ValueError(
                "Application worker requires confirmed database and final-test gate"
            )
        lock = self.db.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 7)) AS held",
            (self.run_id,),
        ).fetchone()
        if not lock["held"]:
            raise ValueError("Another worker owns this run")
        self.owns_lock = True
        if self.db.execute("SHOW fsync").fetchone()["fsync"] != "on":
            raise ValueError("Durable scoring requires PostgreSQL fsync")
        self.db.execute("SET synchronous_commit=on")
        with self.db.transaction():
            self.db.execute(
                """INSERT INTO scoring_runs (run_id,mode,bundle_sha256,policy_version,feature_version,gate_report_sha256,deadline_ms,durability_contract,diagnostic_only)
              VALUES (%s,%s,%s,%s,%s,%s,%s,'postcommit-v1',%s) ON CONFLICT DO NOTHING""",
                (
                    self.run_id,
                    mode,
                    package_pin,
                    scorer.policy["policy_version"],
                    FEATURE_VERSION,
                    gate_report_pin,
                    self.deadline_ms,
                    self.diagnostic_only,
                ),
            )
            run = self.db.execute(
                "SELECT * FROM scoring_runs WHERE run_id=%s", (self.run_id,)
            ).fetchone()
            if (
                run["bundle_sha256"] != package_pin
                or run["policy_version"] != scorer.policy["policy_version"]
                or run["mode"] != mode
                or run["gate_report_sha256"] != gate_report_pin
                or run["durability_contract"] != "postcommit-v1"
                or run["deadline_ms"] != self.deadline_ms
                or run["diagnostic_only"] != self.diagnostic_only
            ):
                raise ValueError("Assigned run identity cannot change on restart")
            self.db.execute(
                "INSERT INTO scoring_worker_health(run_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (self.run_id,),
            )
        self.started_at = run["started_at"]
        self.health(False, "history_reconciling")
        self.reconcile_history()
        if isinstance(self.scorer, FrozenScorer):
            with self.profile_stage("scorer_initialization"):
                warm_scorer(self.scorer)
        self.ensure_group()
        if concurrent_sessions > 1:
            from .parallel_worker import ParallelScoring

            connections = []
            try:
                for _ in range(concurrent_sessions):
                    session = connection_factory()
                    connections.append(session)
                    if (
                        not session.autocommit
                        or session.execute("SHOW fsync").fetchone()["fsync"] != "on"
                    ):
                        raise ValueError("Scoring session durability mismatch")
                    if mode == "application" and not application_database_matches(
                        session, database_target_pin
                    ):
                        raise ValueError("Scoring session database target mismatch")
                    if (
                        mode == "fixture"
                        and session.execute(
                            "SELECT current_database() AS name"
                        ).fetchone()["name"]
                        != "sentinel_task4_test"
                    ):
                        raise ValueError("Scoring fixture session target mismatch")
                    session.execute("SET synchronous_commit=on")
                    session.execute("SET extra_float_digits=3")
                    session.execute("SET statement_timeout=3000")
                    session.execute("SET lock_timeout=1000")
                self.parallel = ParallelScoring(self, connections)
            except BaseException:
                for session in connections:
                    session.close()
                raise

    def scoring_session(self, connection):
        session = object.__new__(ScoringWorker)
        for name in (
            "redis",
            "scorer",
            "run_id",
            "package_pin",
            "mode",
            "stream",
            "group",
            "max_attempts",
            "deadline_ms",
            "diagnostic_only",
            "started_at",
        ):
            setattr(session, name, getattr(self, name))
        session.db = connection
        session.owns_lock = False
        session.parallel = None
        session._profile_records = []
        return session

    def ensure_group(self):
        try:
            self.redis.xgroup_create(self.stream, self.group, "0", mkstream=True)
            self._stream_reconciled = False
        except redis.ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    def health(self, ready, error=None, blocked=False):
        self.db.execute(
            """UPDATE scoring_worker_health SET ready=%s,error_code=%s,
          blocked=blocked OR %s,heartbeat_at=clock_timestamp() WHERE run_id=%s""",
            (ready, error, blocked, self.run_id),
        )
        if ready:
            self._ready_heartbeat_at = time.monotonic()

    def ready_heartbeat(self):
        if time.monotonic() - self._ready_heartbeat_at < 1:
            return
        if not self._stream_reconciled:
            group = next(
                g
                for g in self.redis.xinfo_groups(self.stream)
                if g["name"] == self.group
            )
            if group["lag"] or group["pending"]:
                self.health(False, "stream_reconciling")
                self._ready_heartbeat_at = time.monotonic()
                return
            self._stream_reconciled = True
        blocked = self.db.execute(
            "SELECT blocked FROM scoring_worker_health WHERE run_id=%s", (self.run_id,)
        ).fetchone()["blocked"]
        if not blocked:
            self.health(True)

    def reconcile_history(self):
        # No mutable Redis cache to reconstruct. Verify durable checkpoints first.
        rows = self.db.execute(
            """SELECT h.event_id FROM scoring_history h
          JOIN authorization_events e USING(event_id)
          LEFT JOIN scoring_feature_snapshots f ON f.run_id=h.run_id AND f.event_id=h.event_id
          WHERE h.run_id=%s AND (f.event_id IS NULL OR h.card_token<>e.card_token
            OR h.occurred_at<>e.occurred_at OR h.amount_minor<>e.amount_minor) LIMIT 1""",
            (self.run_id,),
        ).fetchone()
        missing_job = self.db.execute(
            """SELECT j.event_id FROM scoring_jobs j
          LEFT JOIN scoring_feature_snapshots f USING(run_id,event_id)
          WHERE j.run_id=%s AND f.event_id IS NULL
          AND j.error_code IS DISTINCT FROM 'out_of_order_event' LIMIT 1""",
            (self.run_id,),
        ).fetchone()
        if rows or missing_job:
            self.health(False, "history_integrity_failed", True)
            raise ValueError("Durable history integrity failed")
        prior_by_card = {}
        snapshots = self.db.execute(
            """SELECT f.*,e.sanitized_payload FROM scoring_feature_snapshots f
          JOIN authorization_events e USING(event_id) WHERE f.run_id=%s
          ORDER BY e.created_at,e.event_id""",
            (self.run_id,),
        ).fetchall()
        try:
            with self.db.transaction():
                for snapshot in snapshots:
                    event = snapshot["sanitized_payload"]
                    prior = prior_by_card.setdefault(event["card_token"], [])
                    features = features_from_prior(event, prior)
                    if (
                        features != {k: snapshot[k] for k in FEATURE_ORDER}
                        or digest(features) != snapshot["feature_sha256"]
                        or len(prior) != snapshot["history_sequence"]
                    ):
                        raise ValueError("Historical snapshot parity failed")
                    moment = validate_event(event)
                    self.db.execute(
                        """INSERT INTO scoring_history(run_id,event_id,card_token,occurred_at,amount_minor)
                      VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (
                            self.run_id,
                            event["event_id"],
                            event["card_token"],
                            moment,
                            event["amount_minor"],
                        ),
                    )
                    prior.append((int(moment.timestamp()), event["amount_minor"]))
        except ValueError:
            self.health(False, "history_integrity_failed", True)
            raise

    @contextmanager
    def profile_stage(self, stage, event_id=None, **measurements):
        if os.environ.get("SCORING_PROFILE") != "1":
            yield
            return
        tick = time.perf_counter()
        cpu_tick = time.process_time()
        try:
            yield
        finally:
            self._profile_records.append(
                dict(
                    kind="stage_timing",
                    stage=stage,
                    run_id=self.run_id,
                    event_id=str(event_id) if event_id else None,
                    elapsed_ms=(time.perf_counter() - tick) * 1000,
                    process_cpu_ms=(time.process_time() - cpu_tick) * 1000,
                    **measurements,
                )
            )

    def flush_profile(self):
        if self._profile_records:
            records, self._profile_records = self._profile_records, []
            print(
                json.dumps(dict(kind="stage_profile_batch", records=records)),
                flush=True,
            )

    def assign(self, row, *, prepare=False, transaction_open=False):
        queue_ms = (datetime.now(UTC) - row["accepted_at"]).total_seconds() * 1000
        with self.profile_stage(
            "assignment_statement" if transaction_open else "assignment_commit_ack",
            row["event_id"],
            queue_ms=queue_ms,
        ):
            return self._assign(row, prepare=prepare, transaction_open=transaction_open)

    def _assign(self, row, *, prepare=False, transaction_open=False):
        event = row["sanitized_payload"]
        moment = validate_event(event)
        event_id = event["event_id"]
        with (
            self.db.pipeline(),
            nullcontext() if transaction_open else self.db.transaction(),
        ):
            inserted = self.db.execute(
                """INSERT INTO scoring_jobs (run_id,event_id,correlation_id,bundle_sha256,
              model_version,policy_version,feature_version,created_at,deadline_at)
              VALUES (%s,%s,%s,%s,'random_forest.sigmoid',%s,%s,%s,%s + %s * interval '1 millisecond')
              ON CONFLICT DO NOTHING RETURNING event_id""",
                (
                    self.run_id,
                    event_id,
                    row["envelope"]["correlation_id"],
                    self.package_pin,
                    self.scorer.policy["policy_version"],
                    FEATURE_VERSION,
                    row["accepted_at"],
                    row["accepted_at"],
                    self.deadline_ms,
                ),
            ).fetchone()
            if not inserted:
                return None if prepare else True
            with self.profile_stage("history_read", event_id):
                latest = self.db.execute(
                    """SELECT max(occurred_at) AS moment,count(*) AS n,
                    coalesce(jsonb_agg(jsonb_build_array(extract(epoch FROM occurred_at)::bigint,amount_minor))
                      FILTER (WHERE occurred_at >= %s - interval '24 hours' AND occurred_at < %s), '[]'::jsonb) AS prior
                    FROM scoring_history WHERE run_id=%s AND card_token=%s""",
                    (moment, moment, self.run_id, event["card_token"]),
                ).fetchone()
            if latest["moment"] and moment < latest["moment"]:
                self.finish_failure(event_id, "failed", "out_of_order_event")
                self.health(False, "out_of_order_event", True)
                return False
            with self.profile_stage("feature_calculation", event_id):
                features = features_from_prior(event, latest["prior"])
            self.db.execute(
                """INSERT INTO scoring_feature_snapshots
              (run_id,event_id,feature_sha256,history_sequence,amount,hour,day_of_week,
               prior_count_1h,prior_count_24h,prior_sum_24h,prior_mean_24h,merchant_category)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.run_id,
                    event_id,
                    digest(features),
                    latest["n"],
                    *(features[k] for k in FEATURE_ORDER),
                ),
            )
            self.db.execute(
                "INSERT INTO scoring_history(run_id,event_id,card_token,occurred_at,amount_minor) VALUES (%s,%s,%s,%s,%s)",
                (
                    self.run_id,
                    event_id,
                    event["card_token"],
                    moment,
                    event["amount_minor"],
                ),
            )
            if prepare:
                publication = row["publication_status"]
                if publication == "dead_letter":
                    self.finish_failure(event_id, "failed", "publication_failed")
                    return None
                if publication != "published":
                    self.db.execute(
                        """UPDATE scoring_jobs SET status='expired',error_code='deadline_expired',
                        retryable=false,updated_at=clock_timestamp() WHERE run_id=%s AND event_id=%s
                        AND clock_timestamp()>=deadline_at""",
                        (self.run_id, event_id),
                    )
                    return None
                prepared = self.db.execute(
                    """UPDATE scoring_jobs SET status='scoring',attempts=1,
                        updated_at=clock_timestamp()
                    WHERE run_id=%s AND event_id=%s AND clock_timestamp()<deadline_at
                    RETURNING *,clock_timestamp() AS inference_start_clock""",
                    (self.run_id, event_id),
                ).fetchone()
                if not prepared:
                    self.finish_failure(event_id, "expired", "deadline_expired")
                    return None
                prepared.update(features)
                prepared["feature_sha256"] = digest(features)
        # Returning from the transaction context waits for synchronous COMMIT.
        return prepared if prepare else True

    def finish_failure(self, event_id, status, code):
        with self.profile_stage("terminal_failure_storage", event_id, status=status):
            return self._finish_failure(event_id, status, code)

    def _finish_failure(self, event_id, status, code):
        self.db.execute(
            """UPDATE scoring_jobs SET status=%s,error_code=%s,retryable=false,
          next_attempt_at=NULL,updated_at=clock_timestamp() WHERE run_id=%s AND event_id=%s
          AND status NOT IN ('scored','expired','failed')""",
            (status, code, self.run_id, event_id),
        )

    def prepare_pending(self, event_id):
        with self.profile_stage("prepare_commit_ack", event_id):
            return self._prepare_pending(event_id)

    def _prepare_pending(self, event_id):
        with self.db.pipeline(), self.db.transaction():
            row = self.db.execute(
                """SELECT j.*,f.feature_sha256,f.amount,f.hour,f.day_of_week,
                f.prior_count_1h,f.prior_count_24h,f.prior_sum_24h,f.prior_mean_24h,f.merchant_category,
                o.status AS publication_status,clock_timestamp() >= j.deadline_at AS expired,
                clock_timestamp() AS inference_start_clock
              FROM scoring_jobs j LEFT JOIN scoring_feature_snapshots f USING(run_id,event_id)
              JOIN authorization_event_outbox o ON o.event_id=j.event_id
              WHERE j.run_id=%s AND j.event_id=%s FOR UPDATE OF j""",
                (self.run_id, event_id),
            ).fetchone()
            if row["status"] in TERMINAL:
                return
            if row["expired"]:
                self.finish_failure(event_id, "expired", "deadline_expired")
                return
            prediction = self.db.execute(
                "SELECT 1 FROM scoring_predictions WHERE run_id=%s AND event_id=%s",
                (self.run_id, event_id),
            ).fetchone()
            if prediction:
                self.finalize_prediction(event_id)
                return
            publication = row["publication_status"]
            if publication == "dead_letter":
                self.finish_failure(event_id, "failed", "publication_failed")
                return
            if publication != "published":
                return
            if row["attempts"] >= self.max_attempts:
                self.finish_failure(event_id, "failed", "retry_exhausted")
                return
            if row["next_attempt_at"] and row["next_attempt_at"] > datetime.now(UTC):
                return
            self.db.execute(
                "UPDATE scoring_jobs SET status='scoring',attempts=attempts+1,updated_at=clock_timestamp() WHERE run_id=%s AND event_id=%s",
                (self.run_id, event_id),
            )
            snapshot = row
        features = {name: snapshot[name] for name in FEATURE_ORDER}
        if digest(features) != snapshot["feature_sha256"]:
            # SQL numeric roundtrips can change int to float; normalize at creation too.
            self.health(False, "snapshot_integrity_failed", True)
            raise ValueError("Snapshot checksum mismatch")
        return row

    def score_pending(self, event_id):
        self.score_batch([event_id])

    def score_batch(self, event_ids):
        rows = [
            row for event_id in event_ids if (row := self.prepare_pending(event_id))
        ]
        self.score_prepared(rows)

    def score_prepared(self, rows):
        if not rows:
            return
        tick = time.perf_counter()
        try:
            with self.profile_stage(
                "inference",
                batch_size=len(rows),
                event_ids=[str(row["event_id"]) for row in rows],
            ):
                probabilities, actions = self.scorer.score(
                    [{name: row[name] for name in FEATURE_ORDER} for row in rows]
                )
        except Exception:
            for row in rows:
                event_id = row["event_id"]
                with self.db.pipeline(), self.db.transaction():
                    state = self.db.execute(
                        "SELECT *,clock_timestamp() >= deadline_at AS expired FROM scoring_jobs WHERE run_id=%s AND event_id=%s FOR UPDATE",
                        (self.run_id, event_id),
                    ).fetchone()
                    if state["expired"]:
                        self.finish_failure(event_id, "expired", "deadline_expired")
                    elif state["attempts"] >= self.max_attempts:
                        self.finish_failure(event_id, "failed", "inference_failed")
                    else:
                        self.db.execute(
                            """UPDATE scoring_jobs SET status='unavailable',error_code='inference_unavailable',
                          next_attempt_at=clock_timestamp()+interval '50 milliseconds',updated_at=clock_timestamp()
                          WHERE run_id=%s AND event_id=%s""",
                            (self.run_id, event_id),
                        )
            return
        elapsed = (time.perf_counter() - tick) * 1000
        predictions = list(zip(rows, probabilities, actions, strict=True))
        if len(rows) == 1:
            row, probability, action = predictions[0]
            self.persist_prediction(row, float(probability), str(action), elapsed)
            return
        staged = []
        try:
            with (
                self.profile_stage(
                    "prediction_batch_commit_ack",
                    batch_size=len(rows),
                    event_ids=[str(row["event_id"]) for row in rows],
                ),
                self.db.transaction(),
            ):
                for row, probability, action in predictions:
                    if self._persist_prediction(
                        row,
                        float(probability),
                        str(action),
                        elapsed,
                        defer_finalization=True,
                    ):
                        staged.append(row["event_id"])
        except psycopg.errors.RaiseException:
            # A boundary crossed during staging rolls back every private prediction.
            # Retry storage individually with fresh database-clock deadline checks.
            for row, probability, action in predictions:
                self.persist_prediction(row, float(probability), str(action), elapsed)
            return
        # All private predictions are committed before any execution is attempted.
        try:
            with self.profile_stage(
                "execution_batch_commit_ack",
                batch_size=len(staged),
                event_ids=[str(event_id) for event_id in staged],
            ):
                self.finalize_batch(staged)
        except psycopg.errors.RaiseException:
            # A deferred deadline guard rolls the whole execution batch back.
            # Recheck each deadline independently; a timely peer must not be lost.
            for event_id in staged:
                self.finalize_prediction(event_id)

    def score_new_batch(self, batch):
        prepared, staged = [], []
        stopped = False
        for row in batch:
            with self.profile_stage(
                "assignment_start",
                row["event_id"],
                queue_ms=(datetime.now(UTC) - row["accepted_at"]).total_seconds()
                * 1000,
            ):
                pass
        try:
            with (
                self.profile_stage(
                    "checkpoint_prediction_commit_ack",
                    batch_size=len(batch),
                    event_ids=[str(row["event_id"]) for row in batch],
                ),
                self.db.transaction(),
            ):
                prepared, stopped = self.prepare_new_batch(batch)
                if prepared:
                    tick = time.perf_counter()
                    try:
                        with self.profile_stage(
                            "inference",
                            batch_size=len(prepared),
                            event_ids=[str(row["event_id"]) for row in prepared],
                        ):
                            probabilities, actions = self.scorer.score(
                                [
                                    {name: row[name] for name in FEATURE_ORDER}
                                    for row in prepared
                                ]
                            )
                    except Exception as error:
                        raise InferenceFailure from error
                    elapsed = (time.perf_counter() - tick) * 1000
                    staged = self.stage_prediction_batch(
                        prepared, probabilities, actions, elapsed
                    )
        except (InferenceFailure, psycopg.errors.RaiseException) as error:
            if isinstance(error, psycopg.errors.RaiseException):
                if (
                    error.diag.message_primary
                    != "Prediction requires a timely postcommit scoring run"
                ):
                    raise
                now = self.db.execute("SELECT clock_timestamp() AS moment").fetchone()[
                    "moment"
                ]
                if not any(
                    (now - row["accepted_at"]).total_seconds() * 1000
                    >= self.deadline_ms
                    for row in batch
                ):
                    raise
            # No checkpoint survived. The existing retry path records a durable
            # terminal state without restarting history for an expected expiry.
            prepared = []
            for row in batch:
                ready = self.assign(row, prepare=True)
                if ready is False:
                    stopped = True
                    break
                if ready is not None:
                    prepared.append(ready)
            self.score_prepared(prepared)
            return stopped
        # Acknowledged synchronous COMMIT above precedes every public effect.
        if len(staged) == 1:
            self.finalize_prediction(staged[0])
        elif staged:
            try:
                with self.profile_stage(
                    "execution_batch_commit_ack",
                    batch_size=len(staged),
                    event_ids=[str(event_id) for event_id in staged],
                ):
                    self.finalize_batch(staged)
            except psycopg.errors.RaiseException:
                for event_id in staged:
                    self.finalize_prediction(event_id)
        return stopped

    def prepare_new_batch(self, batch):
        inputs = [
            {
                "event_id": str(row["event_id"]),
                "card_token": row["sanitized_payload"]["card_token"],
                "occurred_at": validate_event(row["sanitized_payload"]).isoformat(),
            }
            for row in batch
        ]
        with self.profile_stage(
            "history_batch_read", event_ids=[item["event_id"] for item in inputs]
        ):
            contexts = self.db.execute(
                """SELECT i.event_id, h.moment,h.n,h.prior,
                  EXISTS(SELECT 1 FROM scoring_jobs j WHERE j.run_id=%s AND j.event_id=i.event_id) AS assigned
                FROM jsonb_to_recordset(%s) AS i(event_id uuid,card_token text,occurred_at timestamptz)
                LEFT JOIN LATERAL (
                  SELECT max(occurred_at) AS moment,count(*) AS n,
                    coalesce(jsonb_agg(jsonb_build_array(extract(epoch FROM occurred_at)::bigint,amount_minor))
                      FILTER(WHERE occurred_at>=i.occurred_at-interval '24 hours' AND occurred_at<i.occurred_at),'[]'::jsonb) AS prior
                  FROM scoring_history WHERE run_id=%s AND card_token=i.card_token
                ) h ON true""",
                (self.run_id, Jsonb(inputs), self.run_id),
            ).fetchall()
        by_id = {str(row["event_id"]): row for row in contexts}
        selected, appended, last, seen = [], {}, {}, set()
        stopped = False
        for row in batch:
            event = row["sanitized_payload"]
            event_id = str(row["event_id"])
            context = by_id[event_id]
            if context["assigned"] or event_id in seen:
                continue
            seen.add(event_id)
            moment = validate_event(event)
            card = event["card_token"]
            latest = last.get(card, context["moment"])
            item = {
                "event_id": event_id,
                "correlation_id": row["envelope"]["correlation_id"],
                "accepted_at": row["accepted_at"].isoformat(),
                "occurred_at": moment.isoformat(),
                "card_token": card,
                "amount_minor": event["amount_minor"],
                "publication_status": row["publication_status"],
                "out_of_order": bool(latest and moment < latest),
                "feature_sha256": None,
            }
            selected.append(item)
            if item["out_of_order"]:
                stopped = True
                break
            prior = appended.setdefault(card, [])
            with self.profile_stage("feature_calculation", event_id):
                features = features_from_prior(event, context["prior"] + prior)
            item.update(features)
            item["feature_sha256"] = digest(features)
            item["history_sequence"] = context["n"] + len(prior)
            prior.append((int(moment.timestamp()), event["amount_minor"]))
            last[card] = moment
        if not selected:
            return [], stopped
        with self.profile_stage(
            "checkpoint_batch_statements",
            event_ids=[item["event_id"] for item in selected],
        ):
            rows = self.db.execute(
                "SELECT q.*,clock_timestamp() AS inference_start_clock FROM prepare_scoring_checkpoints(%s,%s,%s,%s,%s,%s) q",
                (
                    self.run_id,
                    self.package_pin,
                    self.scorer.policy["policy_version"],
                    FEATURE_VERSION,
                    self.deadline_ms,
                    Jsonb(selected),
                ),
            ).fetchall()
        if stopped:
            self.health(False, "out_of_order_event", True)
        features_by_id = {item["event_id"]: item for item in selected}
        positions = {item["event_id"]: index for index, item in enumerate(selected)}
        rows.sort(key=lambda row: positions[str(row["event_id"])])
        prepared = []
        for row in rows:
            if row["status"] != "scoring":
                continue
            item = features_by_id[str(row["event_id"])]
            row.update({name: item[name] for name in FEATURE_ORDER})
            row["feature_sha256"] = item["feature_sha256"]
            prepared.append(row)
        return prepared, stopped

    def stage_prediction_batch(self, prepared, probabilities, actions, elapsed):
        payload = [
            {
                "event_id": str(row["event_id"]),
                "probability": float(probability),
                "action": str(action),
                "reason_code": {
                    "Pass": "below_review",
                    "Review": "review_region",
                    "Block": "block_region",
                }[str(action)],
                "inference_started_at": row["inference_start_clock"].isoformat(),
                "inference_ms": elapsed,
            }
            for row, probability, action in zip(
                prepared, probabilities, actions, strict=True
            )
        ]
        with self.profile_stage(
            "prediction_batch_statement",
            event_ids=[item["event_id"] for item in payload],
        ):
            rows = self.db.execute(
                """WITH locked AS MATERIALIZED (
                    SELECT j.event_id,j.deadline_at,i.probability,i.action,i.reason_code,
                      i.inference_started_at,i.inference_ms
                    FROM scoring_jobs j JOIN jsonb_to_recordset(%s) AS i(event_id uuid,
                      probability double precision,action text,reason_code text,
                      inference_started_at timestamptz,inference_ms double precision) USING(event_id)
                    WHERE j.run_id=%s AND j.status='scoring' FOR UPDATE OF j
                ), expired AS (
                    UPDATE scoring_jobs j SET status='expired',error_code='deadline_expired',
                      retryable=false,updated_at=clock_timestamp() FROM locked l
                    WHERE j.run_id=%s AND j.event_id=l.event_id AND clock_timestamp()>=l.deadline_at
                    RETURNING j.event_id
                )
                INSERT INTO scoring_predictions(run_id,event_id,probability,action,review_threshold,
                    block_threshold,reason_code,inference_started_at,inference_finished_at,inference_ms,decision_at)
                SELECT %s,l.event_id,l.probability,l.action,%s,%s,l.reason_code,
                    l.inference_started_at,clock_timestamp(),l.inference_ms,clock_timestamp()
                FROM locked l WHERE clock_timestamp()<l.deadline_at
                RETURNING event_id""",
                (
                    Jsonb(payload),
                    self.run_id,
                    self.run_id,
                    self.run_id,
                    self.scorer.r,
                    self.scorer.b,
                ),
            ).fetchall()
        return [row["event_id"] for row in rows]

    def persist_prediction(self, row, probability, action, elapsed):
        with self.profile_stage("result_commit_ack", row["event_id"]):
            return self._persist_prediction(row, probability, action, elapsed)

    def _persist_prediction(
        self,
        row,
        probability,
        action,
        elapsed,
        *,
        defer_finalization=False,
        transaction_open=False,
    ):
        event_id, started = row["event_id"], row["inference_start_clock"]
        try:
            with (
                self.profile_stage(
                    "prediction_statement"
                    if transaction_open
                    else "prediction_commit_ack",
                    event_id,
                ),
                self.db.pipeline(),
                nullcontext()
                if transaction_open or defer_finalization
                else self.db.transaction(),
            ):
                state = self.db.execute(
                    "SELECT *,clock_timestamp() >= deadline_at AS expired FROM scoring_jobs WHERE run_id=%s AND event_id=%s FOR UPDATE",
                    (self.run_id, event_id),
                ).fetchone()
                if state["expired"]:
                    self.finish_failure(event_id, "expired", "deadline_expired")
                    return
                self.db.execute(
                    """WITH timing AS MATERIALIZED (SELECT clock_timestamp() AS finished)
                  INSERT INTO scoring_predictions (run_id,event_id,probability,action,review_threshold,block_threshold,
                  reason_code,inference_started_at,inference_finished_at,inference_ms,decision_at)
                  SELECT %s,%s,%s,%s,%s,%s,%s,%s,finished,%s,finished FROM timing""",
                    (
                        self.run_id,
                        event_id,
                        probability,
                        action,
                        self.scorer.r,
                        self.scorer.b,
                        {
                            "Pass": "below_review",
                            "Review": "review_region",
                            "Block": "block_region",
                        }[action],
                        started,
                        elapsed,
                    ),
                )
            # No effect exists yet. Only an acknowledged synchronous COMMIT permits
            # finalization; recovery reuses this immutable prediction without inference.
            if defer_finalization or transaction_open:
                return True
            self.finalize_prediction(event_id)
        except psycopg.errors.RaiseException:
            if defer_finalization or transaction_open:
                raise
            # Deferred deadline validation may reject COMMIT. Never acknowledge it as success.
            state = self.db.execute(
                "SELECT clock_timestamp() >= deadline_at AS expired FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
                (self.run_id, event_id),
            ).fetchone()
            if state["expired"]:
                self.finish_failure(event_id, "expired", "deadline_expired")
            else:
                raise

    def finalize_prediction(self, event_id):
        with self.profile_stage("execution_commit_ack", event_id):
            try:
                self._finalize_prediction(event_id)
            except psycopg.errors.RaiseException:
                state = self.db.execute(
                    "SELECT clock_timestamp() >= deadline_at AS expired FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
                    (self.run_id, event_id),
                ).fetchone()
                if not state["expired"]:
                    raise
                self.finish_failure(event_id, "expired", "deadline_expired")

    def _finalize_prediction(self, event_id):
        self.finalize_batch([event_id])

    def finalize_batch(self, event_ids):
        if not event_ids:
            return
        # One statement is one synchronous transaction in autocommit mode. Its
        # deferred deadline/action guards finish before execute returns.
        # RETURNING dependencies keep result insertion before completion updates.
        self.db.execute(
            """WITH locked AS MATERIALIZED (
                SELECT j.*,clock_timestamp()>=j.deadline_at AS expired
                FROM scoring_jobs j WHERE j.run_id=%s AND j.event_id=ANY(%s::uuid[])
                  AND j.status NOT IN ('scored','expired','failed')
                ORDER BY j.created_at,j.event_id FOR UPDATE OF j
            ), expired_jobs AS (
                UPDATE scoring_jobs j SET status='expired',error_code='deadline_expired',
                  retryable=false,next_attempt_at=NULL,updated_at=clock_timestamp()
                FROM locked l WHERE j.run_id=l.run_id AND j.event_id=l.event_id
                  AND l.expired RETURNING j.event_id
            ), results AS (
                INSERT INTO scoring_results
                SELECT p.run_id,p.event_id,p.probability,p.action,p.review_threshold,
                  p.block_threshold,p.reason_code,p.inference_started_at,
                  p.inference_finished_at,p.inference_ms,clock_timestamp()
                FROM locked l JOIN scoring_predictions p USING(run_id,event_id)
                WHERE NOT l.expired RETURNING run_id,event_id
            )
            UPDATE scoring_jobs j SET status='scored',retryable=false,error_code=NULL,
              next_attempt_at=NULL,updated_at=clock_timestamp()
            FROM results r WHERE j.run_id=r.run_id AND j.event_id=r.event_id""",
            (self.run_id, event_ids),
        )

    def drain(self, limit=50):
        if self.parallel is not None:
            return self.parallel.drain(limit)
        if self.db.execute(
            "SELECT blocked FROM scoring_worker_health WHERE run_id=%s", (self.run_id,)
        ).fetchone()["blocked"]:
            return 0
        rows = self.candidate_rows(limit)
        # Batch only already-waiting attempts; never delay arrivals to fill a batch.
        for first in range(0, len(rows), 4):
            batch = rows[first : first + 4]
            if self.score_new_batch(batch):
                return 0
        jobs = self.db.execute(
            """SELECT j.event_id FROM scoring_jobs j
          JOIN authorization_event_outbox o USING(event_id)
          WHERE j.run_id=%s AND j.status NOT IN ('scored','expired','failed')
          AND (j.deadline_at <= clock_timestamp()
            OR EXISTS (SELECT 1 FROM scoring_predictions p
              WHERE p.run_id=j.run_id AND p.event_id=j.event_id)
            OR (o.status IN ('published','dead_letter')
              AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= clock_timestamp())))
          ORDER BY j.created_at,j.event_id LIMIT %s""",
            (self.run_id, limit),
        ).fetchall()
        for first in range(0, len(jobs), 4):
            self.score_batch([job["event_id"] for job in jobs[first : first + 4]])
        return len(rows) + len(jobs)

    def candidate_rows(self, limit):
        # Database acceptance order is authoritative, irrespective of Redis delivery order.
        # Both event IDs are non-null primary keys; NOT IN permits a hashed lookup
        # instead of repeatedly probing every previously assigned event's index.
        rows = self.db.execute(
            """WITH candidates AS MATERIALIZED (
              SELECT event_id,created_at FROM authorization_events
              WHERE schema_version='2.0' AND created_at >= %s
                AND event_id NOT IN (SELECT event_id FROM scoring_jobs WHERE run_id=%s)
              ORDER BY created_at,event_id LIMIT %s
          ) SELECT e.*,o.envelope,o.status AS publication_status,coalesce(a.received_at,e.created_at) AS accepted_at
          FROM candidates c JOIN authorization_events e USING(event_id)
          JOIN authorization_event_outbox o USING(event_id)
          LEFT JOIN LATERAL (SELECT min(received_at) AS received_at FROM ingestion_attempts
             WHERE event_id=e.event_id AND outcome='accepted') a ON true
          ORDER BY c.created_at,c.event_id""",
            (self.started_at, self.run_id, limit),
        ).fetchall()
        # Wait for the publisher's durable outcome before creating a checkpoint.
        # Acceptance remains in PostgreSQL. Stop at the first unready predecessor
        # so later history cannot overtake it; expiry still records its history.
        ready_rows = []
        for row in rows:
            if (
                row["publication_status"] not in ("published", "dead_letter")
                and (datetime.now(UTC) - row["accepted_at"]).total_seconds() * 1000
                < self.deadline_ms
            ):
                break
            ready_rows.append(row)
        return ready_rows

    def delivery(
        self, message_id, fields, *, acknowledgements=None, lookup=None, failures=None
    ):
        def acknowledge():
            if acknowledgements is None:
                self.redis.xack(self.stream, self.group, message_id)
            else:
                acknowledgements.append(message_id)

        raw = fields.get("envelope", "")
        try:
            if set(fields) != {"envelope"} or not isinstance(raw, str):
                raise ValueError("Invalid stream fields")
            envelope = json.loads(raw)
            if set(envelope) != ENVELOPE_FIELDS:
                raise ValueError("Invalid envelope")
            event_id = str(UUID(envelope["event_id"]))
            row = (
                lookup.get(event_id)
                if lookup is not None
                else self.db.execute(
                    "SELECT envelope FROM authorization_event_outbox WHERE event_id=%s",
                    (event_id,),
                ).fetchone()
            )
            if not row or row["envelope"] != envelope:
                raise ValueError("Untrusted envelope")
        except (ValueError, TypeError, KeyError):
            if failures is not None:
                failures.append(
                    {
                        "message_id": message_id,
                        "payload_sha256": digest(fields),
                        "error_code": "invalid_envelope",
                    }
                )
                acknowledge()
                return
            self.db.execute(
                """INSERT INTO scoring_delivery_failures(run_id,stream_name,message_id,payload_sha256,error_code)
              VALUES (%s,%s,%s,%s,'invalid_envelope') ON CONFLICT DO NOTHING""",
                (
                    self.run_id,
                    self.stream,
                    message_id,
                    digest(fields),
                ),
            )
            acknowledge()
            return
        state = (
            ({"status": row["status"]} if row["status"] is not None else None)
            if lookup is not None
            else self.db.execute(
                "SELECT status FROM scoring_jobs WHERE run_id=%s AND event_id=%s",
                (self.run_id, event_id),
            ).fetchone()
        )
        if state and state["status"] in TERMINAL:
            acknowledge()
        elif not state:
            event = (
                row
                if lookup is not None
                else self.db.execute(
                    "SELECT created_at,schema_version FROM authorization_events WHERE event_id=%s",
                    (event_id,),
                ).fetchone()
            )
            if event and (
                event["created_at"] < self.started_at
                or event["schema_version"] != "2.0"
            ):
                if failures is not None:
                    failures.append(
                        {
                            "message_id": message_id,
                            "payload_sha256": digest(envelope),
                            "error_code": "outside_run",
                        }
                    )
                    acknowledge()
                    return
                self.db.execute(
                    """INSERT INTO scoring_delivery_failures(run_id,stream_name,message_id,payload_sha256,error_code)
                  VALUES (%s,%s,%s,%s,'outside_run') ON CONFLICT DO NOTHING""",
                    (self.run_id, self.stream, message_id, digest(envelope)),
                )
                acknowledge()

    def delivery_batch(self, messages):
        # All audit evidence commits before any stream acknowledgement. Duplicate
        # delivery after a lost COMMIT/ACK reuses the unique message identity.
        if (
            not self.db.autocommit
            or self.db.info.transaction_status != psycopg.pq.TransactionStatus.IDLE
        ):
            raise ValueError("Delivery requires an independent durable boundary")
        acknowledgements, failures = [], []
        with self.profile_stage("delivery_audit_commit_ack", batch_size=len(messages)):
            event_ids = []
            for _, fields in messages:
                try:
                    event_ids.append(
                        str(UUID(json.loads(fields.get("envelope", ""))["event_id"]))
                    )
                except (ValueError, TypeError, KeyError, AttributeError):
                    pass
            rows = self.db.execute(
                """SELECT o.event_id,o.envelope,e.created_at,e.schema_version,j.status
                FROM authorization_event_outbox o JOIN authorization_events e USING(event_id)
                LEFT JOIN scoring_jobs j ON j.event_id=o.event_id AND j.run_id=%s
                WHERE o.event_id=ANY(%s::uuid[])""",
                (self.run_id, event_ids),
            ).fetchall()
            lookup = {str(row["event_id"]): row for row in rows}
            for message_id, fields in messages:
                self.delivery(
                    message_id,
                    fields,
                    acknowledgements=acknowledgements,
                    lookup=lookup,
                    failures=failures,
                )
            if failures:
                # No ACK until the implicit transaction and deferred audit guards
                # complete. Normal delivery reads already-committed terminal state.
                self.db.execute(
                    """INSERT INTO scoring_delivery_failures(run_id,stream_name,message_id,payload_sha256,error_code)
                    SELECT %s,%s,i.message_id,i.payload_sha256,i.error_code
                    FROM jsonb_to_recordset(%s) AS i(message_id text,payload_sha256 text,error_code text)
                    ON CONFLICT DO NOTHING""",
                    (self.run_id, self.stream, Jsonb(failures)),
                )
        if acknowledgements:
            self.redis.xack(self.stream, self.group, *acknowledgements)

    def cycle(self):
        try:
            return self._cycle()
        finally:
            self.flush_profile()

    def _cycle(self):
        cycle_start = time.perf_counter()
        self.redis.ping()
        self.ensure_group()
        drain_start = time.perf_counter()
        processed = self.drain()
        drain_end = time.perf_counter()
        claimed = self.redis.xautoclaim(
            self.stream, self.group, "serial-worker", 1500, self.claim_cursor, count=50
        )
        self.claim_cursor = claimed[0]
        fresh = self.redis.xreadgroup(
            self.group,
            "serial-worker",
            {self.stream: ">"},
            count=50,
            block=None if processed else 50,
        )
        stream_end = time.perf_counter()
        messages = list(claimed[1]) + [m for _, messages in fresh for m in messages]
        if messages:
            self.delivery_batch(messages)
        self.ready_heartbeat()
        if os.environ.get("SCORING_DIAGNOSTICS") == "1":
            print(
                json.dumps(
                    {
                        "kind": "cycle_timing",
                        "work_items": processed,
                        "cycle_ms": (time.perf_counter() - cycle_start) * 1000,
                        "drain_ms": (drain_end - drain_start) * 1000,
                        "stream_ms": (stream_end - drain_end) * 1000,
                        "completion_ms": (time.perf_counter() - stream_end) * 1000,
                    }
                ),
                flush=True,
            )

    def close(self):
        try:
            if self.owns_lock and not self.db.closed:
                self.health(False, "worker_stopped")
        finally:
            try:
                if self.parallel is not None:
                    self.parallel.close()
                    self.parallel = None
            finally:
                self.db.close()


@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--gate-report", type=Path)
    parser.add_argument("--gate-report-sha256")
    parser.add_argument("--diagnostic-deadline-ms", type=int, choices=(2000,))
    args = parser.parse_args(argv)
    from .database import database_connection

    pg_url, tls_settings = database_connection()
    redis_url = os.environ["REDIS_URL"]
    if args.fixture:
        guard_fixture_urls(pg_url, redis_url)
    scorer = FrozenScorer(args.bundle, args.bundle_sha256)
    scorer.verify_references()
    if not args.fixture:
        verify_activation(
            args.gate_report, args.gate_report_sha256, args.bundle_sha256, scorer.policy
        )
    while True:
        worker = None
        connection = None
        try:
            connection = psycopg.connect(
                pg_url,
                **tls_settings,
                autocommit=True,
                row_factory=dict_row,
                connect_timeout=3,
                options="-c statement_timeout=3000 -c lock_timeout=1000 -c extra_float_digits=3",
            )
            connection.execute("SET extra_float_digits=3")
            connection.execute("SET statement_timeout=3000")
            connection.execute("SET lock_timeout=1000")
            transport = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            worker = ScoringWorker(
                connection,
                transport,
                scorer,
                args.run_id,
                args.bundle_sha256,
                mode="fixture" if args.fixture else "application",
                stream=os.environ.get("SCORING_STREAM", "authorization.events.v1"),
                gate_report_pin=args.gate_report_sha256,
                diagnostic_deadline_ms=args.diagnostic_deadline_ms,
                database_target_pin=os.environ.get(
                    "APPLICATION_DATABASE_TARGET_SHA256"
                ),
                concurrent_sessions=int(os.environ.get("SCORING_CONCURRENCY", "1")),
                connection_factory=lambda: psycopg.connect(
                    pg_url,
                    **tls_settings,
                    autocommit=True,
                    row_factory=dict_row,
                    connect_timeout=3,
                    options="-c statement_timeout=3000 -c lock_timeout=1000 -c extra_float_digits=3",
                ),
            )
            while True:
                worker.cycle()
        except KeyboardInterrupt:
            break
        except (psycopg.Error, redis.RedisError) as error:
            print(
                json.dumps(dependency_failure(error)),
                flush=True,
            )
            time.sleep(0.1)
        finally:
            if worker:
                try:
                    worker.close()
                except psycopg.Error:
                    pass
            elif connection:
                connection.close()


if __name__ == "__main__":
    main()
