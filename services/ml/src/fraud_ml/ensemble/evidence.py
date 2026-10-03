"""Development-only Task 5 evidence; cannot freeze, test or activate a policy."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from fraud_ml import data
from fraud_ml.cli import _require_ignored_artifacts
from fraud_ml.evaluation import score_model
from fraud_ml.features import FEATURE_ORDER, FEATURE_VERSION
from fraud_ml.models import validate_features
from fraud_ml.sparkov_audit import file_hash
from fraud_ml.split import chronological_split, partition_summary

from .calibration import probability_metrics
from .config import MODEL_ORDER, EnsembleConfig
from .fusion import optimize_weights
from .probability import fit_mapping, mapped_probability
from .reporting import code_record, environment_record, write_json
from .tradeoffs import policy_table
from .tracks import TRACKS, owns_candidate, track_models, track_root


def calibration_periods(times, labels, calibration):
    """Use calendar periods checked for class coverage, never the reserved test."""
    selected = times.iloc[calibration]
    january, february = (
        pd.Timestamp(date, tz="UTC") for date in ("2020-01-01", "2020-02-01")
    )
    masks = (
        selected < january,
        (selected >= january) & (selected < february),
        selected >= february,
    )
    result = dict(
        zip(
            ("component_calibration", "fusion_weights", "fusion_calibration"),
            (calibration[mask.to_numpy()] for mask in masks),
            strict=True,
        )
    )
    for rows in result.values():
        counts = labels.iloc[rows].value_counts()
        # A coverage guard, not a fraud objective or an operating-policy limit.
        if min(counts.get(0, 0), counts.get(1, 0)) < 100:
            raise ValueError("Calendar calibration period has inadequate class support")
    return result


def verify_baselines(artifact_dir, report_dir):
    summary_path = report_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    provenance = json.loads(
        (report_dir / "provenance.json").read_text(encoding="utf-8")
    )
    inventory = json.loads(
        (report_dir / "artifact-inventory.json").read_text(encoding="utf-8")
    )
    if (
        summary.get("status") != "completed"
        or summary.get("feature_version") != FEATURE_VERSION
        or summary.get("feature_order") != list(FEATURE_ORDER)
        or summary.get("test_partition_evaluated") is not False
        or summary.get("calibration_performed") is not False
        or summary.get("dataset_source", {}).get("pinned_sha256") != data.SOURCE_HASHES
        or summary.get("versions", {}).get("sklearn")
        != environment_record()["scikit_learn"]
    ):
        raise ValueError("Task 4 evidence is incompatible or incomplete")
    expected_files = {
        f"{name}.{extension}"
        for name in MODEL_ORDER
        for extension in ("joblib", "calibration.npy", "validation.npy")
    }
    if set(inventory["sha256"]) != expected_files:
        raise ValueError("Task 4 inventory is incomplete")
    for name, expected in inventory["sha256"].items():
        if file_hash(artifact_dir / name) != expected:
            raise ValueError("Task 4 artifact checksum mismatch")
    for name in MODEL_ORDER:
        model = summary["models"][name]
        if model["status"] != "completed" or model.get("fit_warnings"):
            raise ValueError("Task 4 model is not a clean completed fit")
        if model["training"]["available"] != summary["partitions"]["train"]:
            raise ValueError("Unexpected training exposure")
    return summary, provenance, inventory


def reliability_plot(path, bins, title):
    """Standalone scientific plot; include the bin support rather than hiding it."""
    svg = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width="760",
        height="540",
        viewBox="0 0 760 540",
    )
    ET.SubElement(svg, "rect", width="760", height="540", fill="white")

    def text(x, y, value):
        node = ET.SubElement(
            svg, "text", x=str(x), y=str(y), fill="#222", **{"font-size": "12"}
        )
        node.text = value

    text(35, 25, title + " (development evidence)")
    ET.SubElement(
        svg,
        "line",
        x1="60",
        y1="440",
        x2="460",
        y2="40",
        stroke="#888",
        **{"stroke-dasharray": "5 5"},
    )
    ET.SubElement(svg, "path", d="M60 40 V440 H460", stroke="#222", fill="none")
    for tick in np.linspace(0, 1, 6):
        text(60 + 400 * tick, 460, f"{tick:.1f}")
        text(20, 440 - 400 * tick, f"{tick:.1f}")
    for row in bins:
        if row["count"]:
            ET.SubElement(
                svg,
                "circle",
                cx=str(60 + 400 * row["mean_probability"]),
                cy=str(440 - 400 * row["fraud_rate"]),
                r="4",
                fill="#187e70",
            )
        text(
            500,
            65 + 19 * row["bin"],
            f"[{row['lower']:.2f}, {row['upper']:.2f}]: n={row['count']}",
        )
    text(170, 490, "Mean predicted probability")
    text(60, 520, "Y: observed fraud fraction. Empty bins have no plotted point.")
    ET.ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)


def write_policy_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value) if isinstance(value, list) else value
                    for key, value in row.items()
                }
            )


@threadpool_limits.wrap(limits=1)
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", required=True)
    parser.add_argument("--track", choices=TRACKS, default="all")
    parser.add_argument("--data-dir", type=Path, default=data.DEFAULT_DATA_DIR)
    parser.add_argument(
        "--key-file", type=Path, default=Path("secrets/replay-hmac.key")
    )
    args = parser.parse_args(argv)
    if Path(args.baseline_run).name != args.baseline_run:
        parser.error("baseline-run must be a run identifier, not a path")
    base_artifacts = Path("artifacts/sparkov-v1") / args.baseline_run
    base_reports = Path("reports/sparkov-task4") / args.baseline_run
    summary, provenance, inventory = verify_baselines(base_artifacts, base_reports)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    artifacts = track_root("artifacts/sparkov-task5", args.track) / run_id
    reports = track_root("reports/sparkov-task5", args.track) / run_id
    model_order = track_models(args.track)
    _require_ignored_artifacts(artifacts)
    features, labels, times = data.load_development(
        args.data_dir, data.load_key(args.key_file)
    )
    validate_features(features)
    cache = json.loads(
        (data.CACHE_DIR / "feature-cache.json").read_text(encoding="utf-8")
    )
    if cache != provenance["feature_cache"] or not cache["parity_passed"]:
        raise ValueError(
            "Task 4 feature provenance changed; do not mix baseline exposures"
        )
    train, calibration, comparison = chronological_split(times)
    for name, rows in zip(
        ("train", "calibration", "validation"),
        (train, calibration, comparison),
        strict=True,
    ):
        if (
            partition_summary(labels.iloc[rows], times.iloc[rows])
            != summary["partitions"][name]
        ):
            raise ValueError("Task 4 split exposure mismatch")
    periods = calibration_periods(times, labels, calibration)
    periods = {"base_training": train, **periods, "comparison": comparison}
    manifest = {
        "track": args.track,
        "fitted_component_models": list(model_order),
        "unused_fitting_periods": ["fusion_weights", "fusion_calibration"]
        if args.track == "random-forest"
        else [],
        "baseline_run": args.baseline_run,
        "baseline_summary_sha256": file_hash(base_reports / "summary.json"),
        "baseline_artifacts": inventory,
        "feature_cache": cache,
        "feature_version": FEATURE_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "source_audit": data.verify_audit(),
        "partitions": {
            name: partition_summary(labels.iloc[rows], times.iloc[rows])
            for name, rows in periods.items()
        },
        "boundaries_rationale": "Reuse Task 4 training and later comparison; calendar Jan/Feb boundaries verified for >=100 observations of each class per fitting segment. No prevalence changes.",
        "training": {name: summary["models"][name]["training"] for name in MODEL_ORDER},
        "base_refit": False,
        "test_loaded": False,
        "selection_warning": "Comparison labels are development evidence used for selection, not a new unbiased final evaluation. Task 4 already reported comparison rankings.",
        "calibration_api": "CalibratedClassifierCV(FrozenEstimator(ScoreClassifier()), ensemble=False); unchanged fitted base scores; no CV/refit",
        "seed": 42,
        "environment": environment_record(),
        "code": code_record(),
        "command": [
            "fraud-calibration-develop",
            "--baseline-run",
            args.baseline_run,
            "--track",
            args.track,
        ],
        "dependency_lock_sha256": file_hash(Path("uv.lock")),
    }
    artifacts.mkdir(parents=True, exist_ok=False)
    reports.mkdir(parents=True, exist_ok=False)
    write_json(reports / "split-use.json", manifest)
    report = {
        "track": args.track,
        "run_id": run_id,
        "status": "running",
        "reserved_test": "locked_unscored",
        "gate": "G1_DEVELOPMENT_EVIDENCE",
        "candidates": {},
        "policy_approval": "PENDING_OWNER_LIMITS_AND_SELECTION",
        "frozen_bundle": None,
        "activation_allowed": False,
        "metric_definition": "average_precision is sklearn non-interpolated AP, not trapezoidal PR-AUC",
        "uncertainty": "Wilson 95% binomial intervals are descriptive; synthetic serially dependent transactions are not independent real-bank trials. Zero observed false blocks is not zero future risk.",
    }
    write_json(reports / "summary.json", report)
    calibration_lookup = {int(row): i for i, row in enumerate(calibration)}
    local = {
        name: np.array([calibration_lookup[int(row)] for row in rows])
        for name, rows in periods.items()
        if name not in ("base_training", "comparison")
    }
    methods = ("sigmoid", "isotonic")
    component_values, mappings = {}, {}
    sample_positions = np.linspace(0, len(comparison) - 1, 30, dtype=int)
    sample_features = features.iloc[comparison[sample_positions]]

    def retain(name, probabilities, description, latency):
        target = labels.iloc[comparison].to_numpy()
        evidence = probability_metrics(target, probabilities, bins=20)
        evidence["rows"], evidence["fraud"] = len(target), int(target.sum())
        rows = policy_table(target, probabilities, times.iloc[comparison])
        write_policy_csv(reports / f"{name}.policies.csv", rows)
        reliability_plot(
            reports / f"{name}.reliability.svg", evidence["reliability_bins"], name
        )
        np.save(artifacts / f"{name}.comparison.npy", probabilities, allow_pickle=False)
        report["candidates"][name] = {
            "track_policy_candidate": owns_candidate(args.track, name),
            **description,
            "metrics": evidence,
            "latency": latency,
            "policy_pairs": len(rows),
        }
        write_json(reports / "summary.json", report)
        print(
            f"{name}: AP={evidence['average_precision']:.6f} Brier={evidence['brier_score']:.6f} logloss={evidence['log_loss']:.6f}",
            flush=True,
        )

    for name in model_order:
        print(f"Calibrating verified {name}; no base refit", flush=True)
        base = joblib.load(base_artifacts / f"{name}.joblib")
        raw_cal = np.load(
            base_artifacts / f"{name}.calibration.npy", allow_pickle=False
        )
        raw_comparison = np.load(
            base_artifacts / f"{name}.validation.npy", allow_pickle=False
        )
        if raw_cal.shape != (len(calibration),) or raw_comparison.shape != (
            len(comparison),
        ):
            raise ValueError("Cached scores do not match their split exposure")
        raw_sample = score_model(base, sample_features)
        if not np.allclose(
            raw_sample, raw_comparison[sample_positions], atol=1e-12, rtol=1e-12
        ):
            raise ValueError("Loaded base/cached score parity failed")
        for method in methods:
            mapper = fit_mapping(
                raw_cal[local["component_calibration"]],
                labels.iloc[periods["component_calibration"]],
                method,
            )
            mappings[name, method] = mapper
            probabilities = mapped_probability(mapper, raw_comparison)
            component_values[name, method] = {
                "comparison": probabilities,
                "fusion_weights": mapped_probability(
                    mapper, raw_cal[local["fusion_weights"]]
                ),
                "fusion_calibration": mapped_probability(
                    mapper, raw_cal[local["fusion_calibration"]]
                ),
            }
            latency_ms = []
            for position in range(len(sample_features)):
                started = time.perf_counter()
                output = mapped_probability(
                    mapper, score_model(base, sample_features.iloc[[position]])
                )
                latency_ms.append((time.perf_counter() - started) * 1000)
                if not np.allclose(
                    output,
                    probabilities[sample_positions[position]],
                    atol=1e-12,
                    rtol=1e-12,
                ):
                    raise ValueError("Calibrated in-process reference parity failed")
            joblib.dump(mapper, artifacts / f"{name}.{method}.mapping.joblib")
            retain(
                f"{name}.{method}",
                probabilities,
                {
                    "kind": "calibrated_baseline",
                    "base": name,
                    "calibration": method,
                    "score_input": summary["models"][name]["score_kind"],
                    "base_sha256": inventory["sha256"][f"{name}.joblib"],
                },
                {
                    "scope": "measured sequential single-row preprocessing/base inference/calibration; not end-to-end",
                    "samples": 30,
                    "p50_ms": float(np.percentile(latency_ms, 50)),
                    "p95_ms": float(np.percentile(latency_ms, 95)),
                    "thread_limit": 1,
                },
            )
        del base

    fusion_methods = () if args.track == "random-forest" else methods
    bases = {
        name: joblib.load(base_artifacts / f"{name}.joblib")
        for name in MODEL_ORDER
        if fusion_methods
    }
    for method in fusion_methods:

        def matrix(partition):
            return np.column_stack(
                [component_values[name, method][partition] for name in MODEL_ORDER]
            )

        weights = optimize_weights(
            matrix("fusion_weights"),
            labels.iloc[periods["fusion_weights"]],
            EnsembleConfig(),
        )
        for fusion_method in methods:
            mapper = fit_mapping(
                matrix("fusion_calibration") @ weights,
                labels.iloc[periods["fusion_calibration"]],
                fusion_method,
            )
            candidate = f"fusion.{method}.{fusion_method}"
            probabilities = mapped_probability(mapper, matrix("comparison") @ weights)
            joblib.dump(mapper, artifacts / f"{candidate}.mapping.joblib")
            timings = []
            for index, position in enumerate(sample_positions):
                started = time.perf_counter()
                request = sample_features.iloc[[index]]
                components = np.column_stack(
                    [
                        mapped_probability(
                            mappings[name, method], score_model(bases[name], request)
                        )
                        for name in MODEL_ORDER
                    ]
                )
                output = mapped_probability(mapper, components @ weights)
                timings.append((time.perf_counter() - started) * 1000)
                if not np.allclose(
                    output, probabilities[position], atol=1e-12, rtol=1e-12
                ):
                    raise ValueError(
                        "Four-model inference/cached probability parity failed"
                    )
            retain(
                candidate,
                probabilities,
                {
                    "kind": "four_model_fusion",
                    "component_calibration": method,
                    "fusion_calibration": fusion_method,
                    "model_order": list(MODEL_ORDER),
                    "weights": weights.tolist(),
                    "optimizer": {
                        "loss": "natural-prevalence log loss + L2 to uniform",
                        "regularization": 0.05,
                        "minimum_weight": 0.01,
                    },
                },
                {
                    "scope": "measured sequential single-row four-model preprocessing/inference/component calibration/fusion/final calibration; not end-to-end",
                    "samples": 30,
                    "thread_limit": 1,
                    "p50_ms": float(np.percentile(timings, 50)),
                    "p95_ms": float(np.percentile(timings, 95)),
                    "end_to_end": None,
                },
            )
    report["status"] = "completed_development_evidence"
    policy_candidates = [
        name for name in report["candidates"] if owns_candidate(args.track, name)
    ]
    report["probability_quality_front_runner"] = min(
        policy_candidates,
        key=lambda name: report["candidates"][name]["metrics"]["log_loss"],
    )
    report["ranking_front_runner"] = max(
        policy_candidates,
        key=lambda name: report["candidates"][name]["metrics"]["average_precision"],
    )
    report["serving_recommendation"] = (
        "Pending operating requirements and owner selection; front runners are evidence, not approval. Connected end-to-end latency remains unmeasured."
    )
    write_json(reports / "summary.json", report)
    write_json(
        artifacts / "inventory.json",
        {
            "status": "DEVELOPMENT_ONLY_NOT_FROZEN_NOT_APPROVED",
            "baseline_run": args.baseline_run,
            "sha256": {
                path.name: file_hash(path)
                for path in sorted(artifacts.iterdir())
                if path.is_file()
            },
            "report_sha256": {
                path.name: file_hash(path)
                for path in sorted(reports.iterdir())
                if path.is_file()
            },
        },
    )
    print(
        f"Completed development evidence: {reports}; G2 policy approval remains blocked",
        flush=True,
    )


if __name__ == "__main__":
    main()
