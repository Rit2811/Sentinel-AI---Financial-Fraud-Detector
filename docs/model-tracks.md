# Two Development Tracks

Owner requested both tracks on 2026-10-02. RF now passed its authorized final
test; the ensemble remains development-only. Neither application worker is active.
This is an engineering separation, not an assessment of patent coverage.

## Random Forest

Runs only Random Forest component calibration and inference. Sigmoid and
isotonic calibration are compared. The owner-selected proposal is sigmoid
RF with Review at 0.10 and Block at 0.25; remaining operational approvals
were subsequently approved for freeze; its one separately authorized final test
passed. See `task-5-final-test-record.md`. Development average precision is 0.950762.

## Four-Model Ensemble

Combines Logistic Regression, Random Forest, Linear SVM and KNN. Each has
its own calibrated probability; learned positive weights combine all four,
then a final calibration produces the ensemble probability. All four retain
at least 0.01 weight. Component diagnostics remain available, but only fused
candidates can win this track's model selection or receive policy proposals.
Existing best ensemble average precision is 0.921907. These are development
ranking metrics, not accuracy or guaranteed future performance.

RF currently leads the measured comparison. The ensemble remains a separate
research path; its method and thresholds can be improved independently.
No ensemble policy has been owner-selected. RF thresholds are never inherited.

## Commands

Run from `services/ml`, using the same verified Task 4 base models:

```powershell
uv run fraud-calibration-develop --track random-forest --baseline-run 20261001T141637951841Z
uv run fraud-calibration-develop --track four-model-ensemble --baseline-run 20261001T141637951841Z
```

Each prints its new run folder. Assess that track's run with:

```powershell
uv run fraud-policy-options --track random-forest --evidence-run <RF_RUN_ID> --requirements ../../docs/task-5-operating-requirements.json
uv run fraud-policy-options --track four-model-ensemble --evidence-run <ENSEMBLE_RUN_ID> --requirements ../../docs/task-5-operating-requirements.json
```

To reuse the already measured combined run without recalibration, add
`--source-track all --evidence-run 20261002T061437063185Z` instead of the
new run ID. Candidates and policy-selection metadata are filtered by track.
Omitting `--track` retains the legacy combined research command for compatibility.

New development artifacts and evidence are stored independently:

- `services/ml/artifacts/sparkov-task5/<track>/<run>/`
- `services/ml/reports/sparkov-task5/<track>/<run>/`
- `services/ml/reports/sparkov-policy-options/<track>/<run>/`

Each run keeps checksums, provenance, calibration methods and measured results.
The original combined evidence is preserved. Immutable Task 4 base pipelines,
dataset pins, point-in-time features and chronological partitions are shared
for a fair comparison. RF leaves the fusion-fitting periods unused. No raw
identity or label enters scoring. RF's one authorized reserved-test evaluation
is complete; the ensemble has no authorization to use that test.

## Remaining Gates

These are ML workspaces, not live dashboard tabs or two deployed scorers.
Each future serving package needs its own model/policy identity, approval,
hashes and reference proof. RF operating decisions and freeze are now approved;
the ensemble remains unselected. Agree on
the exact frozen candidates and final-test protocol before any reserved-test
access; do not use repeated test results to tune or pick between the tracks.
Task 6 live scoring and action execution have not been activated.

## Verified Runs

Completed on 2026-10-02 using the existing verified development cache:

| Track | Calibration evidence run | Policy-options run |
| --- | --- | --- |
| random-forest | `20261002T073554111965Z` | `20261002T073647025380Z` |
| four-model-ensemble | `20261002T073635259375Z` | `20261002T073736021146Z` |

RF contains two calibrated candidates. Ensemble contains four fused candidates
plus eight component diagnostics; its policy report contains only the four
fused candidates. Both reproduce the earlier probability-quality metrics.
Policy search proposals do not overwrite the owner's balanced RF selection.

Verification: 76 ML tests passed; Ruff lint and formatting passed (31 Python
files); artifact/report hashes and track-specific selection/gate assertions
passed on both completed runs. Generated output paths are Git-ignored.
Existing upstream joblib/NumPy deprecation warnings remain; the ensemble run
also reported physical-core detection fallback to logical cores. No new
dependency, backend/database change, final-test scoring or activation occurred.
