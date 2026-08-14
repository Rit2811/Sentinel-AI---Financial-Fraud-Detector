from __future__ import annotations

import pandas as pd


def chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = (
        frame.assign(_original_row=range(len(frame)))
        .sort_values(["Time", "_original_row"], kind="stable")
        .reset_index(drop=True)
    )
    train_end, validation_end = split_boundaries(
        ordered, train_fraction, validation_fraction
    )
    parts = (
        ordered.iloc[:train_end],
        ordered.iloc[train_end:validation_end],
        ordered.iloc[validation_end:],
    )
    return tuple(part.drop(columns="_original_row").copy() for part in parts)


def split_boundaries(
    ordered_frame: pd.DataFrame,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> tuple[int, int]:
    train_target = int(len(ordered_frame) * train_fraction)
    validation_target = int(len(ordered_frame) * (train_fraction + validation_fraction))
    return (
        _after_equal_time_group(ordered_frame, train_target),
        _after_equal_time_group(ordered_frame, validation_target),
    )


def _after_equal_time_group(frame: pd.DataFrame, target: int) -> int:
    if target <= 0 or target >= len(frame):
        return target
    time_value = frame.iloc[target - 1]["Time"]
    while target < len(frame) and frame.iloc[target]["Time"] == time_value:
        target += 1
    return target
