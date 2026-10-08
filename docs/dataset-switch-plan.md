# Sparkov migration gates

Requested source: `kartik2112/fraud-detection/versions/1`. The user authorized
the dataset migration through Task 6, subject to the supplied PDF's evidence
gates. The PDF is an implementation guide, not evidence of completed work.

## Repository inspection

Inspected branch `ritwik`, commit `44e0bc9624ce8ab59614f7e948b80855a365bb29`.
Remote `main` checked on 2026-10-01:
`64f54824179182b1bd02ec77e250dd39ca3f1659`. Their trees are identical.
No merge, branch switch, commit or push is needed for this implementation.
The older `docs/planning/` material is absent locally. The supplied October 1
dataset-switch PDF and October 2 Task 5/6 guide define the gates. The newer
guide explicitly permits independent Task 6 storage/API preparation while
holding activation until owner approvals, freeze, final test and DB readiness.

## File-by-file sequence

1. `services/ml/src/fraud_ml/sparkov_audit.py`: repeatable source schema,
   integrity, time consistency and cross-file leakage audit. Raw files and
   generated evidence stay ignored. Pin version and SHA-256 before training.
2. `docs/feature-contract.md` and `services/ml/src/fraud_ml/features.py`:
   versioned safe replay mapping and one point-in-time implementation for
   offline and replay features, with strictly earlier history.
3. `services/ml/src/fraud_ml/data.py`, `split.py`, `cli.py`, `models.py`,
   `evaluation.py`: replace active source, split and baseline pipeline;
   reserve the supplied future test file after verifying its chronology.
4. `backend/src/contracts/authorizationEvent.js`, event repository and a new
   additive migration: schema 2 Sparkov events, no invented payment fields,
   preserve immutable schema 1 rows and the existing outbox/receipt links.
5. ML and backend tests: source mutation, raw-data/label exclusion, same-time
   and future-event leakage, unknown categories, chronological boundaries,
   feature parity, v2 ingestion, retries and stream deduplication.
6. README files, API documentation and `AGENTS.md`: make the active dataset,
   implemented boundaries and incomplete gates explicit.
7. `services/ml/src/fraud_ml/ensemble/`: retire incompatible old defaults;
   after Task 4 passes and owner constraints are available, implement
   chronological calibration, fusion comparison, policy freezing and one
   locked-test evaluation.
8. Prepare storage/read API independently; activate Python Redis inference
   and timely simulator decisions only after Task 5 and actual-target DB gates
   pass. Polling is sufficient; no second inference HTTP framework is required.
   Verify label-free replay, timeout/restart/concurrency and durable history.

## Acceptance checklist

- [x] Source version, license listing, both file sizes and SHA-256 recorded.
- [x] Columns, label validity/prevalence, nulls, duplicates, card counts audited.
- [x] Text/unix clock relationship resolved explicitly.
- [x] Train/test identity disjointness and forward time verified.
- [x] Exact feature order/types/units/history/missing/category policy documented.
- [x] Historical/replay parity demonstrated without labels or raw identities.
- [x] Four Task 4 baselines plus all-legitimate comparison measured.
- [x] New test unscored during development.
- [x] Schema 2 event traverses PostgreSQL outbox, Redis and deduplicated receipt.
- [x] Owner provisional Review capacity, false-block and capture targets recorded.
- [x] Development-only chronological calibration and four-model fusion measured.
- [x] Policy-pair options assessed against provisional normal/peak limits.
- [x] Owner timing/failure/review choices and sigmoid RF/policy approval recorded.
- [x] Selected RF preprocessing/model/calibration/policy frozen with verified hashes.
- [x] Frozen RF policy evaluated once on the locked test; approved criteria passed.
- [x] Task 6 decisions/actions persisted, idempotent and reproducible across restart.
- [ ] Task 6 actual-application zero-expiry normal/full-peak qualification and activation.

See `task-5-final-test-record.md` for the completed model gate and
`scoring-verification.md` for current application evidence. The protected
APIs and connected worker are implemented and actual actions were verified;
general activation remains held on persistent-database performance. The separate
four-model ensemble remains a development track, not the selected frozen scorer.

Absent from the source: observed currency/timezone, channel, entry mode,
device/terminal identity, account balances and merchant country. Do not derive
these from category, location or transaction amounts. The dataset label is a
simulation outcome, not bank-confirmed feedback. Raw card number, names and
addresses stay in private source storage only.
