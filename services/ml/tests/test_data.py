import pandas as pd

from fraud_ml.data import EXPECTED_CLASS_COUNTS, EXPECTED_SHAPE
from fraud_ml.split import chronological_split


def test_locked_dataset_expectations():
    assert EXPECTED_SHAPE == (284_807, 31)
    assert EXPECTED_CLASS_COUNTS == {0: 284_315, 1: 492}


def test_chronological_split_keeps_equal_times_together():
    frame = pd.DataFrame(
        {
            "Time": [0, 1, 1, 2, 3],
            "feature": range(5),
            "Class": [0, 0, 1, 0, 1],
        }
    )
    train, validation, test = chronological_split(frame)
    assert set(train["Time"]).isdisjoint(set(validation["Time"]))
    assert set(validation["Time"]).isdisjoint(set(test["Time"]))
    assert list(pd.concat([train, validation, test])["Time"]) == [0, 1, 1, 2, 3]


def test_split_is_stable_for_equal_times():
    frame = pd.DataFrame({"Time": [1, 1, 1], "feature": [2, 1, 3], "Class": [0, 1, 0]})
    train, _, _ = chronological_split(frame)
    assert train["feature"].tolist() == [2, 1, 3]
