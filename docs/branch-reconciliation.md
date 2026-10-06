# Branch Reconciliation

2026-10-06: owner approved a local checkpoint, merge and verification on `ritwik`.
No push, main merge, activation or deadline change was authorized or performed.

## Preserved Work

PC checkpoint `8619787` is retained by `recovery/pc-checkpoint-20261006`.
The earlier ignored patch/untracked-file snapshot remains under
`services/ml/artifacts/branch-recovery/20261006T180154867Z/`.
Laptop commit `410472e` and its three handoff/history documents are incorporated;
machine-specific deployment observations are marked historical, not erased.
The recorded Task 7 feature-verification scope is preserved but not started.

Four Compose conflicts were naming-only. Canonical configuration remains identical
to the tested PC checkpoint, including the explicit Mumbai overrides and hold.
The isolated project keeps `sentinel-test` and the legacy DNS aliases required
by immutable images/fixture guards. Fixed laptop container names were not kept:
the real Redis restart test expects `sentinel-test-redis-1`.

The generated npm cache at `backend/false/` is now ignored, not deleted.
Environment files, CA, model binaries, reports and backups remain excluded.
No known private environment values or forbidden artifact paths matched the
reviewed staged files. This is not a substitute for reviewing future commits.

## Verification

- Backend: 180 unit and 49 integration tests passed; ESLint and Prettier passed.
- Python: Ruff lint and formatting passed; 126 focused worker/parallel/gate tests
  passed, including actual frozen-policy parity, retries, ordering, uncertain
  commit recovery and explicitly enabled isolated Redis restart.
- Initial Python run had 125 passes and one stale benchmark test-stub failure.
  Its mocked DB lacked the new clock preflight. An explicit unit-only clock stub
  was added; the isolated test and full focused rerun passed. No production
  scoring, clock tolerance, feature meaning or deadline was changed.
- 816 existing joblib/NumPy 2.5 deprecation warnings remain documented.
- Base/test/pipeline/deadline/combined and actual cloud Compose syntax validated;
  actual private config was inspected only through quiet validation.
- A real container authenticated through both legacy fixture DNS aliases and
  verified the strictly isolated database name and migration ledger of 12.
- All 43 inventoried private runtime/frozen/gate files retained their SHA-256.
- Source main reference remains `b767e1cc4a232edd9fdc790b843f1e3c809e26c3`.
  No application writer was started; fixtures were stopped after verification.

All database-changing tests targeted disposable test PostgreSQL/Redis, never
Mumbai or the preserved application volumes. No reserved evaluation was repeated.

## Next Steps

The reconciled local branch can be reviewed for a separately authorized normal
push; do not force-push. Refresh remote history first if it has advanced again.
On the laptop, a clean `git pull --ff-only` is appropriate only once the resulting
commit is actually pushed and no local changes would be overwritten. Preserve
any laptop edits before synchronization. Git does not transfer Docker tags,
private files or persistent Redis state: follow [laptop-handoff.md](laptop-handoff.md).

This resolves branch integration, NOT Task 6 performance. Task 5 remains complete;
Task 6 remains incomplete with activation held after the valid-clock 24/30 normal
precheck. Both ten-minute zero-expiry qualifications and final same-deployment
checks remain required. See [pipeline-qualification.md](pipeline-qualification.md).
