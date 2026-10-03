# Execution and Database Evidence

Historical migration-0006 checkpoint, not the current deployment status.
See `task-6-verification-record.md` for the implemented worker, applied
migrations 0001-0009, restored backups and remaining workload/activation gates.
Task 5's authorized test now passed;
`task-5-final-test-record.md` contains its unchanged-package evidence.

## Actual Application Target

Owner confirmed `sentinel` at localhost:15432. Compose API, publisher and proof
consumer resolve to `postgres:5432/sentinel`; host API config resolves to
`127.0.0.1:15432/sentinel`. There is no connected Python scoring worker yet.
Do not confuse proof-consumer receipts with scores.

Before migration, the actual database had zero public tables and no ledger.
The repository node-pg-migrate runner applied 0001-0005, then the tested
`0006_simulated-execution`. Verified six ledger entries, required constraints,
SELECT/INSERT permissions and zero application events/results/executions.
No application fixture decisions were inserted. No database or volume was reset.
The local prototype role has broad privileges; this is not production RBAC.

API smoke against this actual database: health 200, OpenAPI 200, authenticated
unknown-result lookup 404, scoring readiness 503, unconfigured review API 503.

## Backup and Recovery

Before migration, `pg_dump -Fc --no-owner` saved the application database to
`services/ml/artifacts/database-recovery/20261002/sentinel-pre-task6.dump`.
SHA-256:
`50bb9862a1ce860bcdbce259cd37c277a84321cf01b7af4fe620ac2809071c9c`.
The dump is private and Git-ignored. Its archive table of contents was checked.
`pg_restore --no-owner --exit-on-error` succeeded into a newly created
`sentinel_recovery_probe` database in the separate disposable PostgreSQL
instance on port 25432. Restored public-table count was zero, matching the
pre-migration source. This proves recovery of the empty baseline, not a later
populated deployment backup.

For future populated migrations: stop writes, take a fresh dump and record its
hash, restore into a NEW isolated database and verify counts/constraints first.
Retain the original application database. Prefer forward repair for migration
errors; transactional migration failures roll back. Never run a down migration
against populated scoring/execution evidence. Any restore or connection switch
over an existing application target requires explicit confirmation. A pre-schema
dump cannot recover transactions created after it.

## Automated Simulation

Migration 0006 creates separate immutable `simulated_executions` and
`review_resolutions`. At scoring transaction commit, Pass becomes `allowed`,
Block becomes `rejected`, Review becomes `pending_review`. The execution row is
the effect in this local simulator; no payment network or account balance changes.
A deferred trigger checks the actual database clock before execution. Crossing
the deadline before commit rolls back result/execution; the future worker must
then durably record Expired and acknowledge only that terminal record.
The processing enum now distinguishes `expired`; an expired job cannot revive.

One execution per run/event is enforced by primary key. Model results and
execution records cannot be updated/deleted. Human review inserts a separate
immutable resolution, whose allow/reject outcome is the final simulated state;
the original model action remains Review. Human review has no scoring deadline.
None of these operations produces a fraud/non-fraud label.

## Review API

`POST /api/v1/transactions/{eventId}/review-resolution`

Requires separate private `REVIEW_API_TOKEN` (>=32 characters), server-configured
`REVIEWER_ID` (letters/digits/underscore/hyphen) and UUID `SCORING_RUN_ID`.
Configuration remains blank, so the application route is disabled by default.
Each credential represents one reviewer. Do not share one reviewer credential
across people; multiple-user authentication remains future work. Never send
secrets in chat. Keep the API loopback-only.

JSON contains only `resolution_id` UUID, `resolution` allow/reject, and `notes`
(1-2000 characters). Reviewer identity cannot be supplied by the caller. Keep
notes free of personal/card information; a card-like digit filter is an extra
guard, not comprehensive PII detection. Bodies and notes are not logged.

201 means committed; identical retry returns original evidence with 200;
conflicting resolution or reused identity returns 409; missing review 404;
bad authentication 401; unavailable configuration/storage 503. Row locking and
unique constraints serialize concurrent resolutions. If COMMIT response is lost,
retry with the SAME resolution ID/body; storage is checked before another effect.
GET result exposes original model evidence, current execution state, authenticated
reviewer identity, resolution notes and timestamps separately. See OpenAPI and
`task-6-requests.http`.

## Verification and Remaining Work

143 backend unit tests and 33 isolated PostgreSQL/Redis integration tests passed.
Checks include all three simulated outcomes, concurrent identical review requests
(one 201 and one 200), conflicting resolution, immutable evidence, expiry,
deadline crossing between INSERT and COMMIT, schema up/down/up and existing
ingestion/stream receipt recovery. The first full integration invocation failed
because the new disposable database was not migrated; after runner migration and
FK-aware fixture cleanup, the complete suite passed. ESLint/Prettier passed.

Remaining: authorized reserved-test pass; connected Python worker; durable ordered
history and feature snapshots through retries/restarts; run/package gate registry;
durable attempt/terminal-failure handling; lost-stream reconciliation for scoring;
offline/live score parity; connected failure matrix; 1 TPS and 5 TPS/ten-minute
measurements. No throughput, queue-age or end-to-end latency result is claimed.
G5 storage preparation is verified, but G6/G7 and Task 6 completion remain open.
