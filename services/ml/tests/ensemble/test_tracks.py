from pathlib import Path

import pytest

from fraud_ml.ensemble.config import MODEL_ORDER
from fraud_ml.ensemble.options import main as options_main
from fraud_ml.ensemble.tracks import (
    owns_candidate,
    scoped_requirements,
    track_models,
    track_root,
)


def test_independent_models_and_paths():
    assert track_models("random-forest") == ("random_forest",)
    assert track_models("four-model-ensemble") == MODEL_ORDER
    assert len(MODEL_ORDER) == 4
    for root in ("artifacts/sparkov-task5", "reports/sparkov-policy-options"):
        assert track_root(root, "all") == Path(root)
        assert track_root(root, "random-forest") != track_root(
            root, "four-model-ensemble"
        )
    with pytest.raises(ValueError):
        track_root("reports", "../escape")


@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
def test_component_diagnostics_cannot_win_ensemble_selection(method):
    assert owns_candidate("random-forest", f"random_forest.{method}")
    assert not owns_candidate("four-model-ensemble", f"random_forest.{method}")
    assert owns_candidate("four-model-ensemble", f"fusion.{method}.sigmoid")
    assert not owns_candidate("random-forest", f"fusion.{method}.sigmoid")


def test_rf_selection_never_becomes_fusion_policy():
    original = {
        "selected_scorer": "random_forest.sigmoid",
        "review_threshold": 0.1,
        "block_threshold": 0.25,
        "maximum_reviews_per_hour": 20,
        "final_test_criteria_approved": False,
    }
    rf = scoped_requirements(original, "random-forest")
    fusion = scoped_requirements(original, "four-model-ensemble")
    assert rf["review_threshold"] == original["review_threshold"] == 0.1
    assert fusion["review_threshold"] is None
    assert fusion["block_threshold"] is None
    assert fusion["selected_scorer"] is None
    assert fusion["maximum_reviews_per_hour"] == 20
    assert not fusion["final_test_criteria_approved"]


def test_cross_track_input_rejected_before_io(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:
        options_main(
            [
                "--track",
                "random-forest",
                "--source-track",
                "four-model-ensemble",
                "--evidence-run",
                "missing",
                "--requirements",
                "missing.json",
            ]
        )
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == []
