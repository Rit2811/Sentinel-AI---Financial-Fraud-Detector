"""Development track boundaries; no track grants serving or test approval."""

from pathlib import Path

from .config import MODEL_ORDER

TRACKS = ("all", "random-forest", "four-model-ensemble")


def track_models(track):
    if track not in TRACKS:
        raise ValueError("Unknown development track")
    return ("random_forest",) if track == "random-forest" else MODEL_ORDER


def track_root(root, track):
    track_models(track)
    return Path(root) if track == "all" else Path(root) / track


def owns_candidate(track, name):
    track_models(track)
    if track == "all":
        return True
    prefix = "random_forest." if track == "random-forest" else "fusion."
    return name.startswith(prefix)


def scoped_requirements(requirements, track):
    """Keep shared limits, but never transfer another scorer's selected policy."""
    result = dict(requirements)
    selected = result.get("selected_scorer")
    if selected and not owns_candidate(track, selected):
        for key in (
            "selected_scorer",
            "review_threshold",
            "block_threshold",
            "selection_recorded_at_utc",
            "selection_evidence_run",
            "selection_reason",
            "policy_version",
            "policy_approver",
            "policy_approval_timestamp",
        ):
            result[key] = None
        result["final_test_criteria_approved"] = False
        result["status"] = "track_policy_selection_pending"
    result["track"] = track
    return result
