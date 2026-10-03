from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler
from sklearn.svm import LinearSVC

from .features import FEATURE_ORDER, NUMERIC_FEATURES


def validate_features(features) -> None:
    if tuple(features.columns) != FEATURE_ORDER:
        raise ValueError("Features must contain only FEATURE_ORDER, in contract order")


def _pipeline(classifier) -> Pipeline:
    return Pipeline(
        [
            (
                "preprocessor",
                ColumnTransformer(
                    [
                        ("numeric", RobustScaler(), list(NUMERIC_FEATURES)),
                        (
                            "category",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                            ["merchant_category"],
                        ),
                    ],
                    remainder="drop",
                ),
            ),
            ("classifier", classifier),
        ]
    )


def build_models(seed: int = 42) -> dict:
    return {
        "logistic_regression": _pipeline(
            LogisticRegression(
                class_weight="balanced", max_iter=1000, random_state=seed
            ),
        ),
        "linear_svm": _pipeline(
            LinearSVC(
                class_weight="balanced",
                dual=False,
                max_iter=10_000,
                random_state=seed,
            ),
        ),
        "random_forest": _pipeline(
            RandomForestClassifier(
                n_estimators=100,
                max_depth=18,
                min_samples_leaf=2,
                class_weight="balanced",
                n_jobs=1,
                random_state=seed,
            ),
        ),
        "knn": _pipeline(KNeighborsClassifier(n_neighbors=5, n_jobs=1)),
    }


def reduce_knn_majority(
    features,
    target,
    majority_limit: int = 10_000,
    seed: int = 42,
):
    validate_features(features)
    if majority_limit < 1:
        raise ValueError("majority_limit must be positive")
    if len(features) != len(target) or not features.index.equals(target.index):
        raise ValueError("Training features and labels must be aligned")
    target_array = np.asarray(target)
    if not np.isin(target_array, [0, 1]).all():
        raise ValueError("Training labels must be binary")
    fraud = np.flatnonzero(target_array == 1)
    majority = np.flatnonzero(target_array == 0)
    if len(majority) > majority_limit:
        rng = np.random.default_rng(seed)
        majority = np.sort(rng.choice(majority, majority_limit, replace=False))
    selected = np.sort(np.concatenate([majority, fraud]))
    return features.iloc[selected], target.iloc[selected]
