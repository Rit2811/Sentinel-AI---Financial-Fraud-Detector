# Mumbai Application Deployment

Superseded checkpoint: read [pipeline qualification](pipeline-qualification.md)
FIRST for the additive migration, tested per-card concurrency and canceled clock
stability approval. Task 6 remains incomplete; writers/activation are paused.

Latest checkpoint: 2026-10-06. This supersedes the Tokyo resume instructions.
Task 5 is COMPLETE. Task 6 is INCOMPLETE; activation remains held.

## Migration Verified

The owner-supplied Mumbai Supabase Session pooler is the application target:
`aws-0-ap-south-1.pooler.supabase.com:5432/postgres`, PostgreSQL 17.11.
Non-secret target SHA-256:
`070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2`.
Verified TLS/hostname checks passed from Windows and Docker using the supplied CA.
Eight concurrent authenticated sessions passed. Application connection limits are
API 3, publisher 1, worker 1; the optional consumer is stopped. Redis stays local.
React has no database credentials and communicates only with Express.

Writers were stopped and outstanding source work reconciled before snapshot.
All 17,019 Tokyo application events were imported in one transaction together
with app-only privilege lockdown. Supabase built-in schemas/ACLs were preserved.
All 18 table fingerprints, 106 constraints, 33 indexes, 12 functions, 23 triggers,
two sequences and 11 migration records matched. The repository migration runner
reported no missing migrations. RLS and browser-role revocations were verified.
Source Tokyo and original local `sentinel` databases/configurations/volumes remain
preserved. No raw training CSV, card numbers, labels or model files were imported.

After diagnostics, Mumbai contains 17,309 application events; all are published.
The current candidate has 1,897 terminal jobs (1,303 Scored, 594 Expired), including
earlier history. No invalid/late simulated executions were found across the DB.
Current Redis scoring group has zero pending deliveries and zero lag; no queues
were flushed. Original local `sentinel` still has 16,822 events and is read-only.
Database size is approximately 90.2 MB, below the owner-reported 500 MB free quota.
No paid resources were purchased. Physical provider storage placement is not
observable from the Session pooler; a named volume/managed service is not SSD proof.

## Measured Pipeline Work

Mumbai warm query round trips are about 33-40 ms, versus Tokyo's 145-160 ms.
Feature arithmetic is below 1 ms; repeated remote statements/transaction control
and serial queue waiting are material. Missing samples are not reported as zero.
The Docker allocation is four CPUs and 1,998,864,384 bytes RAM. No builds or other
test stacks ran during the load checks. Local Docker/Redis storage remains on the
original HDD; application PostgreSQL data/WAL are now provider-managed.

The worker now handles an already-waiting bounded ordered batch: shared Python
feature calculation, grouped history/snapshot/job writes, grouped predictions,
atomic finalization and one canonical delivery lookup. No fill delay, parallel
per-card history, model change, audit removal or durability relaxation was added.
Expected prediction/deadline races recover durably without restarting all history.
Original pending and status-transition audit evidence remains. Actual prediction
COMMIT acknowledgment precedes finalization; stream ACK follows durable completion.

Private evidence under `services/ml/reports/replay-load/`:

| Report | Workload | Result |
| --- | --- | --- |
| `20261006T111647434817Z` | 1 TPS, 30 seconds | 30 Scored, zero Expired; maximum 824.774 ms |
| `20261006T112043039543Z` | 5 TPS, 30 seconds | 17 Scored, 133 Expired; parity and no late effects |
| `20261006T114626032462Z` | outer-pipeline experiment, 1 TPS/30s | all 30 Expired; clock subsequently found unsynchronized |

Peak sends were paced (median 200.312 ms, maximum 208.790 ms); offered rate
4.976 TPS, not a catch-up burst. Queue samples reached seven jobs, oldest 1.29s.
Measured median stage times: checkpoint/prediction 379 ms per batch, inference
82 ms, execution batch 121 ms, delivery audit 123 ms; feature calculation <1 ms.
Sampled lock blockers were absent. This is sampling evidence, not proof of no
transient locks. Per-event traces include expired events. WAL/disk timing is
limited by provider statistics visibility; do not attribute all waits to fsync.

The outer-pipeline trial was rejected. A paired, read-only actual-pooler probe
measured median BEGIN/SELECT/COMMIT at 120.09 ms without versus 202.72 ms with
outer pipelining (eight samples each). Its four outer scopes were removed;
the prior bounded batching and recovery protocol remain. The private runtime
selects `sentinel-ai-scoring-worker:mumbai-batched`, immutable image
`sha256:9569aad4268c3ac49d9023975ba430f5f10b3cd70786168b5afca2ff0567f4bf`.
The API/publisher remain image `sha256:2ff4ec17d97a9a4e0bf37e02e1611b40ff6378abb649df89f8b3e778ea3faa7d`.
The stopped experimental worker container is retained, not the resume selection.

## Recovery Evidence

The final tested worker passed 47 isolated worker/profile checks with Redis restart
enabled; qualification/controller/profile helpers passed 52 checks. Ruff and
`git diff --check` passed (line-ending warnings only). Final Tokyo preservation
comparison matched all original table hashes and catalogs, with 17,019 events.
The selected image's worker source SHA-256 matches the final tested source:
`eb9b3be95c066b58821c32f9b7883b849808e3dac1125711fcaab26e363395a5`.
Secrets/artifacts/reports remain ignored; main is unchanged and work is on ritwik.

Private backup directory:
`services/ml/artifacts/database-recovery/mumbai-migration/20261006/`.

Source backup `tokyo-application-before-mumbai.dump`: 15,494,848 bytes,
SHA-256 `4186003378fbbc961976f562bb3f91032853da39e61af59f5b94e7cf0295ffb5`.
Final writers-stopped backup `mumbai-application-after-diagnostics.dump`:
15,739,117 bytes, SHA-256
`6605fe5995a071c687e239a804713cba4a4a78ae17f740f4b1255426471aa9ee`.
It restored atomically into a NEW disposable PostgreSQL 17 database: all 18
table fingerprints and complete constraint/index/function/trigger/sequence
comparisons matched; all 18 restored tables retained RLS. This is recovery
evidence, not application performance evidence. The disposable target is stopped.

Restore using PG17 `pg_restore --exit-on-error --single-transaction --no-owner
--no-acl --use-list=mumbai-recovery.toc` into a fresh compatible destination.
The TOC omits only existing public schema metadata. Before any cloud consumers,
apply the destination-specific app privilege lockdown atomically and verify it;
`--no-acl` is not permission restoration. Never overwrite populated built-in schemas.
For rollback, first stop ALL cloud writers, back up and reconcile Mumbai-only
data (290 events beyond Tokyo, 487 beyond original local), then switch EVERY
consumer together. Preserve canonical Redis IDs/groups; do not flush queues,
delete volumes, discard the delta or allow divergent writes to both targets.

## Remaining Gates

Windows reverted to Leap Indicator 3/Stratum 0. Measured Windows and Docker clocks
are about 458-460 ms ahead of the DB (query uncertainty about 16-25 ms). Resync
from the agent session returned Access denied `0x80070005`. Application writers
are STOPPED; health records `clock_sync_required`, activation hold remains 1.
No further traffic was sent after confirming that mismatch. Clock-skewed runs
must not qualify; the controller now measures clocks before/after traffic and
refuses material skew before ingestion. The normal activation gate now requires
600 seconds, not the legacy 60-second minimum, and checks complete arrival counts.

1. Restore stable administrator-managed Windows time synchronization and verify
   Windows/Docker/DB offsets. The owner was notified; previous approval is retained.
2. Use both ignored `.env.application.local` and `.env.supabase-mumbai.runtime.local`
   with the Supabase override. Keep the same candidate run
   `c5b2dab3-0330-4a32-9ba7-82c85d311b40` and target/image pins; wait for history recovery.
3. Run valid-clock short 1/5 TPS checks. Only promising checks justify ten-minute
   tests at BOTH rates against this actual configuration, with zero expiries,
   full parity, complete durable actions and no duplicate/late effects.
4. Verify final readiness, Pass/Block execution, authorized Review resolution and
   same-run/Redis recovery on the qualified deployment. Bind deployment evidence
   to the Mumbai run/images without overwriting original local runtime approvals.
5. Release activation only after all gates pass under existing owner approval.

If valid-clock performance still fails, report the remaining measured costs and
consider an EXISTING host near Mumbai for API/worker/Redis, or explicit workload
changes. No suitable host or revised requirement is assumed; do not purchase
resources, keep increasing deadlines or claim clock repair guarantees peak success.
No ten-minute Mumbai rate has yet been qualified. Task 7 is not started.
Frozen model, Review 0.10/Block 0.25, 1000 ms deadline, fsync/synchronous_commit,
and the passing reserved-test report are unchanged; no reserved evaluation rerun.

Raw evidence: `services/ml/reports/mumbai-deployment/` (import checks, snapshots,
backup hashes, restore comparison, effective targets and checkpoint) and
`services/ml/reports/replay-load/` (stages, queues, pacing, parity and failures).
