"""Verified RF package loading. Loading alone never authorizes test or activation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .features import FEATURE_ORDER, FeatureStream
from .ensemble.probability import mapped_probability, policy_actions


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runtime_versions():
    return {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(name)
            for name in (
                "numpy",
                "pandas",
                "scipy",
                "scikit-learn",
                "joblib",
                "threadpoolctl",
            )
        },
    }


def verify_manifest(root, expected_sha256):
    root = Path(root).resolve()
    path = root / "manifest.json"
    if len(expected_sha256) != 64 or sha256(path) != expected_sha256:
        raise ValueError("Package manifest checksum mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_PENDING_RESERVED_TEST":
        raise ValueError("Unsupported package status")
    required = {
        "model.joblib",
        "calibrator.joblib",
        "policy.json",
        "references.json",
        "uv.lock",
        "feature-contract.md",
        "src/fraud_ml/serving.py",
        "src/fraud_ml/features.py",
        "src/fraud_ml/ensemble/probability.py",
    }
    if not required <= manifest["files"].keys():
        raise ValueError("Incomplete package inventory")
    for name, expected in manifest["files"].items():
        file = (root / name).resolve()
        if not file.is_relative_to(root) or file == root or sha256(file) != expected:
            raise ValueError("Package file checksum mismatch")
    if manifest["runtime"] != runtime_versions():
        raise ValueError("Package requires matching runtime versions")
    return manifest


class FrozenScorer:
    def __init__(self, root, expected_sha256):
        self.root = Path(root).resolve()
        self.manifest = verify_manifest(self.root, expected_sha256)
        # Ensure the executing feature/scoring implementation matches packaged code.
        code_root = Path(__file__).parent
        for relative in ("serving.py", "features.py", "ensemble/probability.py"):
            if (
                sha256(code_root / relative)
                != self.manifest["files"][f"src/fraud_ml/{relative}"]
            ):
                raise ValueError("Executing code differs from frozen implementation")
        self.policy = json.loads(
            (self.root / "policy.json").read_text(encoding="utf-8")
        )
        if (
            self.policy["status"]
            != "owner_approved_for_freeze_reserved_test_not_authorized"
            or self.policy["selected_scorer"] != "random_forest.sigmoid"
            or not self.policy["final_test_criteria_approved"]
        ):
            raise ValueError("Package policy lacks freeze approval")
        self.r, self.b = self.policy["review_threshold"], self.policy["block_threshold"]
        policy_actions([0], self.r, self.b)
        # Only trusted local artifacts with an externally supplied manifest pin.
        self.model = joblib.load(self.root / "model.joblib")
        self.calibrator = joblib.load(self.root / "calibrator.joblib")

    def score(self, features):
        if not features or any(set(row) != set(FEATURE_ORDER) for row in features):
            raise ValueError("Scoring accepts only the label-free feature contract")
        frame = pd.DataFrame(features, columns=FEATURE_ORDER)
        probabilities = mapped_probability(
            self.calibrator, self.model.predict_proba(frame)[:, 1]
        )
        return probabilities, policy_actions(probabilities, self.r, self.b)

    def verify_references(self):
        references = json.loads(
            (self.root / "references.json").read_text(encoding="utf-8")
        )
        stream = FeatureStream()
        for case in references["history_cases"]:
            if stream.transform(case["event"]) != case["features"]:
                raise ValueError("Frozen history reference mismatch")
        cases = references["score_cases"]
        probabilities, actions = self.score([case["features"] for case in cases])
        if not np.allclose(
            probabilities,
            [case["probability"] for case in cases],
            rtol=1e-12,
            atol=1e-12,
        ):
            raise ValueError("Frozen probability reference mismatch")
        if actions.tolist() != [case["action"] for case in cases]:
            raise ValueError("Frozen action reference mismatch")
        if policy_actions(
            [np.nextafter(self.r, 0), self.r, self.b], self.r, self.b
        ).tolist() != ["Pass", "Review", "Block"]:
            raise ValueError("Frozen policy boundary mismatch")
        return {
            "history_cases": len(references["history_cases"]),
            "score_cases": len(cases),
            "probability_tolerance": 1e-12,
            "exact_policy_boundaries": "passed",
        }
