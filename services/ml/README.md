# Sparkov ML Workspace

## Independent Model Tracks

`--track random-forest` develops RF alone; `--track four-model-ensemble`
develops the LR/RF/SVM/KNN combination. Both calibration and policy-options
commands support these tracks with independent output folders. See
`../../docs/model-tracks.md` for commands, shared evidence and approval gates.
The owner-selected RF policy does not select an ensemble policy.

Python 3.12, locked with `uv.lock`. Active source:
`kartik2112/fraud-detection/versions/1`. See `../../docs/dataset-source.md`
for exact hashes and `../../docs/feature-contract.md` for source mapping,
clock/currency assumptions and the shared point-in-time feature contract.

From this directory:

```powershell
uv sync --locked
$env:KAGGLEHUB_CACHE = (Join-Path (Get-Location) 'data/kagglehub')
uv run python -c "import kagglehub; print(kagglehub.dataset_download('kartik2112/fraud-detection/versions/1'))"
uv run fraud-audit --data-dir data/kagglehub/datasets/kartik2112/fraud-detection/versions/1
uv run fraud-baselines --data-dir data/kagglehub/datasets/kartik2112/fraud-detection/versions/1
uv run pytest -q
```

When using the existing environment directly, replace `uv run` with
`.venv/Scripts/python.exe -m` for module commands; the baseline entry point is
`fraud_ml.cli.baseline_main`. The audit module is `fraud_ml.sparkov_audit`.

The audit checks all source rows using bounded chunks. Training refuses files
whose hashes differ from the pins or whose audit has failed. `fraudTrain.csv`
is sorted by the canonical text time and transaction ID. Chronological
partitions reserve 60% for fitting, 20% for later calibration and 20% for
validation, keeping equal-time groups together. The supplied future
`fraudTest.csv` is never loaded by the development feature builder.

`features.py` supplies both the historical adapter and replay feature engine.
Real-row parity is checked against an independent prior-history calculation
on the first 10000 development rows. The local random HMAC key is created once
at `secrets/replay-hmac.key`; keep it stable and private. No raw identities or
labels enter inference features. Category encoding and scaling are fit inside
each model pipeline, on training data only.

Baselines: Logistic Regression, Linear SVM, Random Forest, KNN, and an
all-legitimate comparator. KNN uses a reported training-only majority cap;
validation keeps its natural prevalence. Reports include average precision
(PR-AUC convention), recall, precision, confusion counts, and measured bulk
and single-request scoring cost. Raw baseline scores are not calibrated
decision policies. Faster single models remain candidates for Task 5.

Source CSVs, feature caches, per-row labels/scores, model binaries and generated
reports are ignored. Safe aggregate source documentation is checked in.
The feature-cache manifest binds source, feature/loader code, feature version
and local key fingerprint. Cache checksums are verified before reuse.

## Gated Stages

The prior dataset-specific loader, defaults, artifacts and ensemble workflow
are retired. Existing local artifacts are not deleted, renamed or reused.
The ensemble development/smoke commands fail closed while there is no new
compatible frozen bundle. Generic numerical helpers are reusable methods,
not evidence of a finished Sparkov ensemble.

Task 5 development evidence is now available. Existing legacy ensemble commands
remain blocked; the following commands are development-only and cannot freeze,
open the reserved test or activate a model:

```powershell
uv run fraud-calibration-develop --baseline-run 20261001T141637951841Z
uv run fraud-policy-options --evidence-run 20261002T061437063185Z --requirements ../../docs/task-5-operating-requirements.json
```

See `../../docs/task-5-decision-sheet.md` for leakage-separated calendar periods,
candidate metrics and provisional policy options. Task 4 models are reused only
after their artifact/cache/exposure hashes are verified. New artifacts are
development-only calibrators and scores, not a serving package. Never load an
untrusted joblib file: deserialization can execute code.

RF policy/operating approval, package freeze and clean-load/reference proof are
now recorded in `../../docs/task-5-freeze-record.md`. The separately authorized
one-time final test passed; see `../../docs/task-5-final-test-record.md`.
Do not rerun it. `python -m fraud_ml.freeze` is the
approval-checked freeze entry point; `fraud_ml.serving.FrozenScorer` verifies
the externally pinned package before loading trusted artifacts.
The connected PostgreSQL/Redis worker is `python -m fraud_ml.worker` and the
isolated label-free load harness is `python -m fraud_ml.worker_benchmark`.
Install worker clients with `uv sync --extra worker`. Both require exact frozen
package pins. Application mode additionally verifies a pinned passing final-test
report. Task 6 remains incomplete and application scoring is not active; read
`../../docs/scoring-worker-status.md` before running either command.
