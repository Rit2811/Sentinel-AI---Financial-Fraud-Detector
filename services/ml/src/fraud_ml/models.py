from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.svm import LinearSVC


def build_models(seed: int = 42) -> dict:
    return {
        "logistic_regression": make_pipeline(
            RobustScaler(),
            LogisticRegression(
                class_weight="balanced", max_iter=1000, random_state=seed
            ),
        ),
        "linear_svm": make_pipeline(
            RobustScaler(),
            LinearSVC(class_weight="balanced", random_state=seed),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            n_jobs=1,
            random_state=seed,
        ),
        "knn": make_pipeline(
            RobustScaler(), KNeighborsClassifier(n_neighbors=5, n_jobs=1)
        ),
    }


def reduce_knn_majority(
    features,
    target,
    majority_limit: int = 50_000,
    seed: int = 42,
):
    target_array = np.asarray(target)
    fraud = np.flatnonzero(target_array == 1)
    majority = np.flatnonzero(target_array == 0)
    if len(majority) > majority_limit:
        rng = np.random.default_rng(seed)
        majority = np.sort(rng.choice(majority, majority_limit, replace=False))
    selected = np.sort(np.concatenate([majority, fraud]))
    return features.iloc[selected], target.iloc[selected]
