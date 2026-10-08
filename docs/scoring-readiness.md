# Scoring Readiness

Historical preparation checkpoint. Current status is in `scoring-verification.md`:
the connected worker now exists and Task 5 passed its authorized final test.
Task 6 is still incomplete and application scoring is NOT activated. The storage
details below describe the earlier preparation stage, not the current worker.

## Database

`backend/migrations/0005_scoring-evidence-preparation.sql` adds three logical
records without touching existing events: version-assigned `scoring_jobs`,
typed eight-feature `scoring_feature_snapshots`, and immutable `scoring_results`
combining original prediction/decision evidence. Namespaces use a UUID run
plus the existing canonical event ID. Raw card numbers and labels have no
columns. Only safe explicit feature columns can be inserted.

Unique keys prevent duplicate original evidence. Assigned identity, package,
model, policy, feature version and deadline cannot change on retry. Deferred
SQL constraints require the result and scored terminal status in one commit;
full-precision thresholds/action boundaries and nonfinite values are checked.
Snapshots/results cannot be changed or deleted. Expired decisions cannot
commit as timely success. Down migration refuses populated evidence.

This is not a complete worker persistence implementation: durable ordered
history, leases/fencing, retry scheduling, audit transitions, late evidence,
component-score storage and approved-run registry remain to be implemented.
The snapshot history sequence is a storage field, not a proven checkpoint.
No fixture model or policy is installed in the application database.

Initial configured local PostgreSQL inspection on 2026-10-02 found only
`postgres` and `sentinel` databases, no ULB-named database. `sentinel` had no
public tables and no `pgmigrations` ledger. The owner subsequently explicitly
confirmed `sentinel` as the target. After backup and configuration alignment,
the repository runner applied migrations 0001-0006. Ledger, permissions and
actual-target API retrieval were verified. No application data or volumes were
reset. Recovery proof is in `scoring-execution-recovery.md`.

Earlier preparation migrations were applied with the repository runner to isolated
`sentinel_task4_test` on port 25432; test Redis is port 26379. Fixtures use
`FIXTURE_MODEL`/`FIXTURE_POLICY` and isolated schemas. They are never live results.

## API contract

Schema-v2 acceptance includes `processing_status: pending` and a
`result_location`. A duplicate returns the original identifiers/location,
not a recalculated score. A 202 still means ingestion, never payment approval.

`GET /api/v1/transactions/{eventId}/result` requires a bearer token matching
local `RESULT_API_TOKEN` (at least 32 characters) and an explicit UUID
`SCORING_RUN_ID`. Missing configuration fails 503; missing/wrong token is 401.
This is a local prototype access boundary, not tenant/user authorization.
Do not expose it publicly; role-based and ingestion authorization are not added.
The response is no-store and selects only safe fields from PostgreSQL.

| Situation | Status/meaning |
|---|---|
| Pending/scoring job | 200, unavailable score/action represented by null |
| Scored job | 200, stored unrounded probability, risk 100*p, action, thresholds, versions/time |
| Unavailable/failed job | 200, safe reason/retry metadata, no score/action |
| Accepted event with no assigned job | 200 unavailable, `scoring_not_activated` (or unsupported v1 schema) |
| Unknown accepted event | 404 `event_not_found` |
| Invalid UUID | 400 `invalid_event_id` |
| Schema/storage failure | 503 `scoring_store_unavailable`, no raw error |

Execution is now stored separately as allowed/rejected/pending_review, with
immutable human resolution where applicable. Expired processing has no execution.
The new review API and approved deadline semantics are documented in
`scoring-execution-recovery.md`. Result lookup also exposes review evidence.
`GET /ready/scoring` always returns 503 during preparation.
Existing `/health` is process liveness; `/ready` still checks infrastructure,
not model approval. No model is downloaded, trained or substituted on startup.
OpenAPI and `transaction-replay.http` describe the actual implemented routes.

## Verification and remaining gates

Isolated integration checks cover empty up/down/up preservation, immutable
snapshots/results, atomic result/status commit, exact Review boundary,
nonfinite/out-of-range probabilities, prohibited column injection, version
immutability, concurrent duplicate job assignment, expired commits and guarded
downgrade. Unit checks cover API authentication, correct state/nulls, unknown
IDs, error redaction, repeated retrieval and exact full-precision boundaries.

These do NOT prove connected scoring, one history effect, stream decision
recovery or actual-target migration. Before Task 6 completion:

1. Authorize the exact frozen package's one-shot test and obtain a passing
   criteria report. Approval, freeze and clean loading are already complete.
2. Keep actual-target schema/configuration aligned with any further worker
   migrations. Current migrations, ledger and recovery are already verified.
3. Implement trusted verified package loading and Python Redis scoring worker,
   durable per-card ordering, snapshots/history effects once, assigned versions,
   retries/leases/reconciliation and acknowledgement only after durable effects.
4. Connect the approved deadline/terminal-failure handling to the future worker;
   execution/review storage and API exist but are not receiving live decisions.
5. Run chronological offline/connected parity and the full PDF failure matrix,
   including crashes before/after commit, Redis loss, DB outage, missing/corrupt
   bundle, poison messages, timeouts and restarts. Retain actual commands/results.
6. Measure 1 TPS and 5 TPS workloads including queue age and end-to-end p50/p95
   against owner-approved timing limits. Add the approved worker to Compose
   and verify clean startup. Do not call stream receipts fraud decisions.

No frontend redesign, feedback loop, concept drift, retraining, commit or push
is part of this preparation.
