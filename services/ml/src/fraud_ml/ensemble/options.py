"""Assess measured development policies against owner-supplied provisional limits."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fraud_ml.sparkov_audit import file_hash

from .evidence import write_policy_csv
from .reporting import write_json
from .tradeoffs import policy_table
from .tracks import TRACKS, owns_candidate, scoped_requirements, track_root


def constraint_thresholds(labels, probabilities, requirements):
    legitimate = np.sort(probabilities[labels == 0])
    allowed_blocks = int(
        np.floor(len(legitimate) * requirements["maximum_false_block_rate"])
    )
    cutoff = legitimate[max(0, len(legitimate) - allowed_blocks - 1)]
    block = float(np.nextafter(cutoff, 1))
    rate = min(
        requirements["maximum_reviews_per_hour"]
        / (requirements["normal_transactions_per_second"] * 3600),
        requirements["maximum_reviews_per_hour"]
        / (requirements["peak_transactions_per_second"] * 3600),
        requirements["maximum_reviews_per_staffed_day"]
        / (
            requirements["normal_transactions_per_second"]
            * 3600
            * requirements["staffed_hours_per_day"]
        ),
    )
    allowed_reviews = int(np.floor(len(labels) * rate))
    below_block = np.sort(probabilities[probabilities < block])
    review = (
        0.0
        if len(below_block) <= allowed_reviews
        else float(np.nextafter(below_block[-allowed_reviews - 1], 1))
    )
    return [review, block]


def assess(row, requirements):
    result = dict(row)
    rate = float(row["review_rate"])
    normal_hour = rate * requirements["normal_transactions_per_second"] * 3600
    peak_hour = rate * requirements["peak_transactions_per_second"] * 3600
    day = normal_hour * requirements["staffed_hours_per_day"]
    violations = []
    for key, actual, limit in (
        ("normal_review_hour", normal_hour, requirements["maximum_reviews_per_hour"]),
        ("peak_review_hour", peak_hour, requirements["maximum_reviews_per_hour"]),
        (
            "staffed_normal_review_day",
            day,
            requirements["maximum_reviews_per_staffed_day"],
        ),
        (
            "false_block_rate",
            float(row["false_block_rate"]),
            requirements["maximum_false_block_rate"],
        ),
    ):
        if actual > limit:
            violations.append(key)
    if float(row["fraud_routed_rate"]) < requirements["minimum_fraud_routed_rate"]:
        violations.append("minimum_fraud_routed_rate")
    result.update(
        {
            "estimated_normal_reviews_per_hour": normal_hour,
            "estimated_peak_reviews_per_hour": peak_hour,
            "estimated_staffed_normal_reviews_per_day": day,
            "violations": violations,
            "feasibility": "PROVISIONAL_TARGETS_MET"
            if not violations
            else "PROVISIONAL_TARGETS_NOT_MET",
            "preferred_capture_met": float(row["fraud_routed_rate"])
            >= requirements["preferred_fraud_routed_rate"],
        }
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-run", required=True)
    parser.add_argument("--track", choices=TRACKS, default="all")
    parser.add_argument(
        "--source-track",
        choices=TRACKS,
        help="Evidence location; defaults to --track. Use all for legacy combined runs.",
    )
    parser.add_argument("--requirements", required=True, type=Path)
    args = parser.parse_args(argv)
    if Path(args.evidence_run).name != args.evidence_run:
        parser.error("evidence-run must be a run identifier")
    source_track = args.source_track or args.track
    if source_track != "all" and source_track != args.track:
        parser.error("A dedicated source track cannot feed another track")
    evidence = track_root("reports/sparkov-task5", source_track) / args.evidence_run
    inventory_path = (
        track_root("artifacts/sparkov-task5", source_track)
        / args.evidence_run
        / "inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for name, expected in inventory["report_sha256"].items():
        if Path(name).name != name or file_hash(evidence / name) != expected:
            raise ValueError("Development evidence checksum mismatch")
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    if (
        summary["status"] != "completed_development_evidence"
        or summary["reserved_test"] != "locked_unscored"
        or summary.get("track", "all") != source_track
    ):
        raise ValueError("Complete development-only evidence is required")
    requirements = scoped_requirements(
        json.loads(args.requirements.read_text(encoding="utf-8")), args.track
    )
    candidates = {
        name: candidate
        for name, candidate in summary["candidates"].items()
        if owns_candidate(args.track, name)
    }
    if not candidates:
        raise ValueError("Evidence has no candidates for the requested track")
    for key in (
        "normal_transactions_per_second",
        "peak_transactions_per_second",
        "maximum_reviews_per_hour",
        "maximum_reviews_per_staffed_day",
        "staffed_hours_per_day",
    ):
        if (
            not isinstance(requirements.get(key), (float, int))
            or requirements[key] <= 0
        ):
            raise ValueError(
                "Explicit positive owner traffic/capacity requirements are needed"
            )
    for key in (
        "maximum_false_block_rate",
        "minimum_fraud_routed_rate",
        "preferred_fraud_routed_rate",
    ):
        if (
            not isinstance(requirements.get(key), (float, int))
            or not 0 <= requirements[key] <= 1
        ):
            raise ValueError("Explicit owner rate requirements in [0, 1] are needed")
    split = json.loads((evidence / "split-use.json").read_text(encoding="utf-8"))
    cache_path = Path("artifacts/sparkov-v1/development-features.npz")
    if file_hash(cache_path) != split["feature_cache"]["cache_sha256"]:
        raise ValueError("Development cache evidence mismatch")
    with np.load(cache_path, allow_pickle=False) as cache:
        times = pd.Series(pd.to_datetime(cache["times"], utc=True))
        start = pd.Timestamp(split["partitions"]["comparison"]["date_min"])
        selected = times >= start
        labels = cache["labels"][selected.to_numpy()]
        comparison_times = times[selected].reset_index(drop=True)
    output = track_root("reports/sparkov-policy-options", args.track) / datetime.now(
        UTC
    ).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "track": args.track,
        "source_track": source_track,
        "status": "PROPOSALS_ONLY_OWNER_APPROVAL_REQUIRED",
        "evidence_run": args.evidence_run,
        "evidence_inventory_sha256": file_hash(inventory_path),
        "requirements": requirements,
        "requirements_sha256": file_hash(args.requirements),
        "traffic_assumption": "Development review fraction scaled to supplied traffic; peak/hour constraint also checked. Day estimate assumes normal traffic during the supplied 8 staffed hours. Peak duration and real arrival distribution remain unspecified. Static thresholds do not cap queues.",
        "search_scope": "Finite score quantiles, explicit boundaries and capacity/false-block critical score cutoffs. Tied scores are never split. Proposals use full-precision float64 values.",
        "proposal_order": "Prefer capture >= preferred target, then higher routed fraud, fewer legitimate blocks and lower review volume. This comparison ordering is proposed, not an approved financial objective.",
        "activation_allowed": False,
        "reserved_test": "locked_unscored",
        "candidates": {},
    }
    for name, candidate in candidates.items():
        artifact_dir = inventory_path.parent
        probability_path = artifact_dir / f"{name}.comparison.npy"
        if file_hash(probability_path) != inventory["sha256"][probability_path.name]:
            raise ValueError("Comparison probability checksum mismatch")
        probabilities = np.load(probability_path, allow_pickle=False)
        rows = [
            assess(row, requirements)
            for row in policy_table(
                labels,
                probabilities,
                comparison_times,
                constraint_thresholds(labels, probabilities, requirements),
            )
        ]
        write_policy_csv(output / f"{name}.assessed.csv", rows)
        feasible = [row for row in rows if not row["violations"]]
        feasible.sort(
            key=lambda row: (
                not row["preferred_capture_met"],
                -float(row["fraud_routed_rate"]),
                float(row["false_block_rate"]),
                float(row["review_rate"]),
            )
        )
        report["candidates"][name] = {
            "searched_pairs": len(rows),
            "feasible_pairs": len(feasible),
            "proposed_pair": feasible[0] if feasible else None,
            "probability_metrics": candidate["metrics"],
            "latency": candidate["latency"],
        }
    write_json(output / "summary.json", report)
    write_json(output / "requirements.json", requirements)
    print(output, flush=True)
    for name, evidence in report["candidates"].items():
        pair = evidence["proposed_pair"]
        if pair:
            print(
                f"{name}: {evidence['feasible_pairs']} feasible pairs; proposed r={pair['r']} b={pair['b']} capture={float(pair['fraud_routed_rate']):.4%} false blocks={float(pair['false_block_rate']):.4%} peak reviews/h={pair['estimated_peak_reviews_per_hour']:.2f}",
                flush=True,
            )
        else:
            print(f"{name}: no searched pair met provisional limits", flush=True)


if __name__ == "__main__":
    main()
