"""Freeze approved RF development artifacts; never open the reserved test."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import joblib
import numpy as np
import pandas as pd

from .cli import _require_ignored_artifacts
from .features import FEATURE_ORDER, NUMERIC_FEATURES, FEATURE_VERSION, FeatureStream
from .ensemble.evidence import verify_baselines
from .ensemble.probability import mapped_probability, policy_actions
from .ensemble.reporting import code_record, write_json
from .serving import FrozenScorer, runtime_versions, sha256


def require_approval(policy):
    if (
        policy.get("status") != "owner_approved_for_freeze_reserved_test_not_authorized"
        or policy.get("selected_scorer") != "random_forest.sigmoid"
        or policy.get("review_threshold") != 0.1
        or policy.get("block_threshold") != 0.25
        or not policy.get("policy_approver")
        or not policy.get("policy_approval_timestamp")
        or not policy.get("policy_version")
        or not policy.get("final_test_criteria_approved")
        or policy.get("reserved_test_authorized") is not False
    ):
        raise ValueError("Explicit RF policy/criteria freeze approval required")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-run", required=True)
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args(argv)
    if Path(args.evidence_run).name != args.evidence_run:
        parser.error("evidence-run must be a run identifier")
    policy = json.loads(args.approval.read_text(encoding="utf-8"))
    require_approval(policy)
    artifacts = Path("artifacts/sparkov-task5/random-forest") / args.evidence_run
    reports = Path("reports/sparkov-task5/random-forest") / args.evidence_run
    inventory = json.loads((artifacts / "inventory.json").read_text(encoding="utf-8"))
    for section, root in (("sha256", artifacts), ("report_sha256", reports)):
        for name, expected in inventory[section].items():
            if Path(name).name != name or sha256(root / name) != expected:
                raise ValueError("Development evidence checksum mismatch")
    summary = json.loads((reports / "summary.json").read_text(encoding="utf-8"))
    if (
        summary["status"] != "completed_development_evidence"
        or summary["reserved_test"] != "locked_unscored"
    ):
        raise ValueError("Completed development evidence required")
    baseline = inventory["baseline_run"]
    base = Path("artifacts/sparkov-v1") / baseline
    base_reports = Path("reports/sparkov-task4") / baseline
    verify_baselines(base, base_reports)
    split = json.loads((reports / "split-use.json").read_text(encoding="utf-8"))
    cache = Path("artifacts/sparkov-v1/development-features.npz")
    if sha256(cache) != split["feature_cache"]["cache_sha256"]:
        raise ValueError("Development feature cache checksum mismatch")
    model = joblib.load(base / "random_forest.joblib")
    calibrator = joblib.load(artifacts / "random_forest.sigmoid.mapping.joblib")
    expected = np.load(
        artifacts / "random_forest.sigmoid.comparison.npy", allow_pickle=False
    )
    actions = policy_actions(
        expected, policy["review_threshold"], policy["block_threshold"]
    )
    positions = set(np.linspace(0, len(expected) - 1, 30, dtype=int).tolist())
    for action in ("Pass", "Review", "Block"):
        positions.add(int(np.flatnonzero(actions == action)[0]))
    with np.load(cache, allow_pickle=False) as stored:
        # Read no labels, and no reserved-test files. Only safe development features.
        frame = pd.DataFrame(
            stored["numeric"][-len(expected) :], columns=NUMERIC_FEATURES
        )
        frame["merchant_category"] = stored["category"][-len(expected) :]
    positions = sorted(positions)
    values = mapped_probability(
        calibrator, model.predict_proba(frame.iloc[positions])[:, 1]
    )
    if not np.allclose(values, expected[positions], rtol=1e-12, atol=1e-12):
        raise ValueError("Original development reference parity failed")
    cases = [
        {
            "features": frame.iloc[pos].to_dict(),
            "probability": float(expected[pos]),
            "action": str(actions[pos]),
            "source": "label-free development feature snapshot",
        }
        for pos in positions
    ]
    history_cases, stream = [], FeatureStream()
    for index, offset in enumerate((0, 0, 1, 3600, 3601, 86400, 86401)):
        event = {
            "schema_version": "2.0",
            "data_origin": "sparkov_replay",
            "event_id": str(uuid5(NAMESPACE_URL, f"sentinel:reference:{index}")),
            "authorization_id": str(
                uuid5(NAMESPACE_URL, f"sentinel:reference:auth:{index}")
            ),
            "occurred_at": (
                datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=offset)
            )
            .isoformat()
            .replace("+00:00", "Z"),
            "amount_minor": 1234 + index,
            "currency": "USD",
            "card_token": "card_" + "a" * 64,
            "merchant_id": "merchant_" + "b" * 64,
            "merchant_category": "reference_unseen_category",
            "time_basis": "source_wall_clock_as_utc",
            "currency_basis": "simulation_assumption",
        }
        features = stream.transform(event)
        history_cases.append({"event": event, "features": features})
        p = float(
            mapped_probability(
                calibrator,
                model.predict_proba(pd.DataFrame([features], columns=FEATURE_ORDER))[
                    :, 1
                ],
            )[0]
        )
        cases.append(
            {
                "features": features,
                "probability": p,
                "action": str(
                    policy_actions(
                        [p], policy["review_threshold"], policy["block_threshold"]
                    )[0]
                ),
                "source": "synthetic reference with history preconditions in history_cases",
            }
        )
    output = Path("artifacts/frozen/random-forest") / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    _require_ignored_artifacts(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(base / "random_forest.joblib", output / "model.joblib")
    shutil.copy2(
        artifacts / "random_forest.sigmoid.mapping.joblib", output / "calibrator.joblib"
    )
    for name in ("uv.lock", "pyproject.toml"):
        shutil.copy2(name, output / name)
    for file in Path("src/fraud_ml").rglob("*.py"):
        destination = output / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
    shutil.copy2("../../docs/feature-contract.md", output / "feature-contract.md")
    shutil.copy2(reports / "split-use.json", output / "split-use.json")
    shutil.copy2(reports / "summary.json", output / "development-summary.json")
    shutil.copy2(artifacts / "inventory.json", output / "development-inventory.json")
    write_json(output / "policy.json", policy)
    write_json(
        output / "references.json",
        {
            "history_initial_state": "empty",
            "history_cases": history_cases,
            "score_cases": cases,
        },
    )
    manifest = {
        "status": "FROZEN_PENDING_RESERVED_TEST",
        "scorer": "random_forest.sigmoid",
        "feature_version": FEATURE_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "runtime": runtime_versions(),
        "code": code_record(),
        "baseline_run": baseline,
        "evidence_run": args.evidence_run,
        "reserved_test_accessed": False,
        "activation_allowed": False,
        "approval_sha256": sha256(args.approval),
        "hash_procedure": "SHA256 of exact UTF-8 canonical manifest bytes (sorted keys, compact separators); manifest excluded from its own files",
        "files": {
            p.relative_to(output).as_posix(): sha256(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    checksum = sha256(output / "manifest.json")
    verification = FrozenScorer(output, checksum).verify_references()
    print(
        json.dumps(
            {
                "package": str(output.resolve()),
                "manifest_sha256": checksum,
                "reference_verification": verification,
                "reserved_test": "LOCKED",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
