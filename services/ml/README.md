# Task 4 offline ML lane

This Python 3.12 workspace audits the pinned ULB credit-card-fraud dataset and
evaluates four classical baselines on validation data only.

Run uv sync first. Then:

- uv run fraud-audit loads the pinned Kaggle version through KaggleHub.
- uv run fraud-baselines trains Logistic Regression, Linear SVM, Random
  Forest, and KNN and writes ignored local artifacts.
- Add --local-csv path/to/creditcard.csv to use an already downloaded copy.

The CSV, Kaggle credentials, reports, per-row scores, and model artifacts are
local-only and ignored by Git. The test partition is created and reported but
never scored.

## Validation-only calibrated ensemble

Ensemble development performs deterministic five-fold training-only calibration, compares
equal and constrained weighted soft voting, and generates three measured
Allow/Review/Block profiles:

- `uv run fraud-ensemble-develop --local-csv data/creditcard.csv`
- `uv run fraud-ensemble-smoke --bundle-dir artifacts/model-bundles/ensemble-development-v1`

The development command writes a structured, checksummed local bundle under
ignored `artifacts/model-bundles/ensemble-development-v1/` and safe aggregate
evidence under `reports/ensemble-development/`. The smoke command verifies the
complete bundle and scores a synthetic feature row without `Class`. Development
is paused at the M4 profile-selection gate. The locked test remains unopened.
