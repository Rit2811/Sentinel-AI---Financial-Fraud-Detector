import numpy as np
import pandas as pd
import pytest

from fraud_ml.ensemble.evidence import calibration_periods
from fraud_ml.ensemble.probability import (
    ScoreClassifier,
    checked_probability,
    fit_mapping,
    mapped_probability,
    policy_actions,
)
from fraud_ml.ensemble.tradeoffs import policy_table, wilson_interval


@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
def test_mapping_preserves_base_and_round_trips(method, tmp_path):
    import joblib

    scores = np.linspace(-3, 3, 200)
    target = np.tile([0, 0, 0, 1], 50)
    mapper = fit_mapping(scores, target, method)
    probabilities = mapped_probability(mapper, scores)
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    joblib.dump(mapper, tmp_path / "mapping.joblib")
    assert np.array_equal(
        probabilities,
        mapped_probability(joblib.load(tmp_path / "mapping.joblib"), scores),
    )
    with pytest.raises(RuntimeError, match="never be refitted"):
        ScoreClassifier().fit(scores, target)


def test_exact_policy_boundaries_and_full_precision():
    r, b = 0.1, 0.9
    assert policy_actions(
        [np.nextafter(r, 0), r, np.nextafter(b, 0), b], r, b
    ).tolist() == ["Pass", "Review", "Review", "Block"]
    for thresholds in [(0.5, 0.5), (-0.1, 0.7), (0.3, 1.1), (np.nan, 0.9)]:
        with pytest.raises(ValueError):
            policy_actions([0.2], *thresholds)


@pytest.mark.parametrize("values", [[], [np.nan], [np.inf], [-0.1], [1.1], [[0.1]]])
def test_invalid_probabilities_rejected(values):
    with pytest.raises(ValueError):
        checked_probability(values)


def test_tradeoffs_match_direct_actions_including_ties():
    labels = np.array([0, 1, 0, 1, 1, 0, 0, 1])
    scores = np.array([0, 0.1, 0.1, 0.5, 0.9, 0.9, 1, 1])
    times = pd.Series(pd.date_range("2020-03-07", periods=8, freq="h", tz="UTC"))
    for row in policy_table(labels, scores, times):
        actions = policy_actions(scores, row["r"], row["b"])
        for action in ("pass", "review", "block"):
            mask = actions == action.title()
            assert row[action + "_fraud"] == labels[mask].sum()
            assert row[action + "_legitimate"] == (labels[mask] == 0).sum()
        assert row["false_block_rate"] == row["block_legitimate"] / 4
        assert row["feasibility"] == "NOT_ASSESSED_OWNER_LIMITS_MISSING"


def test_zero_errors_still_have_uncertainty():
    lower, upper = wilson_interval(0, 10000)
    assert lower == 0
    assert 0 < upper < 0.001
    assert wilson_interval(0, 0) is None


def test_calendar_segments_are_disjoint_forward_and_have_support():
    times = pd.Series(
        pd.to_datetime(
            ["2019-12-01"] * 200 + ["2020-01-01"] * 200 + ["2020-02-01"] * 200, utc=True
        )
    )
    labels = pd.Series([0, 1] * 300)
    result = calibration_periods(times, labels, np.arange(600))
    assert [len(rows) for rows in result.values()] == [200, 200, 200]
    assert np.array_equal(np.concatenate(list(result.values())), np.arange(600))
    with pytest.raises(ValueError, match="inadequate"):
        calibration_periods(times, pd.Series([0] * 600), np.arange(600))


def test_baseline_inventory_is_verified_before_deserialization(tmp_path):
    import json

    from fraud_ml.data import SOURCE_HASHES
    from fraud_ml.ensemble.config import MODEL_ORDER
    from fraud_ml.ensemble.evidence import verify_baselines
    from fraud_ml.ensemble.reporting import environment_record
    from fraud_ml.features import FEATURE_ORDER, FEATURE_VERSION
    from fraud_ml.sparkov_audit import file_hash

    reports, artifacts = tmp_path / "reports", tmp_path / "artifacts"
    reports.mkdir()
    artifacts.mkdir()
    summary = {
        "status": "completed",
        "feature_version": FEATURE_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "test_partition_evaluated": False,
        "calibration_performed": False,
        "dataset_source": {"pinned_sha256": SOURCE_HASHES},
        "versions": {"sklearn": environment_record()["scikit_learn"]},
        "partitions": {"train": {"rows": 10}},
        "models": {
            name: {
                "status": "completed",
                "fit_warnings": [],
                "training": {"available": {"rows": 10}},
            }
            for name in MODEL_ORDER
        },
    }
    files = {}
    for name in MODEL_ORDER:
        for extension in ("joblib", "calibration.npy", "validation.npy"):
            path = artifacts / f"{name}.{extension}"
            path.write_bytes(b"fixture never deserialized")
            files[path.name] = file_hash(path)
    (reports / "summary.json").write_text(json.dumps(summary))
    (reports / "provenance.json").write_text("{}")
    (reports / "artifact-inventory.json").write_text(json.dumps({"sha256": files}))
    assert verify_baselines(artifacts, reports)[0] == summary
    (artifacts / "random_forest.joblib").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_baselines(artifacts, reports)
    summary["test_partition_evaluated"] = True
    (reports / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="incompatible"):
        verify_baselines(artifacts, reports)
