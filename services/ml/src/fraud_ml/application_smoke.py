"""Non-destructive generated-event check of the activated local application."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import numpy as np
from threadpoolctl import threadpool_limits

from .features import features_from_prior
from .serving import FrozenScorer


BASE = "http://127.0.0.1:18000"


def is_duplicate_acceptance(status, duplicate, acceptance):
    return status == 200 and duplicate == {**acceptance, "outcome": "duplicate"}


def request(path, *, method="GET", body=None, token=None, key=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    message = Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
        method=method,
    )
    try:
        response = urlopen(message, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def terminal(event_id, token):
    until = time.monotonic() + 5
    while time.monotonic() < until:
        status, body = request(f"/api/v1/transactions/{event_id}/result", token=token)
        if status == 200 and body["status"] in ("scored", "failed", "expired"):
            return body
        time.sleep(0.05)
    raise RuntimeError("Application result did not become terminal")


def generated_cases(scorer):
    events = []
    for category in ("grocery_pos", "shopping_net", "misc_net", "shopping_pos"):
        for hour in (0, 3, 12, 23):
            for amount in (
                100,
                1000,
                10000,
                20000,
                40000,
                60000,
                80000,
                100000,
                150000,
            ):
                events.append(
                    {
                        "schema_version": "2.0",
                        "data_origin": "sparkov_replay",
                        "event_id": str(uuid4()),
                        "authorization_id": str(uuid4()),
                        "occurred_at": (
                            datetime(2020, 1, 5, tzinfo=UTC) + timedelta(hours=hour)
                        )
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "amount_minor": amount,
                        "currency": "USD",
                        "card_token": "card_"
                        + hashlib.sha256(uuid4().bytes).hexdigest(),
                        "merchant_id": "merchant_"
                        + hashlib.sha256(b"task6-generated-smoke").hexdigest(),
                        "merchant_category": category,
                        "time_basis": "source_wall_clock_as_utc",
                        "currency_basis": "simulation_assumption",
                    }
                )
    features = [features_from_prior(event, []) for event in events]
    probabilities, actions = scorer.score(features)
    selected = {}
    for event, vector, probability, action in zip(
        events, features, probabilities, actions
    ):
        selected.setdefault(str(action), (event, vector, float(probability)))
    if set(selected) != {"Pass", "Review", "Block"}:
        raise RuntimeError("Generated cold-history fixtures do not cover all actions")
    return selected


@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-report",
        type=Path,
        help="Recheck existing evidence after restart; no new ingestion",
    )
    args = parser.parse_args(argv)
    ml_root = Path(__file__).resolve().parents[2]
    root = ml_root.parents[1]
    config = {
        key: value
        for line in (root / ".env.task6.local").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }
    metadata = json.loads((ml_root / "artifacts/runtime/application.json").read_text())
    if config["SCORING_RUN_ID"] != metadata["run_id"]:
        raise ValueError("Application run identity mismatch")
    status, _ = request("/ready/scoring")
    if status != 200:
        raise RuntimeError("Application scoring is not ready")
    token = config["RESULT_API_TOKEN"]
    if args.verify_report:
        report = json.loads(args.verify_report.read_text())
        if report["run_id"] != metadata["run_id"]:
            raise ValueError("Restart evidence belongs to another run")
        for case in report["cases"]:
            status, current = request(
                f"/api/v1/transactions/{case['event_id']}/result", token=token
            )
            if status != 200 or current != case["final_result"]:
                raise RuntimeError("Stored application evidence changed across restart")
        report["restart_verified_at"] = datetime.now(UTC).isoformat()
        args.verify_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(args.verify_report), "restart_parity": True}))
        return
    scorer = FrozenScorer(config["SCORING_BUNDLE_DIR"], config["SCORING_BUNDLE_SHA256"])
    scorer.verify_references()
    selected = generated_cases(scorer)
    cases = []
    report = {
        "run_id": metadata["run_id"],
        "bundle_sha256": metadata["bundle_sha256"],
        "data": "Three generated label-free fixtures; no reserved-test data",
        "cases": cases,
        "reserved_test_accessed": False,
        "started_at": datetime.now(UTC).isoformat(),
    }
    output = (
        ml_root
        / "reports/task6-application"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    output.mkdir(parents=True, exist_ok=False)
    path = output / "report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def fail(message):
        report["status"] = "FAIL"
        report["failure"] = message
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError(message)

    for action in ("Pass", "Review", "Block"):
        event, features, probability = selected[action]
        key = str(uuid4())
        status, acceptance = request(
            "/api/v1/authorization-events", method="POST", body=event, key=key
        )
        if status != 202 or acceptance.get("outcome") != "accepted":
            fail("Generated application event was not accepted")
        result = terminal(event["event_id"], token)
        case = {
            "event_id": event["event_id"],
            "features": features,
            "expected_action": action,
            "original_result": result,
        }
        cases.append(case)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        expected = {"Pass": "allowed", "Review": "pending_review", "Block": "rejected"}[
            action
        ]
        if (
            result["run_id"] != metadata["run_id"]
            or result["status"] != "scored"
            or result["action"] != action
            or result["execution_state"] != expected
            or not np.isclose(
                result["probability"], probability, rtol=1e-12, atol=1e-12
            )
            or result["thresholds"] != {"review": 0.1, "block": 0.25}
            or result["versions"]["bundle_sha256"] != metadata["bundle_sha256"]
        ):
            fail("Application scoring/execution parity failed")
        duplicate_status, duplicate = request(
            "/api/v1/authorization-events", method="POST", body=event, key=key
        )
        if not is_duplicate_acceptance(duplicate_status, duplicate, acceptance):
            fail("Application idempotent acceptance changed")
        unauthorized, _ = request(f"/api/v1/transactions/{event['event_id']}/result")
        if unauthorized != 401:
            fail("Result authentication check failed")
        if action == "Review":
            resolution = {
                "resolution_id": str(uuid4()),
                "resolution": "allow",
                "notes": "Reviewed generated local-prototype evidence",
            }
            route = f"/api/v1/transactions/{event['event_id']}/review-resolution"
            unauthorized, _ = request(route, method="POST", body=resolution)
            if unauthorized != 401:
                fail("Review authentication check failed")
            resolved, first = request(
                route, method="POST", body=resolution, token=config["REVIEW_API_TOKEN"]
            )
            repeated, second = request(
                route, method="POST", body=resolution, token=config["REVIEW_API_TOKEN"]
            )
            conflict, _ = request(
                route,
                method="POST",
                body={**resolution, "resolution": "reject"},
                token=config["REVIEW_API_TOKEN"],
            )
            if resolved != 201 or repeated != 200 or first != second or conflict != 409:
                fail("Review resolution/idempotency check failed")
            result = terminal(event["event_id"], token)
            if (
                result["action"] != "Review"
                or result["probability"] != case["original_result"]["probability"]
                or result["execution_state"] != "allowed"
                or result["review_resolution"]["reviewer_id"] != config["REVIEWER_ID"]
            ):
                fail("Human resolution changed model evidence")
        case["final_result"] = result
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["status"] = "PASS"
    report["completed_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps({"report": str(path), "actions": list(selected), "status": "PASS"})
    )


if __name__ == "__main__":
    main()
