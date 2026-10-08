"""Bounded independent-card scoring under one durable run owner."""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from psycopg.types.json import Jsonb

from .features import FEATURE_VERSION, validate_event


class ParallelScoring:
    def __init__(self, owner, connections):
        self.owner = owner
        self.connections = connections
        self.slots = Queue(maxsize=len(connections))
        for connection in connections:
            self.slots.put(owner.scoring_session(connection))
        self.executor = ThreadPoolExecutor(
            max_workers=len(connections), thread_name_prefix="card-scoring"
        )
        self.active = {}
        self.latest = {
            row["card_token"]: row["moment"]
            for row in owner.db.execute(
                "SELECT card_token,max(occurred_at) AS moment FROM scoring_history WHERE run_id=%s GROUP BY card_token",
                (owner.run_id,),
            ).fetchall()
        }
        self.closed = False

    def collect(self):
        for future, info in list(self.active.items()):
            if future.done():
                del self.active[future]
                self.owner._profile_records.extend(info["records"])
                future.result()

    def submit(self, card, rows, retry=False):
        session = self.slots.get_nowait()
        info = {
            "card": card,
            "ids": {str(row["event_id"]) for row in rows},
            "records": [],
        }

        def execute():
            session._profile_records = []
            try:
                if retry:
                    session.score_batch([row["event_id"] for row in rows])
                else:
                    session.score_new_batch(rows)
            finally:
                info["records"] = list(session._profile_records)
                self.slots.put(session)

        self.active[self.executor.submit(execute)] = info

    def reject_order(self, row):
        owner = self.owner
        payload = {
            "event_id": str(row["event_id"]),
            "correlation_id": row["envelope"]["correlation_id"],
            "accepted_at": row["accepted_at"].isoformat(),
            "publication_status": row["publication_status"],
            "out_of_order": True,
            "feature_sha256": None,
        }
        owner.db.execute(
            "SELECT * FROM prepare_scoring_checkpoints(%s,%s,%s,%s,%s,%s)",
            (
                owner.run_id,
                owner.package_pin,
                owner.scorer.policy["policy_version"],
                FEATURE_VERSION,
                owner.deadline_ms,
                Jsonb([payload]),
            ),
        )
        owner.health(False, "out_of_order_event", True)

    def drain(self, limit):
        self.collect()
        owner = self.owner
        if owner.db.execute(
            "SELECT blocked FROM scoring_worker_health WHERE run_id=%s", (owner.run_id,)
        ).fetchone()["blocked"]:
            return len(self.active)
        ids = {event_id for info in self.active.values() for event_id in info["ids"]}
        busy = {info["card"] for info in self.active.values()}
        jobs = owner.db.execute(
            """SELECT j.event_id,e.card_token,
            (j.deadline_at<=clock_timestamp() OR EXISTS(SELECT 1 FROM scoring_predictions p WHERE p.run_id=j.run_id AND p.event_id=j.event_id)
             OR (o.status IN ('published','dead_letter') AND (j.next_attempt_at IS NULL OR j.next_attempt_at<=clock_timestamp()))) AS due
            FROM scoring_jobs j JOIN authorization_events e USING(event_id) JOIN authorization_event_outbox o USING(event_id)
            WHERE j.run_id=%s AND j.status NOT IN ('scored','expired','failed') ORDER BY j.created_at,j.event_id LIMIT %s""",
            (owner.run_id, limit),
        ).fetchall()
        reserved = {row["card_token"] for row in jobs}
        reserved.update(
            row["card_token"]
            for row in owner.db.execute(
                "SELECT DISTINCT e.card_token FROM scoring_jobs j JOIN authorization_events e USING(event_id) WHERE j.run_id=%s AND j.status NOT IN ('scored','expired','failed')",
                (owner.run_id,),
            ).fetchall()
        )
        submitted = 0
        for job in jobs:
            if str(job["event_id"]) in ids or not job["due"]:
                continue
            if len(self.active) >= len(self.connections) or job["card_token"] in busy:
                break
            self.submit(job["card_token"], [job], retry=True)
            busy.add(job["card_token"])
            submitted += 1
        if len(self.active) >= len(self.connections):
            return submitted + len(self.active)
        rows = [
            row
            for row in owner.candidate_rows(limit)
            if str(row["event_id"]) not in ids
        ]
        position = 0
        while position < len(rows) and len(self.active) < len(self.connections):
            card = rows[position]["sanitized_payload"]["card_token"]
            # A busy predecessor stops admission rather than being overtaken.
            if card in busy or card in reserved:
                break
            batch = []
            last = self.latest.get(card)
            rejected = None
            while (
                position < len(rows)
                and len(batch) < 4
                and rows[position]["sanitized_payload"]["card_token"] == card
            ):
                row = rows[position]
                moment = validate_event(row["sanitized_payload"])
                if last is not None and moment < last:
                    rejected = row
                    break
                batch.append(row)
                last = moment
                position += 1
            if batch:
                self.submit(card, batch)
                busy.add(card)
                self.latest[card] = last
                submitted += len(batch)
            if rejected is not None:
                self.reject_order(rejected)
                break
        return submitted + len(self.active)

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Never release the coordinator's advisory fence while session work lives.
        self.executor.shutdown(wait=True, cancel_futures=True)
        for info in self.active.values():
            self.owner._profile_records.extend(info["records"])
        self.active.clear()
        for connection in self.connections:
            connection.close()
