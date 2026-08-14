# Task 4 offline ML lane

This Python 3.12 workspace audits the pinned ULB credit-card-fraud dataset and
evaluates four classical baselines on validation data only.

Run uv sync first. Then:

- uv run fraud-audit loads the pinned Kaggle version through KaggleHub.
- uv run fraud-baselines trains Logistic Regression, Linear SVM, Random
  Forest, and KNN and writes ignored local artifacts.
- Add --local-csv path/to/creditcard.csv to use an already downloaded copy.

The CSV, Kaggle credentials, reports, and model artifacts are ignored by Git.
The test partition is created and reported but never scored.
