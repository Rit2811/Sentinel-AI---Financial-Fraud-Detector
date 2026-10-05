"""Correlate safe stage records with diagnostic outcomes, not scoring inputs."""

import json
from collections import defaultdict

from .connected_benchmark import latency_summary


def event_profiles(report, output):
    events = {
        row["event_id"]: dict(row, stages={})
        for row in report["event_database_timings"]
    }
    for name in (
        "worker-profile.log",
        "publisher-profile.log",
        "ingestion-profile.log",
    ):
        path = output / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            for record in message.get("records", []):
                ids = record.get("event_ids") or [record.get("event_id")]
                for event_id in ids:
                    if event_id not in events:
                        continue
                    stages = events[event_id]["stages"]
                    stage = record["stage"]
                    stages.setdefault(stage, []).append(record["elapsed_ms"])
                    if "queue_ms" in record:
                        stages.setdefault("accepted_to_assignment_queue", []).append(
                            record["queue_ms"]
                        )
    groups = {}
    for status in ("scored", "expired", "failed"):
        timings = defaultdict(list)
        selected = [row for row in events.values() if row["status"] == status]
        for row in selected:
            for stage, durations in row["stages"].items():
                timings[stage].extend(durations)
        groups[status] = {
            "count": len(selected),
            "stages": {
                stage: latency_summary(values) for stage, values in timings.items()
            },
        }
    return {
        "basis": "UUID-correlated stage scopes; batch duration shared by members, not additive. DB timestamps except earlier acknowledged prediction witness are pre-COMMIT. Missing records are missing, never zero.",
        "outcomes": groups,
        "events": list(events.values()),
    }
