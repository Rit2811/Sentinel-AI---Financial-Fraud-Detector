# Application Pipeline Qualification

## Controlled Deployment Recheck

2026-10-06: Windows time service is synchronized, polling every 64 seconds;
phase offset -1.889 ms. Actual scoring-image Docker/DB midpoint probes were
about -3 ms. Clock checks passed both before and after the latest traffic.
Clock setup is complete; no additional owner synchronization action is pending.

Actual parallel normal precheck `20261006T161643262336Z` FAILED: 24 Scored and
6 Expired of 30 accepted transactions, all published. All 24 scored results
matched offline, with zero worker/correctness errors and no invalid/late execution.
The earlier valid-clock parallel failure `20261006T153146964136Z` (12/18)
remains on record. No peak/full qualification followed these failed prechecks.

Durable scored-only latency p50/p95/p99/max was
815.768/960.210/988.839/996.969 ms; this excludes expired events and is NOT a pass.
Offered traffic was 0.998 TPS; median send interval 1000.202 ms, maximum 1029.704
ms, no catch-up sends. One acceptance interval was 477 ms despite paced sends;
ingestion jitter can compress server arrivals without a bursty load generator.

Expired events' median acceptance-to-assignment wait was 745.401 ms, maximum
1154.847 ms. Feature arithmetic median 0.291 ms, maximum 1.412 ms. Their
checkpoint/prediction/commit scope had median 461.106 ms, maximum 722.945 ms;
only three of six expired events reached inference (median 173.659 ms).
Stage scopes overlap and must not be added as independent totals. Publication
timestamps are pre-COMMIT and some checkpoints precede completed publication.
Acceptance-to-publication pre-COMMIT median was 531.608 ms for expired events,
versus 300.926 ms for scored events. Publication, inference and remote calls
show occasional spikes. There were no sampled lock blockers; one WAL-write wait
was sampled. WAL/IO timing is disabled, so storage dominance is NOT established.
Sparse 0/10/20-second queue samples were empty; this does not rule out transient
backlog. These results establish neither zero-expiry sustainable capacity nor
that closing browser tabs solves the performance problem.

Current actual data: 17,762 events, all published; ledger 12; candidate 2,350
terminal jobs (1,662 Scored/688 Expired). Cross-run checks found zero duplicate
history/snapshot/result/execution effects, invalid/late executions or prohibited
payload fields. fsync and synchronous_commit remain on. Readiness returned 503;
all application writers were then stopped. PostgreSQL, Redis and all data remain
preserved. Model, policy, one-second deadline and reserved results are unchanged.

New consistent backup `mumbai-after-controlled-normal.dump` is 16,156,963 bytes,
SHA-256 `605bcca7b04937b5623c800d5829f746ba63c7bfc9d19433d39079dc1a15d74c`.
Archive-content validation and a full restore into a NEW disposable PostgreSQL
17 database passed. All 18 table hashes, constraints, indexes, functions,
triggers, sequences and table RLS matched the stopped Mumbai snapshot. Original
databases and earlier backups remain intact. Frozen manifest and passing reserved
report checksums were rechecked unchanged, without another model evaluation.
Recovery proof: ignored `reports/mumbai-deployment/controlled-normal-backup.json`
and `controlled-normal-restore-verification.json`. Restore procedure remains the
PG17 single-transaction, no-owner/no-acl procedure below, with the corresponding
new `controlled-normal-recovery.toc`. Reapply destination-specific app permissions
before cloud use; never discard cloud-only records when rolling back locally.

Evidence: ignored `services/ml/reports/replay-load/20261006T161643262336Z/`
and `reports/mumbai-deployment/controlled-normal-{stage-analysis,final-state}.json`.
Task 5 COMPLETE; Task 6 INCOMPLETE, activation HELD. No further speculative tweaks,
deadline increases, paid resources or full workload retries are justified by this
failed precheck. A meaningful correction must address the measured waiting and
latency tails, preserve recovery safety, and pass short checks before both full
600-second workloads and final exact-deployment verification.

## Owner Clock Verification Update

2026-10-06: owner executed the stability helper successfully. PASS reports,
effective 64-second polling and fresh NTP updates verified. Initial verified-TLS
Windows/DB midpoint offset ~35 ms, scoring-image Docker/DB ~26 ms; Windows probes
held ~23-27 ms across 70 seconds, within the existing RTT/2 plus 25 ms tolerance.
This clears the immediate clock setup blocker, NOT full-load stability or Task 6.
No new scoring traffic, deadline change or activation occurred during this check.
Clock manual action is complete; canceled-prompt statements below are HISTORICAL.
Remaining gates: valid-clock parallel short1/5 TPS checks, ten-minute BOTH rates
with zero expiries, and final exact-deployment action/review/readiness/recovery.
Evidence: owner-clock-verification.json and owner-clock-stability-verification.json
under ignored services/ml/reports/mumbai-deployment/.

Latest checkpoint: 2026-10-06. Task 5 COMPLETE; Task 6 INCOMPLETE, activation HELD.
This supersedes earlier clock/serial-worker instructions in mumbai-deployment.md.

## Completed Engineering

- Mumbai migration retained source databases/volumes and all app data. Migration
  runner applied only additive 0012_bounded-scoring-checkpoints. All 17 existing
  data-table hashes and old guards/indexes/functions remained unchanged; the
  ledger has 12 records. The new function denies PUBLIC/browser-role execution.
- Ordered checkpoint writes now take one server call: median fell from about
  120 ms to 37 ms. Shared Python feature calculation and pending/status audits
  remain intact; only already-waiting batches of at most four are admitted.
- Final result/job/audit/action handling is one atomic synchronous statement,
  retaining deferred deadline guards. Normal terminal delivery only reads durable
  state; failure audits commit before ACK. Both formerly took about 110 ms and
  now take about 40 ms. No fsync/synchronous_commit relaxation occurred.
- API initializes/retains its bounded three connections before listening. Frozen
  single-event and unknown-category paths initialize before scoring readiness.
  No model/policy/calibration/file change, application effect or label is produced
  by initialization. Model and passing reserved-report checksums are unchanged.
- One coordinator still owns the run advisory fence. The new opt-in candidate
  has two reused scoring sessions sharing the SAME immutable RF instance. Only
  independent cards overlap; each card is serial, busy predecessors stop admission,
  and order errors block later work. Session work joins before the run fence is
  released. Original serial behavior remains the default and regression-tested.
- Cloud qualification tooling binds both 600-second reports to exact target,
  run, image and pipeline settings, preserving original local approval metadata.
  A load-qualified record alone does not authorize activation or replace the
  final action/review/readiness/recovery checks.

## Verification

180 backend unit tests; 49 backend integration tests; 62 combined serial/parallel
protocol tests (including real frozen-policy parity, expiry rollback, uncertain
commit recovery, duplicates, stream loss, shutdown fencing and enabled Redis
restart); 67 gate/tool checks passed. Ruff/ESLint and diff checks passed, with
line-ending/deprecation warnings retained. No reserved evaluation was repeated.
Nine simultaneous authenticated TLS connections passed capacity preflight.
Combined limits: API 3, publisher 1, coordinator 1, scoring sessions 2; the
diagnostic client/probe add 2. Optional consumer stays stopped.

Actual held serial deployment evidence under services/ml/reports/replay-load/:

| Report | Rate/Duration | Scored | Expired | Durable p50/p95/p99/max (ms) |
| --- | --- | ---: | ---: | --- |
| 20261006T131906008238Z | 1 TPS/30s | 30 | 0 | 747.728/924.674/975.756/993.319 |
| 20261006T132055313770Z | 5 TPS/30s | 110 | 40 | 806.182/979.314/997.330/998.699 |
| 20261006T132612454382Z | 2 TPS/60s | 107 | 13 | 746.973/892.636/943.834/997.173 |

These are NOT ten-minute acceptance or proven maximum/sustainable-capacity
results. Offered peak was 4.974 TPS; median send interval 200.264 ms, no catch-up
bursts. Peak queue samples: 5 pending at 10s (oldest .918s), 4 at 20s (.740s).
Expired attempts waited a median 765.307 ms before preparation; checkpoint,
inference and commit took another median 286.710 ms for their batches. Feature
arithmetic remained sub-ms in typical cases. No sampled lock blockers; WAL waits
were observed, but WAL timing was disabled, so zero timing counters are not zero
storage cost. Scored results matched offline; expired attempts executed nothing.
Actual Pass/Review/Block plus authorized idempotent review resolution passed in
replay-actions/20261006T132931925320Z. Original model decision remained immutable,
401/conflict checks passed, and no confirmed fraud/non-fraud label was created.
Image attestation preserves the original controller-reference fields and links
the actual before/after deployment pins; the diagnostic is not activation evidence.

Hardware: Windows exposes 8,296,152 KiB RAM, with 1,530,384 KiB free at the recorded
precheck. Docker has four CPUs/~2 GB RAM. Local Docker/Redis backing remains HDD;
app data/WAL are provider-managed. The one-second process sample included Docker
backend .875 CPU-seconds, editor processes .141/.094, and the diagnostic PowerShell
itself .969; it was taken before traffic. No builds/fixture stacks ran during load.

## Current Deployment Hold

Owner confirmed NO existing remote server. No server was provisioned/bought and
no deadline/rate requirement was relaxed. Candidate is mumbai-parallel worker
sha256:b21861472e2695ed3d3b9019a1a9fe8e81b1fd07ca2216a794a592ccedc468db,
API/publisher mumbai-ready sha256:692b5d9e6657d32ace5aa4e70286105b0db7ef2f755fc78b9975e14970559361.
Runtime stays .env.application.local plus ignored .env.supabase-mumbai.runtime.local,
run c5b2dab3-0330-4a32-9ba7-82c85d311b40, target
070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2.

Historical precheck 20261006T142814197995Z refused BEFORE traffic for about
815 ms clock skew. The owner subsequently ran the stability helper successfully;
current valid-clock parallel failures are recorded above. All writers are stopped.
Do not substitute isolated tests or old serial results for actual qualification.

Windows may correct offsets gradually and polling settings control synchronization;
see [Microsoft time-service settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings).
scripts/stabilize-clock.ps1 is administrator-only: saves peer/poll settings, refuses
domain-managed clocks, uses 64-second polling, invokes bounded measured correction,
and restores settings on failure. Owner execution is COMPLETE; no repeat approval
or canceled UAC prompt is pending. synchronize-clock.ps1 does not alter settings.

## Remaining Gates

1. Address the measured publication/coordinator waiting and latency spikes with
   a meaningful, recovery-tested correction; do not assume clock sync solved them.
   Check resources and actual Windows/Docker/DB offsets before further traffic.
2. Resume the held candidate and wait for history/session readiness. Run short
   1/5 TPS checks first. Only promising zero-expiry results justify ten-minute tests
   at BOTH rates. Retain all timing/queue/parity/expiry evidence, including failures.
3. Qualify exact Mumbai run/images/configurations in separate private metadata.
   Verify automated actions, human review, same-run and Redis recovery, no duplicate
   effects and no late execution on THAT final deployment; release hold only after
   all required evidence passes under existing owner approval.

No new model approval is needed. Frozen SHA-256
1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696;
reserved report abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2;
Review .10/Block .25; deadline 1000 ms; no learning/drift/retraining implemented.
Prior fully restored backup snapshot: 17,702 events, all published, 12 ledger entries; candidate
2,290 terminal jobs (1,626 Scored/664 Expired), no late effects/prohibited payloads.
Sources remain preserved; never flush Redis/delete volumes or discard cloud deltas.
Final private backup mumbai-after-pipeline-correction.dump, 16,096,968 bytes,
SHA-256 088f28b543b8f0ccc7283f98f7c6bddf35112a99be4599ed08b84ca383e6c3ca.
Recovery comparisons are recorded in services/ml/reports/mumbai-deployment/.
Work remains on ritwik; main unchanged; no new commit/push. Task 7 not started.
