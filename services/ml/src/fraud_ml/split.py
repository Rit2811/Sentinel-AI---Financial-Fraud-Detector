"""Chronological development partitions; the supplied test is never involved."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _timestamps(times: pd.Series) -> pd.Series:
    if not isinstance(times, pd.Series):
        raise TypeError("Pass the canonical timestamp Series, not a feature frame")
    if not pd.api.types.is_datetime64_any_dtype(times.dtype):
        raise ValueError("Canonical timestamps must have a datetime dtype")
    if times.empty or times.isna().any():
        raise ValueError("Canonical timestamps must be nonempty and non-null")
    return times.reset_index(drop=True)


def chronological_split(
    times: pd.Series,
    train_fraction: float = 0.6,
    calibration_fraction: float = 0.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return iloc positions for train, calibration, validation, in time order.

    Stable sorting preserves the loader's transaction-ID order within ties.
    Boundaries advance to the end of a tied group; actual fractions may differ.
    """
    canonical = _timestamps(times)
    order = canonical.sort_values(kind="stable").index.to_numpy()
    train_end, calibration_end = split_boundaries(
        canonical.iloc[order], train_fraction, calibration_fraction
    )
    return order[:train_end], order[train_end:calibration_end], order[calibration_end:]


def split_boundaries(
    ordered_times: pd.Series,
    train_fraction: float = 0.6,
    calibration_fraction: float = 0.2,
) -> tuple[int, int]:
    times = _timestamps(ordered_times)
    if not times.is_monotonic_increasing:
        raise ValueError("split_boundaries requires sorted timestamps")
    if not (
        0 < train_fraction < 1
        and 0 < calibration_fraction < 1
        and train_fraction + calibration_fraction < 1
    ):
        raise ValueError("Fractions must leave three positive partitions")
    boundaries = []
    for fraction in (train_fraction, train_fraction + calibration_fraction):
        target = int(len(times) * fraction)
        if target > 0:
            target = int(times.searchsorted(times.iloc[target - 1], side="right"))
        boundaries.append(target)
    train_end, calibration_end = boundaries
    if not 0 < train_end < calibration_end < len(times):
        raise ValueError("Timestamp groups cannot form three nonempty partitions")
    return train_end, calibration_end


def partition_summary(labels: pd.Series, times: pd.Series) -> dict:
    canonical = _timestamps(times)
    if len(labels) != len(times) or not labels.index.equals(times.index):
        raise ValueError("Partition labels and timestamps must be aligned")
    if not labels.isin([0, 1]).all():
        raise ValueError("Partition labels must be binary")
    return {
        "rows": len(labels),
        "class_counts": {str(value): int((labels == value).sum()) for value in (0, 1)},
        "date_min": canonical.min().isoformat(),
        "date_max": canonical.max().isoformat(),
    }
