import pandas as pd

from fraud_ml.task5.access import development_partitions


def test_development_partitions_expose_no_test_frame():
    frame = pd.DataFrame(
        {
            "Time": [0, 1, 1, 2, 3],
            "feature": range(5),
            "Class": [0, 0, 1, 0, 1],
        }
    )
    partitions = development_partitions(frame)
    assert set(partitions.__dataclass_fields__) == {
        "train",
        "validation",
        "locked_test",
    }
    assert partitions.locked_test.state == "LOCKED"
    assert partitions.locked_test.row_count == 1
    assert not hasattr(partitions.locked_test, "frame")
