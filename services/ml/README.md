# Fraud Feature and Scoring Workspace

Python 3.12 with dependencies pinned in `uv.lock`. Docker includes this runtime;
use [teammate setup](../../docs/teammate-setup.md) for independent local operation.

The serving scorer is an approved frozen sigmoid-calibrated Random Forest.
`fraud_ml.serving.FrozenScorer` verifies the externally pinned manifest, package
files, exact runtime versions and executing feature/scoring code before loading.
Model files and gate evidence are private inputs, not downloadable through Git.
Do not train a replacement or repeat reserved-data evaluation during setup.

`fraud_ml.features` defines the ordered eight inputs: amount, hour, weekday,
prior one-hour/24-hour counts, prior 24-hour sum/mean and merchant category.
Features use earlier available same-card attempts; equal-time/future events do
not contribute. Categories use the saved encoder, including unseen all-zero
encoding. Raw identities and labels are excluded from scorer inputs.

`fraud_ml.worker` maintains durable PostgreSQL snapshots/history/results and
Redis delivery recovery. Per-card order and retry deduplication are preserved;
the supported parallel coordinator overlaps only independent cards. Scoring
unavailability and expiry cannot execute or fabricate Pass.

The separate RF/ensemble development code is preserved independently. Running
the selected application scorer does not require downloading raw datasets or
starting development/training/calibration commands.

Pure tests are under `tests/`; worker integration tests require explicitly
isolated PostgreSQL/Redis fixtures. Trusted frozen artifacts are needed for
frozen-model tests. Keep datasets, binaries, labels, reports, env and keys ignored.
