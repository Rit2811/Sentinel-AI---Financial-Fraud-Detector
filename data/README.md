# Data

The active source is `kartik2112/fraud-detection/versions/1`, simulated Sparkov transactions, listed as CC0. See `docs/dataset-source.md` for pinned hashes and acquisition notes and `docs/feature-contract.md` for the inference boundary.

Raw files live under ignored `services/ml/data/`. Do not commit source CSVs, labels, derived features, reports, credentials or model binaries. Raw `cc_num`, names and addresses must never enter application payloads or logs. Use a stable local HMAC key for card history joins; keep it under ignored `secrets/` and preserve it across replay runs.

The supplied future test file is reserved for a single post-freeze Task 5 evaluation. Source-integrity/aggregate label audits are not model evaluation. Retain raw files locally only as long as needed to reproduce experiments; do not publish them through the application.
