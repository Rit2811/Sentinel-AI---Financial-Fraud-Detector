from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from fraud_ml.ensemble.artifacts import verify_checksums, write_checksums
from fraud_ml.ensemble.calibration import raw_scores
from fraud_ml.ensemble.config import (
    DATASET_SHA256,
    FEATURE_ORDER,
    MODEL_ORDER,
    SPLIT_IMPLEMENTATION_BLOB,
    SPLIT_VERSION,
    EnsembleConfig,
)
from fraud_ml.ensemble.reporting import json_safe, write_json


def preprocessing_record(model) -> dict:
    steps = []
    if hasattr(model, "steps"):
        steps = [
            {
                "name": name,
                "class": f"{step.__class__.__module__}.{step.__class__.__name__}",
            }
            for name, step in model.steps
        ]
    else:
        steps = [
            {
                "name": "estimator",
                "class": f"{model.__class__.__module__}.{model.__class__.__name__}",
            }
        ]
    return {
        "feature_order": list(getattr(model, "feature_names_in_", ())),
        "feature_count": int(getattr(model, "n_features_in_", len(FEATURE_ORDER))),
        "steps": steps,
    }


def expected_bundle_files() -> set[str]:
    files = {
        "manifest.json",
        "feature_contract.json",
        "fusion.json",
        "decision_policy.json",
        "development_config.json",
        "validation_scores.npz",
    }
    for name in MODEL_ORDER:
        files.add(f"models/{name}.joblib")
        files.add(f"calibrators/{name}.joblib")
        files.add(f"preprocessing/{name}.json")
    return files


def package_development_bundle(
    root: Path,
    models,
    fusion,
    profiles,
    recommended_profile,
    validation_y,
    config: EnsembleConfig,
    partition_record,
    environment,
    code,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("models", "calibrators", "preprocessing"):
        (root / directory).mkdir(exist_ok=True)

    for name in MODEL_ORDER:
        joblib.dump(models[name].base_model, root / "models" / f"{name}.joblib")
        joblib.dump(
            models[name].calibrator,
            root / "calibrators" / f"{name}.joblib",
        )
        write_json(
            root / "preprocessing" / f"{name}.json",
            preprocessing_record(models[name].base_model),
        )

    fusion_record = {
        "algorithm": fusion["selected_fusion"],
        "model_order": list(MODEL_ORDER),
        "weights": fusion["selected_weights"],
        "constraints": {
            "non_negative": True,
            "sum_to_one": True,
            "minimum_weight": config.minimum_fusion_weight,
            "regularization": config.fusion_regularization,
        },
    }
    decision_policy = {
        "status": "AWAITING_M4_PROFILE_SELECTION",
        "selected_profile": None,
        "recommended_profile": recommended_profile,
        "profiles": profiles,
        "rule": {
            "block": "probability >= block_threshold",
            "review": "review_threshold <= probability < block_threshold",
            "allow": "probability < review_threshold",
        },
    }
    feature_contract = {
        "schema_version": "ulb-feature-contract-v1",
        "feature_order": list(FEATURE_ORDER),
        "feature_count": len(FEATURE_ORDER),
        "target": "Class",
        "target_in_inference": False,
        "synthetic_smoke_row": {
            feature: 1.0 if feature == "Amount" else 0.0 for feature in FEATURE_ORDER
        },
    }
    manifest = {
        "bundle_schema_version": config.bundle_schema_version,
        "status": "DEVELOPMENT_NOT_FROZEN",
        "dataset": {"sha256": DATASET_SHA256},
        "split": {
            "version": SPLIT_VERSION,
            "implementation_blob": SPLIT_IMPLEMENTATION_BLOB,
            "partitions": partition_record,
        },
        "models": list(MODEL_ORDER),
        "calibration": {
            name: models[name].evidence["selected_method"] for name in MODEL_ORDER
        },
        "fusion": fusion_record,
        "policy_status": decision_policy["status"],
        "environment": environment,
        "code": code,
        "expected_files": sorted(expected_bundle_files()),
    }

    write_json(root / "development_config.json", config.to_dict())
    write_json(root / "feature_contract.json", feature_contract)
    write_json(root / "fusion.json", fusion_record)
    write_json(root / "decision_policy.json", decision_policy)
    write_json(root / "manifest.json", manifest)
    np.savez_compressed(
        root / "validation_scores.npz",
        target=np.asarray(validation_y, dtype=np.int8),
        selected_fusion=np.asarray(fusion["selected_scores"], dtype=float),
        base_probabilities=np.asarray(fusion["base_validation_matrix"], dtype=float),
    )
    checksums = write_checksums(root)
    verify_bundle(root)
    return checksums


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_bundle(root: Path) -> dict:
    checksums = verify_checksums(root)
    expected = expected_bundle_files()
    if set(checksums) != expected:
        missing = sorted(expected - set(checksums))
        unexpected = sorted(set(checksums) - expected)
        raise ValueError(
            f"Bundle contract mismatch; missing={missing}, unexpected={unexpected}"
        )

    manifest = _read_json(root / "manifest.json")
    feature_contract = _read_json(root / "feature_contract.json")
    fusion = _read_json(root / "fusion.json")
    policy = _read_json(root / "decision_policy.json")
    if manifest.get("bundle_schema_version") != EnsembleConfig().bundle_schema_version:
        raise ValueError("Bundle schema version is incompatible")
    if manifest.get("expected_files") != sorted(expected):
        raise ValueError("Manifest file inventory is incompatible")
    if feature_contract.get("feature_order") != list(FEATURE_ORDER):
        raise ValueError("Feature contract order is incompatible")
    if fusion.get("model_order") != list(MODEL_ORDER):
        raise ValueError("Fusion model order is incompatible")
    weights = np.asarray([fusion["weights"][name] for name in MODEL_ORDER], dtype=float)
    if np.any(weights < 0) or not np.isclose(weights.sum(), 1, atol=1e-10):
        raise ValueError("Fusion weights are incompatible")
    if policy.get("status") != "AWAITING_M4_PROFILE_SELECTION":
        raise ValueError("Development bundle unexpectedly contains a frozen policy")
    for name in MODEL_ORDER:
        preprocessing = _read_json(root / "preprocessing" / f"{name}.json")
        if preprocessing.get("feature_order") != list(FEATURE_ORDER):
            raise ValueError(f"Preprocessing feature order is incompatible: {name}")
    return checksums


def smoke_score(root: Path) -> dict:
    verify_bundle(root)
    feature_contract = _read_json(root / "feature_contract.json")
    fusion = _read_json(root / "fusion.json")
    features = pd.DataFrame(
        [feature_contract["synthetic_smoke_row"]],
        columns=feature_contract["feature_order"],
    )
    probabilities = {}
    for name in MODEL_ORDER:
        model = joblib.load(root / "models" / f"{name}.joblib")
        calibrator = joblib.load(root / "calibrators" / f"{name}.joblib")
        probability = float(calibrator.predict(raw_scores(model, features))[0])
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError(f"Synthetic smoke probability is invalid: {name}")
        probabilities[name] = probability
    fused = float(
        sum(probabilities[name] * fusion["weights"][name] for name in MODEL_ORDER)
    )
    if not np.isfinite(fused) or not 0 <= fused <= 1:
        raise ValueError("Synthetic fused probability is invalid")
    return json_safe(
        {
            "status": "PASS",
            "contains_target": "Class" in features.columns,
            "base_probabilities": probabilities,
            "fused_probability": fused,
        }
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify and smoke-score a trusted local ensemble bundle."
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path("artifacts/model-bundles/ensemble-development-v1"),
    )
    args = parser.parse_args(argv)
    print(json.dumps(smoke_score(args.bundle_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
