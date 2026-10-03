import numpy as np
import pytest

from fraud_ml.application_smoke import generated_cases, is_duplicate_acceptance
from fraud_ml.features import FEATURE_ORDER, features_from_prior


class FixtureScorer:
    def score(self, rows):
        assert all(set(row) == set(FEATURE_ORDER) for row in rows)
        return (
            np.array([0.05, 0.15, 0.5] + [0.05] * (len(rows) - 3)),
            np.array(["Pass", "Review", "Block"] + ["Pass"] * (len(rows) - 3)),
        )


@pytest.mark.parametrize(
    "status,duplicate,expected",
    [
        (200, {"event_id": "original", "outcome": "duplicate"}, True),
        (202, {"event_id": "original", "outcome": "accepted"}, False),
        (200, {"event_id": "other", "outcome": "duplicate"}, False),
        (200, {"event_id": "original", "outcome": "accepted"}, False),
    ],
)
def test_duplicate_receipt_uses_existing_api_contract(status, duplicate, expected):
    acceptance = {"event_id": "original", "outcome": "accepted"}
    assert is_duplicate_acceptance(status, duplicate, acceptance) is expected


def test_generated_application_cases_are_label_free_and_reproducible():
    cases = generated_cases(FixtureScorer())
    assert set(cases) == {"Pass", "Review", "Block"}
    for event, features, probability in cases.values():
        assert features == features_from_prior(event, [])
        assert event["card_token"].startswith("card_")
        assert not {"is_fraud", "cc_num", "channel", "device", "balance"} & event.keys()
        assert 0 <= probability <= 1


def test_missing_action_region_is_not_claimed_as_verified():
    class PassOnly:
        def score(self, rows):
            return np.zeros(len(rows)), np.array(["Pass"] * len(rows))

    with pytest.raises(RuntimeError, match="all actions"):
        generated_cases(PassOnly())
