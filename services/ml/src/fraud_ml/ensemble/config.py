from __future__ import annotations

from dataclasses import asdict, dataclass

MODEL_ORDER = (
    "logistic_regression",
    "random_forest",
    "linear_svm",
    "knn",
)
FEATURE_ORDER = ("Time", *[f"V{i}" for i in range(1, 29)], "Amount")
DATASET_SHA256 = "76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89"
SPLIT_VERSION = "task4-chronological-v1"
SPLIT_IMPLEMENTATION_BLOB = "6c787249cd245d9ba3d4595591f60544b8e25257"


@dataclass(frozen=True)
class EnsembleConfig:
    version: str = "ensemble-development-v1"
    bundle_schema_version: str = "ensemble-bundle-v1"
    seed: int = 42
    folds: int = 5
    calibration_bins: int = 10
    isotonic_minority_per_fold: int = 25
    fusion_regularization: float = 0.05
    minimum_fusion_weight: float = 0.01
    probability_tolerance: float = 1e-12
    ranking_regression_tolerance: float = 0.01
    fusion_average_precision_tolerance: float = 0.002
    fusion_log_loss_tolerance: float = 0.02
    fusion_policy_recall_tolerance: float = 0.02
    fusion_stability_tolerance: float = 0.02
    precision_recall_curve_points: int = 201
    review_budgets: tuple[int, ...] = (100, 500, 1000)
    action_rate_grid: tuple[float, ...] = (0.0025, 0.005, 0.01, 0.02, 0.05)
    block_rate_grid: tuple[float, ...] = (0.0005, 0.001, 0.0025, 0.005, 0.01)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["model_order"] = list(MODEL_ORDER)
        payload["feature_order"] = list(FEATURE_ORDER)
        payload["dataset_sha256"] = DATASET_SHA256
        payload["split_version"] = SPLIT_VERSION
        payload["split_implementation_blob"] = SPLIT_IMPLEMENTATION_BLOB
        return payload
