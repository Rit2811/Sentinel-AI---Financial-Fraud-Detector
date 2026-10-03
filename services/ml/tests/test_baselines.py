import json
import warnings

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

from fraud_ml import cli
from fraud_ml.evaluation import (
    all_legitimate_metrics,
    evaluate_model,
    score_metrics,
    score_model,
)
from fraud_ml.features import FEATURE_ORDER, NUMERIC_FEATURES
from fraud_ml.models import build_models, reduce_knn_majority, validate_features
from fraud_ml.split import chronological_split, partition_summary, split_boundaries


def synthetic(rows=200):
    rng = np.random.default_rng(42)
    features = pd.DataFrame(
        {name: rng.uniform(0, 10, rows) for name in NUMERIC_FEATURES}
    )
    features["merchant_category"] = [
        "grocery" if i % 2 else "travel" for i in range(rows)
    ]
    labels = pd.Series((np.arange(rows) % 7 == 0).astype(int), name="is_fraud")
    times = pd.Series(pd.date_range("2020-01-01", periods=rows, freq="s", tz="UTC"))
    return features, labels, times


@pytest.mark.parametrize("name", list(build_models()))
def test_preprocessing_is_fitted_on_training_only_and_handles_unknown_category(name):
    features, labels, _ = synthetic(50)
    training, future = features.iloc[:30].copy(), features.iloc[30:].copy()
    future["merchant_category"] = "unseen"
    future["amount"] = 1_000_000
    model = build_models()[name]
    model.fit(training, labels.iloc[:30])
    preprocessor = model.named_steps["preprocessor"]
    encoder = preprocessor.named_transformers_["category"]
    scaler = preprocessor.named_transformers_["numeric"]
    assert set(encoder.categories_[0]) == {"grocery", "travel"}
    assert encoder.handle_unknown == "ignore"
    assert encoder.sparse_output is False
    np.testing.assert_allclose(
        scaler.center_, training[list(NUMERIC_FEATURES)].median()
    )
    center = scaler.center_.copy()
    transformed = preprocessor.transform(future)
    assert np.all(transformed[:, len(NUMERIC_FEATURES) :] == 0)
    assert np.isfinite(score_model(model, future)).all()
    np.testing.assert_array_equal(scaler.center_, center)
    assert tuple(model.feature_names_in_) == FEATURE_ORDER


def test_chronological_ties_use_positions_and_preserve_loader_order():
    seconds = [7, 5, 0, 9, 1, 5, 2, 7, 3, 4]
    times = pd.Series(
        pd.to_datetime(seconds, unit="s", utc=True), index=range(100, 110)
    )
    train, calibration, validation = chronological_split(times)
    assert train.tolist() == [2, 4, 6, 8, 9, 1, 5]
    assert calibration.tolist() == [0, 7]
    assert validation.tolist() == [3]
    assert times.iloc[train].max() < times.iloc[calibration].min()
    assert times.iloc[calibration].max() < times.iloc[validation].min()
    assert sorted(np.concatenate([train, calibration, validation])) == list(range(10))


def test_default_split_and_partition_evidence():
    _, labels, times = synthetic(100)
    parts = chronological_split(times)
    assert [len(part) for part in parts] == [60, 20, 20]
    summary = partition_summary(labels.iloc[parts[0]], times.iloc[parts[0]])
    assert summary == {
        "rows": 60,
        "class_counts": {"0": 51, "1": 9},
        "date_min": times.iloc[0].isoformat(),
        "date_max": times.iloc[59].isoformat(),
    }


def test_split_rejects_unsplittable_groups_invalid_times_and_fractions():
    _, _, times = synthetic(10)
    with pytest.raises(ValueError, match="nonempty partitions"):
        chronological_split(pd.Series([times.iloc[0]] * 10))
    with pytest.raises(ValueError, match="sorted"):
        split_boundaries(times.iloc[::-1])
    with pytest.raises(ValueError, match="Fractions"):
        chronological_split(times, 0.9, 0.2)
    with pytest.raises(ValueError, match="non-null"):
        chronological_split(pd.Series([pd.NaT], dtype="datetime64[ns]"))
    with pytest.raises(ValueError, match="datetime"):
        chronological_split(pd.Series(range(10)))


@pytest.mark.parametrize(
    "extra", ["is_fraud", "Class", "cc_num", "trans_num", "event_time"]
)
def test_noncontract_columns_are_rejected_before_fit(extra):
    features, labels, _ = synthetic(20)
    features[extra] = labels
    model = build_models()["logistic_regression"]
    with pytest.raises(ValueError, match="FEATURE_ORDER"):
        evaluate_model(model, features, labels, features, labels)
    assert not hasattr(model.named_steps["preprocessor"], "transformers_")


def test_feature_order_is_required():
    features, _, _ = synthetic(10)
    with pytest.raises(ValueError, match="FEATURE_ORDER"):
        validate_features(features.iloc[:, ::-1])


def test_knn_sampling_caps_only_training_majority_and_is_repeatable():
    features, _, _ = synthetic(10_100)
    labels = pd.Series([0] * 10_050 + [1] * 50)
    sampled_x, sampled_y = reduce_knn_majority(features, labels)
    repeated_x, repeated_y = reduce_knn_majority(features, labels)
    assert sampled_y.value_counts().to_dict() == {0: 10_000, 1: 50}
    assert set(labels[labels == 1].index) <= set(sampled_y.index)
    assert sampled_x.index.is_monotonic_increasing
    pd.testing.assert_frame_equal(sampled_x, repeated_x)
    pd.testing.assert_series_equal(sampled_y, repeated_y)
    assert len(features) == 10_100


def test_all_legitimate_metrics_and_single_class_metrics_are_explicit():
    result = all_legitimate_metrics(pd.Series([0, 0, 0, 1]))
    assert result["confusion"] == {"tn": 3, "fp": 0, "fn": 1, "tp": 0}
    assert result["average_precision"] == result["pr_auc"] == 0.25
    assert result["precision"] == result["recall"] == result["false_positives"] == 0
    assert result["roc_auc"] == 0.5
    assert result["accuracy"] == 0.75
    legitimate_only = all_legitimate_metrics(pd.Series([0, 0]))
    assert legitimate_only["average_precision"] is None
    assert legitimate_only["roc_auc"] is None
    assert legitimate_only["confusion"] == {"tn": 2, "fp": 0, "fn": 0, "tp": 0}
    assert score_metrics([0, 1], [0.9, 0.9])["false_positives"] == 1
    json.dumps(legitimate_only, allow_nan=False)


def test_convergence_warning_fails_without_scoring_or_saving(monkeypatch, tmp_path):
    features, labels, _ = synthetic(20)
    model = build_models()["logistic_regression"]

    def warn_on_fit(*args):
        warnings.warn("Synthetic iteration limit", ConvergenceWarning)
        return model

    monkeypatch.setattr(model, "fit", warn_on_fit)
    result = evaluate_model(
        model,
        features,
        labels,
        features,
        labels,
        validation_scores_path=tmp_path / "scores.npy",
    )
    assert result["status"] == "failed_convergence"
    assert result["fit_warnings"] == [
        {
            "category": "ConvergenceWarning",
            "message": "Synthetic iteration limit",
        }
    ]
    assert "average_precision" not in result
    assert not (tmp_path / "scores.npy").exists()


def test_cli_synthetic_run_uses_only_development_and_saves_incrementally(
    monkeypatch, tmp_path
):
    features, labels, times = synthetic()
    features.loc[120:, "merchant_category"] = "future_only"
    key_file = tmp_path / "key"
    dataset_dir = tmp_path / "source"
    calls = []

    def load_key(path, *, create):
        assert path == key_file and create is True
        return b"synthetic-key"

    def load_development(path, key):
        calls.append((path, key))
        return features, labels, times

    monkeypatch.setattr(cli.data, "load_key", load_key)
    monkeypatch.setattr(cli.data, "load_development", load_development)
    monkeypatch.setattr(cli, "_require_ignored_artifacts", lambda path: None)
    monkeypatch.setattr(cli, "record_run_provenance", lambda path: None)
    original_write = cli._write_json
    written_models = []

    def write(path, payload):
        if path.name == "summary.json":
            written_models.append(len(payload["models"]))
        original_write(path, payload)

    monkeypatch.setattr(cli, "_write_json", write)
    cli.baseline_main(
        [
            "--data-dir",
            str(dataset_dir),
            "--key-file",
            str(key_file),
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )
    assert calls == [(dataset_dir, b"synthetic-key")]
    (summary_path,) = (tmp_path / "reports").glob("*/summary.json")
    report = json.loads(summary_path.read_text())
    assert report["status"] == "completed"
    assert report["calibration_performed"] is False
    assert report["test_partition_evaluated"] is False
    assert report["supplied_test"]["status"] == "locked_unscored"
    assert written_models == [0, 1, 2, 3, 4, 4]
    assert [part["rows"] for part in report["partitions"].values()] == [120, 40, 40]
    for name, result in report["models"].items():
        model = joblib.load(result["model_artifact"])
        encoder = model.named_steps["preprocessor"].named_transformers_["category"]
        assert "future_only" not in encoder.categories_[0]
        assert result["training"]["fitted_rows"] == 120
        assert result["latency"]["single_request_rows"] == 30
        assert (
            0
            <= result["latency"]["single_request_p50_ms"]
            <= result["latency"]["single_request_p95_ms"]
        )
        for partition in ("calibration", "validation"):
            scores = np.load(result["raw_scores"][partition], allow_pickle=False)
            assert scores.shape == (40,)
        assert (summary_path.parent / f"{name}.json").is_file()


def test_artifacts_must_be_ignored(monkeypatch, tmp_path):
    class Unignored:
        returncode = 1

    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: Unignored())
    with pytest.raises(ValueError, match="Git-ignored"):
        cli._require_ignored_artifacts(tmp_path)
