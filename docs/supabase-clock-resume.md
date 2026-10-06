# Supabase Valid-Clock Verification

## Status - 2026-10-06

Owner confirmed Windows time synchronization. That manual action is COMPLETE;
do not ask for it again. Windows and Docker time checks passed. Task 5 remains
COMPLETE; Task 6 remains INCOMPLETE and activation is BLOCKED by measured
deployment latency. No scorer, policy, feature, deadline or durability change.
No retraining, reserved evaluation, Git commit/push or Task 7 work occurred.

Read this record before the historical clock blocker in
[the migration record](supabase-database-migration.md). The Supabase migration,
schema ledger, data preservation and prior recovery checks remain valid.

## Clock and Preflight

Windows reports Leap Indicator 0, Stratum 5, last successful synchronization
2026-10-06 13:36:42 Asia/Calcutta. Verified-TLS midpoint probes showed about
-2ms database-minus-Windows offset and approximately -3.3 to +1.8ms offset in
the API container, replacing the old roughly +1090ms error. These are midpoint
estimates: network RTT/2 uncertainty was about 70-85ms, not submillisecond proof.
Both authenticated TLS and explicit extra_float_digits=3 passed.

Docker was initially stopped and briefly returned startup HTTP 500 errors. The
existing installation was started hidden; its original engine and named volumes
became visible without reset, relocation, installation or changed RAM limits.
The early Compose attempt failed at image lookup; it was repeated only after the
original containers/storage were verified. No divergent local writes occurred.

Original sentinel retains 16,822 events, all 18 original table hashes unchanged,
default_transaction_read_only=on. The candidate run remains
c5b2dab3-0330-4a32-9ba7-82c85d311b40, application/postcommit-v1, 1000ms.
History recovery passed before traffic; all 16,945 pre-existing outbox events
were published. Every running service used the pinned Supabase target and exact
existing images; API activation hold stayed 1.

Environment: Docker 29.6.1, four CPUs, 1,998,864,384 bytes memory; existing
i5-6200U/8GB Windows host. Available Windows memory was 375,412 KiB during cold
engine startup, then 1,196,640 KiB after services stabilized. Browser/editor were
present, but no builds, training or separate regression suites ran during traffic.

Frozen manifest still:
1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696.
Reserved-report checksum still:
abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2.
Review=0.10, Block=0.25, sigmoid RF serving selection unchanged.

## Workload Results

| Controlled diagnostic | Attempted | Accepted | Scored | Final Expired | Ingestion failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 TPS, 30 seconds | 30 | 30 | 0 | 30 | 0 |
| Nominal 5 TPS, 10 seconds | 50 | 44 | 0 | 44 | 6 |

Normal offered rate was 0.999 TPS. Peak actual offered rate was 3.908 TPS;
it is NOT a sustained 5 TPS result or a qualification pass. Sender intervals
never caught up in bursts: minima 1000.07ms normal and 200.08ms peak, medians
1000.25ms and 200.25ms. Peak gaps reached 1422.27ms under backpressure. Server
acceptance intervals are recorded separately and can cluster after internal
waiting; do not mistake them for intentional producer bursts.

Normal sampled queue grew to six at 10s and seven at 20s. The ten-second peak
controller captured only its initial queue sample. Supplemental samples started
after peak work had settled and were zero; they do NOT establish a zero peak
backlog or a peak queue maximum. Final per-event waiting proves substantial
backlog; the exact peak count maximum is unmeasured.

Peak report initially read 29 Expired jobs and later 33 stage rows at different
read points. Nineteen feature-parity entries included missing, not-yet-created
snapshots. Final read-only reconciliation verified all 44 accepted peak events
Expired and published. All 1,607 candidate snapshots reproduced the exact shared
features and hashes, including the peak tails. Do not rewrite the raw report or
treat the initial missing snapshots as proven feature calculation errors.

All 74 new accepted events have one history row and one snapshot. No new results,
predictions/probabilities, simulated executions or confirmed fraud labels were
fabricated. No late execution occurred. Zero new timely score rows means new
offline/live SCORE parity remains unproven; historical FEATURE parity passed.

The normal precheck failed, so neither ten-minute qualification was run. The
short peak check measured distinct offered-load behavior, not a retry until pass.
No one-second sustainable scoring rate has been established for this deployment.
Do not describe 0 scored events as a mathematical maximum capacity of 0 TPS.

## Settled Timings

All accepted events, including expired tails, are retained in the final timing
evidence. Values below are milliseconds. Stage scopes overlap; batch durations
are shared by members and cannot be summed into a per-event total.

| Stage | Normal p50 / p95 / max | Peak p50 / p95 / max |
| --- | --- | --- |
| Ingestion pool waiting | 90.88 / 768.00 / 1382.65 | 1807.01 / 1974.01 / 2009.44 |
| Ingestion BEGIN | 148.02 / 160.23 / 165.65 | 146.65 / 158.54 / 841.28 |
| Idempotency statement | 148.92 / 173.68 / 224.51 | 147.55 / 162.00 / 228.99 |
| Event/audit statement | 157.87 / 169.01 / 204.94 | 151.63 / 167.96 / 181.67 |
| Ingestion COMMIT acknowledgement | 147.45 / 161.46 / 207.13 | 147.00 / 168.16 / 182.38 |
| Acceptance to assignment | 7594.64 / 13651.76 / 14197.61 | 19545.50 / 23158.73 / 23426.97 |
| History read | 153.52 / 164.27 / 511.56 | 152.19 / 159.88 / 171.59 |
| Feature calculation | 0.16 / 0.46 / 0.58 | 0.16 / 0.37 / 0.68 |
| Assignment statement scope | 612.73 / 650.44 / 971.68 | 461.87 / 626.31 / 660.52 |
| Checkpoint/expiry commit scope | 2751.71 / 3154.52 / 3154.52 | 2179.86 / 2754.52 / 2754.52 |
| Redis XADD | 3.96 / 36.44 / 335.96 | 3.01 / 47.96 / 85.76 |
| Publisher outcome UPDATE | 146.11 / 169.01 / 287.72 | 145.44 / 151.03 / 158.10 |
| Publisher COMMIT acknowledgement | 146.70 / 152.85 / 154.92 | 146.72 / 155.45 / 158.57 |

The earliest normal assignment was 1179.54ms after server acceptance, already
beyond the 1000ms scoring deadline before inference. The earliest peak assignment
was 2660.42ms. No actual new inference or successful decision-storage timing
exists because these attempts expired. Durable SCORED latency p50/p95/p99/max
are null, not zero or a successful speed claim.

SQL acceptance-to-terminal witnesses are PRE-COMMIT timestamps, not durable
scored latency: normal p50/p95/p99/max 8051.99/14179.78/14618.31/14725.79ms;
peak 19931.21/23534.97/23695.65/23802.06ms. A terminal-failure statement scope
near 0.5ms may only enqueue pipeline work; its batch commit scope is separately
retained. Likewise a stalled event loop can exceed a nominal Redis timeout;
configured bounds are not hard real-time scheduling guarantees.

No sampled database lock blockers. Active samples were normal CPU=8, ClientRead=55;
peak ClientRead=31, WalSync=1, CPU=1. Server history-query cumulative mean/max
0.270/4.694ms, publisher UPDATE 0.330/7.068ms, versus client scopes ~145-154ms.
These normalized server statistics are cumulative, not exclusive test windows.
track_io_timing and track_wal_io_timing are off; no zero-storage-cost claim.
fsync and synchronous_commit remain on. No durability or audit shortcut was used.

Inference from these measurements: repeated cross-region network round trips,
serial pipeline work and API pool contention dominate observed latency; current
evidence does not support another HDD/fsync fix or a model change as the remedy.

## Preservation and Evidence

Cloud now retains 17,019 events/history/snapshots, ledger 0001-0011; all outbox
rows are published. Candidate jobs: 1,237 existing Scored, 370 Expired. The source
still matches all 18 original fingerprints. There are 197 cloud-only events in
total (123 previous diagnostics plus 74 today); a rollback must reconcile ALL
197 and their audit/history, not only the earlier delta.

All cloud application writers are stopped; health is ready=false,
error_code=workload_gate_failed. The obsolete clock_sync_required hold is removed.
Original PostgreSQL and Redis remain healthy on their retained volumes. The
recovery-tested publisher fix, one-row cloud batch and 200ms budget are unchanged.

New native PG17 public backup:
services/ml/artifacts/database-recovery/20261005/sentinel-supabase-clock-resume-20261006.dump
15,494,848 bytes; SHA-256
1e21694caf6a5005e1c9c001c613cb86bbb372477e32462360e38aae87c78bff.
Archive blocks validated with pg_restore --exit-on-error --file=/dev/null.
This new archive was NOT fully restored into another DB; the prior cloud archive
has full 18-table/catalog/sequence/RLS restore proof. Preserve both checkpoints.

Ignored evidence directory: services/ml/reports/task6-supabase-clock-resume/20261006/.
Contains clock samples/uncertainty, preflight, effective services, readiness,
reconciliation, all 74 settled event timings, sanitized stage logs, server costs,
source preservation, final state and backup metadata. Raw logs were not copied.

Original reports remain:
- services/ml/reports/task6-application-load/20261006T082329110590Z/report.json
- services/ml/reports/task6-application-load/20261006T082658851109Z/report.json

## Pending Deployment Choice

The owner was asked which latency-lowering deployment path to investigate. No
response is assumed from a preselected option and no new paid resources/project
were created. Options, requiring measurement rather than a promise:

1. A closer Supabase project, such as Mumbai, while keeping the runtime on this
   PC. Verify actual Windows/Docker RTT and authenticated TLS before importing
   any data. Preserve Tokyo and both rollback configurations. A new project is
   an owner account/target choice, not an authorized silent target replacement.
2. An existing suitable host near Tokyo for Express, publisher, worker and Redis.
   Verify host access, capacity, recovery/storage and combined pool limits before
   deployment. No such host/access has been supplied; do not purchase one.

Mumbai and Tokyo are available specific regions; Supabase recommends choosing
the region closest to users for performance. [Official region guidance](https://supabase.com/docs/guides/platform/regions).
Placing database-intensive compute close to the database is also consistent with
[Supabase locality guidance](https://supabase.com/docs/guides/functions/regional-invocation);
this is an inference for our existing Node/Python runtime, NOT an Edge Functions,
SDK, Auth or Data API migration. No actual alternate-region RTT is measured yet.

After a target/host is selected: inspect and test it first, take and verify a
fresh writers-held backup, preserve/reconcile all application data, switch every
consumer consistently and prove history/order/deduplication recovery. Then short
valid-clock 1/5 TPS checks, followed ONLY if promising by full ten-minute 1 AND
5 TPS zero-expiry qualifications. Finally verify public readiness, automated
Pass/Block, authorized Review resolution and same-deployment restart recovery
before following the existing activation approval. Reserved test remains closed.

PENDING MANUAL ACTIONS - BLOCKING

Choose/provide the deployment path above; credentials stay in ignored local
environment files, never chat. Clock synchronization is already resolved.

PENDING MANUAL ACTIONS - NON-BLOCKING

None. Task 7 not started. Branch ritwik; main unchanged; no commit or push.
