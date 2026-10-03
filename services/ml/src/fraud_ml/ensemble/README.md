# Ensemble evidence and legacy retirement

Sparkov Task 4 is complete. New `evidence.py`, `probability.py`, `tradeoffs.py`
and `options.py` implement development-only chronological calibration and
provisional policy comparisons. See `docs/task-5-decision-sheet.md` at repo root.
There is no compatible frozen bundle. Both legacy ensemble commands exit
nonzero before argument processing, dataset access, training, or artifact loading.
Providing a bundle path or an approval flag cannot bypass this gate.

Retired implementation:

- `access.py` and its tests: dataset-specific chronological partition access.
- `artifacts.py` and its tests: the old bundle checksum and deserialization API.
- `development.py`: dataset loading, calibration training and report generation.
- `bundle.py` and its tests: old packaging, compatibility checks and smoke scoring.
  Only the development and smoke command gates remain.
- `calibration.py`: model fitting, shuffled cross-fitting and calibrator objects.
- `config.py`: feature order, source hash, split pins and workflow defaults.
- `fusion.py`: orchestration tied to retired calibrated model objects.
- `policy.py`: unapproved named profiles and default operating rates/budgets.
- `reporting.py`: dataset-specific model card and reproduction command.

Generic helpers are reused by the new independent development commands.
Neither completed evidence nor supplied provisional numerical targets approve
a policy. Source pins belong to `fraud_ml.data`; feature order belongs to
`fraud_ml.features.FEATURE_ORDER`. Old dataset artifacts are not loaded or
migrated. Freeze, final-test access and live activation remain separately gated.
