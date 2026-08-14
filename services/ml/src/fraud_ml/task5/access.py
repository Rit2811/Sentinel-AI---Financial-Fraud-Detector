from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fraud_ml.split import split_boundaries


@dataclass(frozen=True)
class LockedTestDescriptor:
    start: int
    stop: int
    row_count: int
    state: str = "LOCKED"


@dataclass(frozen=True)
class DevelopmentPartitions:
    train: pd.DataFrame
    validation: pd.DataFrame
    locked_test: LockedTestDescriptor


def development_partitions(frame: pd.DataFrame) -> DevelopmentPartitions:
    ordered = (
        frame.assign(_original_row=range(len(frame)))
        .sort_values(["Time", "_original_row"], kind="stable")
        .reset_index(drop=True)
    )
    train_end, validation_end = split_boundaries(ordered)
    train = ordered.iloc[:train_end].drop(columns="_original_row").copy()
    validation = (
        ordered.iloc[train_end:validation_end].drop(columns="_original_row").copy()
    )
    return DevelopmentPartitions(
        train=train,
        validation=validation,
        locked_test=LockedTestDescriptor(
            start=validation_end,
            stop=len(ordered),
            row_count=len(ordered) - validation_end,
        ),
    )
