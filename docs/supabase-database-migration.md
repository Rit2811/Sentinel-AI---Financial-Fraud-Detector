# Supabase Application Database Migration

Superseded deployment checkpoint: the application has now migrated from preserved
Tokyo to owner-supplied Mumbai. Read [Mumbai deployment](mumbai-deployment.md) first
for current target, verified backups, performance evidence and remaining gates.
The Tokyo details below remain historical recovery evidence, NOT a resume target.

## Latest Update - 2026-10-06

Read [valid-clock verification](supabase-clock-resume.md) before the historical
2026-10-05 measurements below. The owner completed clock sync and offset checks
passed. Valid-clock normal 30/30 and peak 44/44 accepted events still Expired;
six of 50 offered peak attempts failed ingestion. All accepted events published,
no execution, all 1607 candidate feature snapshots reproduce. Task 5 COMPLETE;
Task 6 INCOMPLETE, activation held for measured deployment latency. No full
qualifications after failed short checks. All cloud writers are stopped.
Cloud retains 17019 events/history/snapshots; the original source is unchanged
and read-only. Rollback must preserve/reconcile 197 cloud-only events, not the
older 123-event delta. Latest native backup is 15,494,848 bytes, SHA-256
1e21694caf6a5005e1c9c001c613cb86bbb372477e32462360e38aae87c78bff;
archive blocks verified, previous full cloud restoration evidence retained.
No model, thresholds, 1000ms deadline, durability, image or serving-code change.

## Current Status - 2026-10-05

**Migration and recovery verification passed. Task 5 COMPLETE; Task 6 INCOMPLETE.
Scoring activation is held. Performance testing is paused for Windows clock
synchronization, not approval of a different model or deadline.**

All cloud application writers are stopped. Original local PostgreSQL and Redis
remain running on their preserved volumes; local sentinel is read-only. Do not
restart local writers or remove that fence while cloud-only records exist.
React continues to use Express; no database credentials, Supabase SDK, browser
database access, Data API calls, retraining or feedback learning were introduced.

## Verified Target and Configuration

Owner supplied DATABASE_URL in ignored backend/.env, and the Supabase root CA
from Downloads/prod-ca-2021.crt. The verified destination is the existing Session
pooler in ap-northeast-1, port 5432, database postgres, PostgreSQL 17.11.
Non-secret tenant/host/database identity pin:

`084cfe3ed139d7af8191b42278c4947dcf399fa01256041711a844e1d428e28f`

The URL/password are never printed here. backend/.env has dotenv whitespace
that Docker env-file cannot parse; a separate ignored .env.supabase.local was
generated through structured environment loading. Original .env.task6.local
and its image/run metadata remain unchanged.

CA: ignored secrets/supabase-root.crt, valid until 2031, file SHA-256:

`700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`

Authenticated hostname-verified TLS passed with existing Node and Python drivers
on Windows and in Docker. Node reports authorized TLSv1.3; Python reports
pgconn.ssl_in_use. pg_stat_ssl=false is the pooler-to-backend internal hop, not
the external application's verified client connection. No TLS bypass was used.

The owner's screenshot confirms Free-plan 500 MB quota, then 26 MB dashboard
usage. SQL size before import was 10,770,099 bytes and immediately after import
88,987,315 bytes; dashboard and SQL size are different measures. Eight concurrent
authenticated sessions passed admission. Server max_connections=60 is not proof
of the customized pooler allowance. No upgrades were purchased.
See [official connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).

infrastructure/compose.supabase.yaml configures the API, publisher, optional
legacy consumer and worker with the same verified destination and read-only CA.
API pool max=3; publisher=1; optional consumer=1; worker=1 persistent session.
Maximum runtime budget is six with the optional consumer, plus two benchmark
sessions, excluding administration. Only API/publisher/worker ran in the trial.
Worker and controller require the exact external target pin; original local and
isolated fixture guards remain intact. Public scoring readiness stays held.

## Data Migration and Preservation

Source: PostgreSQL 16.4 sentinel at localhost:15432; migrations 0001-0011.
Writers were stopped before snapshot. All original outbox events were published,
all jobs terminal, all Redis groups had zero pending deliveries. The held
one-second candidate c5b2dab3-0330-4a32-9ba7-82c85d311b40 had lag zero and was
reused in the cloud. Older null group lag is not proof of zero unseen work.
Redis was not flushed or replaced.

The source public-schema dump restored into NEW sentinel_supabase_recovery_20261005.
All 18 content fingerprints, 33 indexes, 12 functions, 23 triggers and sequence
states matched. All 106 constraints remain; one merchant_category CHECK was
equivalently regrouped by PostgreSQL. Raw definition equality for that CHECK is
false and was reviewed explicitly, not ignored.

Before import, the destination public had no tables/functions. A native PostgreSQL
17 backup of the existing destination was created and its archive blocks validated.
Native pg_restore generated app SQL with ownership/ACL adaptation and a supported
TOC selection omitting public schema creation/comment/ACL changes. The application
restore and app-only protection were applied in ONE psql transaction with
ON_ERROR_STOP. Supabase built-in schemas, tables and schema ACLs were preserved.

All imported tables have RLS enabled with no browser policies. Imported tables,
sequences and functions revoke access from PUBLIC, anon, authenticated and
service_role. Existing immutable/audit triggers remain active. Required plpgsql
was available; no extension installation was needed. No raw training CSV, model,
raw card number or fraud-label columns were uploaded.

Import verification passed all 18 table hashes and binary float values, indexes,
functions, triggers and sequences, with the reviewed CHECK regrouping above.
The API's repository migration runner returned **No migrations to run**; the
restored ledger has all 11 entries and was not reset or replayed.

A discovered output-format difference was corrected without rewriting data:
Supabase defaults extra_float_digits=0 versus local=1. Canonical verification and
every application session now SET extra_float_digits=3. Node's startup option
alone did not persist the desired setting through the pooler; awaited onConnect
initializes it before leasing a new connection. The worker initializes precision
and SQL timeouts explicitly. The first formatting-induced startup integrity flag
was released only after independently verifying every original 1,410 feature
snapshot and durable history, with no activation release.

After diagnostics, Supabase retains 16,945 events/history/snapshots: the original
16,822 plus 123 new accepted events. Every new accepted event is Expired; no
probability, successful decision, execution or fraud label was fabricated.
The original source still matches all 18 pre-migration hashes. It is fenced with
default_transaction_read_only=on, leaving volumes and data intact.

## Measurements and Clock Gate

Before trusting workload outcomes, time alignment was measured from BOTH Windows
and the API container. Supabase was approximately **1,090 ms ahead** of their
warm-query midpoint. That exceeds the complete 1,000 ms deadline; Windows
reports Leap Indicator 3 (not synchronized), Stratum 0. A normal
`w32tm /resync` attempt failed with access denied 0x80070005.

The retained diagnostics are failures, NOT performance qualification and NOT
evidence for activation or a longer deadline:

| Diagnostic | Attempted | Accepted | Final Scored | Final Expired | Other |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 TPS / 30s | 30 | 30 | 0 | 30 | zero executions |
| 5 TPS / 30s | 150 | 93 | 0 | 93 | 57 ingestion failures; zero executions |

Reports:
- services/ml/reports/task6-application-load/20261005T165507504325Z/report.json
- services/ml/reports/task6-application-load/20261005T165822569498Z/report.json
- services/ml/reports/task6-supabase-migration/diagnostic-reconciliation.json

The peak offered rate was 4.626 TPS, NOT a demonstrated sustained 5 TPS. Send
interval minimum/median were 200.09/200.22ms; none were catch-up bursts. The
1 TPS rate was 0.999 TPS with 1,000.27ms median send interval. Acceptance pacing
and client pacing are recorded separately.

The peak report initially saw only 72 durable expiries and some absent snapshots
while the worker was behind. Later stage queries saw 76; these were different
read points, not a single atomic measurement. Twenty-five initial feature-parity
failures included not-yet-created snapshots. Final reconciliation found all 93
accepted peak events terminal and published, and restart reproduced ALL 1,533
candidate snapshots. Do not treat temporary missing snapshots as zero durations
or replace the original report. No cloud score-parity success is claimed when
zero new transactions scored. Historical features and stored score bytes matched;
new timely offline/live score parity still requires qualifying traffic.

Observed stage evidence before correction:
- Network query/ack round trips generally 150-195ms; startup samples include
  connection establishment and must be distinguished from warm queries.
- Normal median pool wait 169.93ms, ingestion BEGIN/idempotency/event/COMMIT
  176.97/171.91/180.67/171.68ms.
- Peak median ingestion pool wait 1,912.55ms, with a 2,000.99ms maximum.
- Normal accepted-to-assignment queue median/max 6,798.52/11,934.26ms; peak
  12,879.86/19,972.50ms for captured expired stages. Queues grew, not isolated
  tail spikes: sampled normal max six, peak max 33.
- History-read median ~181-191ms versus feature calculation ~0.13-0.15ms.
  No new inference/decision-storage timing is available where inference never
  ran. Durable scored-latency percentiles/maximum are null, not zero.
- Normal checkpoint/expiry commit scope median 2,831.35ms; batch scope is shared
  by members and overlaps inner stages, so stages must not be summed naively.
- No sampled lock blockers; normal active samples had ClientRead=41, WalSync=1,
  CPU=3; peak ClientRead=49, DataFileRead=2, CPU=3.
- Server normalized history-query mean/max 0.190/3.689ms and publication UPDATE
  0.357/7.068ms, much lower than client scopes. These server stats are cumulative,
  not an exclusive workload window. Disk/WAL timing counters were disabled, so
  zero recorded I/O milliseconds is NOT proof of zero storage cost.

Cloud data_directory is /data/pgdata. Physical disk, WAL symlink/backing device
and service host contention cannot be inspected using the supplied PostgreSQL
connection. Do not infer SSD placement or equivalence with an isolated tmpfs DB.
Local host: i5-6200U, two cores/four threads, 8 GB RAM; Docker four CPUs/1.862GiB.
Brave/VS Code/Docker Desktop were present; no image builds or model evaluation
ran during diagnostic traffic. Evidence is in network-baseline.json,
storage-placement.json, server-query-costs.json and the two clock comparisons
under services/ml/reports/task6-supabase-migration/.

Clock skew is a demonstrated correctness blocker; network and pool/queue costs
are also measured. Do not promise synchronization alone will satisfy latency.
No reliable one-second cloud scoring throughput has been established.

## Measured Publisher Correction and Recovery

Four-row publication repeatedly exceeded the unchanged total 200ms Redis
publication budget because each remote outcome UPDATE acknowledgement took
about 196ms. Prefix acceptance could roll back repeatedly. The single-connection
pool additionally attempted to acquire a failure-record connection before
releasing the original rolled-back connection, preventing retries from progressing.

The correction releases that connection AFTER rollback and BEFORE durable CAS
failure recording. Unknown COMMIT still destroys the connection and inspects
durable state on recovery. Success still commits publication once; no weakened
fsync/synchronous_commit, early publication mark or early ACK was introduced.
The Supabase override uses batch size ONE, retaining the same ordering fence,
bounded Redis timeouts and existing 200ms budget. Scoring deadline stays 1000ms.

Regression tests cover a one-connection pool, Redis failure and uncertain XADD
acceptance with canonical IDs and one downstream receipt. Test injection was
corrected to pause Redis at XADD rather than before slow DB work and to distinguish
publication COMMIT from failure-record COMMIT. Original assertions remain.

All 123 accepted events ultimately published with no dead letters or unfinished
jobs. Three actual cloud duplicate deliveries left jobs/history/snapshots at three
each and predictions/results/executions at zero. Redis pending and lag returned
to zero. Same-run worker restart revalidated all 1,533 snapshots and retained the
same history/job counts. This demonstrates expired-event recovery, not timely
Pass/Review/Block execution on the cloud. No post-correction timing test was run:
the administrator clock gate must pass first.

## Backup and Rollback

Ignored artifacts directory: services/ml/artifacts/database-recovery/20261005/.

| Backup | Bytes | SHA-256 | Verification |
| --- | ---: | --- | --- |
| sentinel-supabase-20261005.dump | 15,334,257 | 77ea93b7b9126cadf01e58b60a8feddea9e59fb8b012772d622808c1277eebe9 | full local restore, 18 hashes |
| supabase-before-import.dump | 361,589 | 9247116a9d23fffe3956b63e6c5a5022d35acf37f666371900f5386e2e5b6d5d | native PG17 archive blocks validated |
| sentinel-supabase-after-tests.dump | 15,437,446 | 9230e04bd119978dc68d8e333bb036649c0ae8230701532f23c52cf7f9b959d3 | full NEW isolated PG17 restore, all 18 hashes |

Final cloud backup was taken with all writers stopped. Restored using native
PG17 pg_restore --exit-on-error --single-transaction --no-owner --no-acl and
cloud-recovery.toc, which omits only existing public schema metadata. All table
hashes, constraints, indexes, functions, triggers and sequence states matched
EXACTLY against the final cloud snapshot; all 18 restored tables retained RLS.
This disposable tmpfs restoration is recovery evidence, NOT performance evidence.
Test/recovery containers were stopped; original application volumes were not
deleted or reset.

For cloud recovery, restore to a fresh compatible PG17 target using the recorded
TOC/ownership adaptation, compare all catalog/data checks, and reapply imported
object privilege lockdown in the same transaction before allowing consumers.
--no-acl intentionally does not recreate the destination-specific browser-role
revocations; RLS alone is not a substitute for that full permission verification.
Do not overwrite a populated Supabase public or alter its built-in schemas.

For local rollback: stop ALL cloud writers first, retain the final cloud backup,
and reconcile its cloud-only 123 events/history/audit with the original source
before resuming local writers. Do not silently discard the delta. Preserve Redis
event identities/groups. Only after that reconciliation, remove the local
read-only fence with ALTER DATABASE sentinel SET default_transaction_read_only=off
from an administrative database, verify .env.task6.local and qualified images,
and switch every consumer together. Never permit both targets to accept writes.

## Verification and Resume

- Backend: 175 unit tests, 49 integration tests passed on isolated fixtures.
- Python worker/cloud/controller checks: 80 passed, one opt-in restart skipped;
  that isolated Redis restart was then explicitly enabled and passed separately.
- Initial cache/temp permission and timing-injection failures were retained in
  the work record and resolved by workspace-local temp directories and precise
  injection boundaries; final serial reruns passed.
- ESLint, Ruff and git diff --check passed. No database configuration/CA reference
  was found in frontend. Secrets, dumps, generated SQL, reports and runtime
  environments are Git-ignored.
- Task 5 manifest unchanged:
  1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696.
- Reserved report unchanged:
  abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2.
  No reserved evaluation was repeated.
- Current cloud API/publisher image:
  sha256:2ff4ec17d97a9a4e0bf37e02e1611b40ff6378abb649df89f8b3e778ea3faa7d.
  Worker: sha256:25de48875339152ea7a143313fd119f484b2acdd03a09476c93587c2e031af13.
  Original qualified image/runtime pins were not promoted.

**PENDING MANUAL ACTIONS - BLOCKING**

Clock synchronization is COMPLETE; do not request another administrative resync.
Select/provide the measured deployment path in supabase-clock-resume.md: a closer
verified DB project or an existing host near Tokyo. No new paid resource or
project is authorized by a preselected choice. Credentials remain local/ignored.

The following command remains the old Tokyo deployment's controlled-resume
command, NOT an instruction to repeat failed tests or activate scoring. After a
deployment choice, verify the effective target/configurations and recover history:

```powershell
docker compose --env-file .env.application.local --env-file .env.supabase.local -f infrastructure/compose.yaml -f infrastructure/compose.supabase.yaml --profile scoring up -d --no-deps api publisher scoring-worker
```

Wait for history/Redis recovery, ensure no competing builds/writers, then run
short controlled 1/5 TPS checks with external target pin and current images.
Only promising results justify ten-minute 1 TPS AND 5 TPS tests. Require zero
expiries, accurate arrival pacing, full offline/live parity, no duplicate effects
or late executions. Then verify final readiness, automated Pass/Block, authorized
manual Review resolution and restart recovery on that same deployment before
following the existing activation approval record.

If valid-clock short tests fail, report measured remaining network/pool/pipeline
costs and viable deployment-locality/workload options. Do not blindly increase
deadlines, buy upgrades or enter another speculative optimization loop.

**PENDING MANUAL ACTIONS - NON-BLOCKING**

None. Task 7 not started. No migration commit, push or main-branch change.
