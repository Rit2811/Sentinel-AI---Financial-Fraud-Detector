# Task 6 Verification Record

## Latest Storage/Pipeline Correction (2026-10-05)

Read [the correction record](storage-and-pipeline-correction.md). No SSD is
available; actual data/WAL are Linux ext4 within an HDD-backed Docker virtual
disk. Original data was backed up with writers stopped, restored independently
and verified across 18 table content hashes and 106 retained constraints.
All original rows still match after qualification. Actual one-second normal
qualification PASSED 600/600 over ten minutes, p95 549.259ms, max 951.522ms.
Final paced short peak FAILED 294 Scored/6 Expired at nominal 5 TPS/60s;
all scored parity and no late execution passed. Full peak was not attempted
after the failed short check. Task 6 remains incomplete; activation is held.
Stream audit COMMIT/ACK boundaries, publication waiting, startup reconciliation
and paced arrivals were corrected using measured evidence. Existing publisher
recovery is preserved with the same total 200ms publication budget.
65 worker/tool/recovery checks (64 plus focused startup), 25 final tool checks,
13 publisher integration/recovery checks and 156 final backend unit checks
passed. An actual same-run restart retained all six candidate table fingerprints.
Candidate worker is stopped, restart disabled; previous qualified API/publisher
configuration is restored. Original private runtime/env hashes are unchanged.
Later one-second evidence supersedes the historical status immediately below.

## Latest Two-Second Trial (2026-10-05)

The owner authorized a diagnostic two-second deadline while retaining the
original one-second requirement and activation hold. Full evidence, storage
placement, stage timings and recovery tests are in
[the trial record](two-second-diagnostic-trial.md). Migration 0011 is applied
to actual `sentinel`; the original run remains 1000ms. A combined-commit
worker passed 85 ML/recovery checks. Actual full 1 TPS/600s passed 600/600,
but full 5 TPS/600s failed with 2927 Scored/73 Expired, exact scored parity
and no late execution. Therefore no revised deadline was adopted, and Task 6
remains incomplete. The diagnostic worker was stopped; previous qualified
API/publisher images were restored and verified. Public scoring readiness is
HTTP 503. All older deployment statements below are historical snapshots and
must not be treated as the current container state.

## Current Status

Task 5 passed for the immutable sigmoid RF package; its reserved test was
evaluated once with owner authorization. Task 6 remains incomplete. Application
storage is migrated and connected functionality is tested, but sustained peak
deadline compliance on the actual persistent application database has failed.
Application qualification ran with a stable identity; general scoring activation
is blocked. The worker was stopped between the earlier measurements; see the
latest diagnostic status above for the current hold.

Latest publisher engineering checkpoint: see **Publisher Commit Reduction** at
the end of this record. The owner explicitly authorized its implementation and
testing, NOT activation or weaker durability. The previous unanswered-approval
statements below are historical and no longer block this engineering change.

This record supersedes earlier status statements in `task-6-worker-status.md`.
No model, calibrator or policy was changed during these workload experiments.

## Application Database and Recovery

The original Docker WSL engine and `sentinel-ai-postgres-data` volume returned.
Actual `sentinel` on localhost:15432 now has migration ledger entries 0001-0009.
The populated recovery checkpoint contained 863 events/jobs/history/snapshots, 156
private predictions, 138 public results/executions, 725 Expired and one review
resolution. Later qualification workloads added records; these are checkpoint
counts, not current live totals. Earlier zero-count statements are historical.
The six-migration backup restored into NEW isolated
`sentinel_worker_recovery_probe`: six ledger entries and 12 public tables.
No application database or volume was reset/replaced.

Backup SHA-256:
`9e241a1a150e6d716d09ef467ce42762f6aa57040db24616cbece96720cc8774`.

## Functional Verification

20 connected worker checks passed after batching: all simulated actions;
individual feature snapshots/history; duplicates/lost ACK; actual process death
before commit and after commit before ACK; history restoration; Redis stream
loss and actual disposable Redis restart; database connection termination;
late inference; retry exhaustion; poison messages; run ownership and ordering.
One batch test proves an expired transaction does not discard a timely peer.
Only explicitly isolated services were used for destructive tests.

33 backend integration checks passed, including review resolution, concurrency,
immutability and commit deadline guards. Four runtime gate checks passed:
incomplete peak duration, expired outcomes, different package and inadequate
offered traffic prevent activation. A local temporary-directory permission
error was resolved using a fresh ignored workspace directory.

Worker batches at most four already-waiting attempts, without waiting to fill a
batch. Features are assigned in canonical acceptance order before inference;
each transaction retains its own deadline, terminal state and committed action.
The same frozen scorer computes batch probabilities. Failed/historical load
reports remain preserved. Model/test metrics were not used for further tuning.

## Load Evidence

Both API and publisher now run with the worker on the same isolated Docker
network. Image identities are pinned for each run. Publisher polling is 50 ms,
worker idle blocking is 50 ms and HTTP result polling is 100 ms.
Reports record VM resources, stored outcomes, HTTP visibility, queue growth,
failures and offline/live feature/probability/action parity. PostgreSQL fixture
storage is tmpfs; passing it would still need application readiness verification.

| Report directory under `services/ml/reports/task6-worker/` | Workload | Outcome |
| --- | --- | --- |
| `20261002T141356566271Z` | Mixed host/Docker, 5 TPS, 30s | 131 scored, 19 expired |
| `20261002T141819948067Z` | All Docker, 5 TPS, 30s | 150/150 scored; maximum acceptance-to-visible result 466.42 ms |
| `20261002T142139594568Z` | All Docker, 1 TPS, 60s | 60/60 scored; maximum 485.992 ms |
| `20261002T142355372658Z` | All Docker serial worker, 5 TPS, 600s | 2,917 scored, 83 expired; peak gate FAILED |
| `20261002T143852418090Z` | All Docker batch worker, 1 TPS, 60s | 60/60 scored; p95 343.799 ms, maximum 591.701 ms |
| `20261002T144110722485Z` | Batch worker, requested 5 TPS/600s | Resource-stressed run FAILED; actual elapsed 1,793.956s |

The last stressed run recorded 1,068 scored and 1,923 expired in durable storage.
Client observations differed: 1,068 scored, 1,915 expired, five observation
timeouts, 2,988 confirmed acceptances. Some requests committed without a confirmed
HTTP response. All 1,068 executions were checked: zero invalid/late executions.
Its 437 reported failures include offline parity comparisons built from incomplete
client-confirmed history; those comparisons do not establish a worker feature bug.
That report is retained unchanged, with this limitation explicitly recorded.

The harness was corrected to build reference history from canonical accepted
attempts, including commits with lost HTTP responses. It now records actual
offered TPS, producer lag and confirmed versus durable acceptances. A scheduled
5 TPS test that cannot offer that rate is not a passing peak test. Runtime gates
require at least 99% of the configured average rate, accounting for request timing
at the interval boundary, plus every attempt timely scored and full parity.

## Resource Investigation

During stressed runs the 8 GB Windows host had only about 730 MB free RAM.
Worker cycles stalled for more than three seconds, across both database and
transport work. Docker's WSL VM reported 4 CPUs and 4,061,409,280 memory bytes,
despite the owner's intended 2 GB setting. No user `.wslconfig` existed, and only
`docker-desktop` was running in WSL. WSL memory pressure is a plausible contributor;
the observations do not prove it is the sole cause.

Reviewed proposal `infrastructure/wslconfig.task6` sets only `[wsl2] memory=2GB`.
On the owner's continuation request, it was installed as the previously absent
`C:/Users/lenovo/.wslconfig`; Docker Desktop was stopped, WSL shut down and Docker
restarted. No volumes were removed. Docker now reports 1,998,868,480 memory bytes.
The original application ledger still contains 0001-0008 and zero events.
Only Docker's WSL distribution was running before this restart. This global WSL
cap is reversible by removing the newly installed file and restarting WSL.
Microsoft documents that WSL
memory is configured globally and changes take effect after WSL restarts:
[WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

## Remaining Gates

1. Resource configuration is applied and original application storage verified.
2. Run the corrected harness at 1 TPS and at 5 TPS for ten minutes. Retain all
   failures; require sustainable offered traffic, timely results and full parity.
3. Prepare ignored local configuration with `python -m fraud_ml.runtime`; it
   verifies the immutable package, passing final-test report, workload reports
   and exact measured image identities before issuing credentials/run identity.
4. Activate the approved scorer against actual `sentinel`, verify readiness and
   authoritative API results, then record deployment/restart evidence.

Do not repeat the reserved test. Keep the same application run ID across worker
restarts. The four-model comparison remains a separate development track.
Infinite hung inference still requires process recovery; database deadline guards
prevent late execution. No feedback learning, drift monitoring or retraining exists.
Task 7 is not started.

## Latest Workload Checkpoint

`20261002T154929520773Z` did not save a report: all 60 transactions were scored,
but the attached Docker CLI timed out after the container had stopped. Its logs
are retained; it is not passing workload evidence. The harness now terminates
only that stuck attached CLI after successful container stop, then saves evidence.

`20261002T155456708218Z`: 1 TPS/60 seconds, 60/60 scored, no failures or expiries,
60 feature/probability/action parity rows. Durable decision p95 280.579 ms,
maximum 339.742 ms; HTTP visibility p95 381.723 ms, maximum 442.709 ms.
Offered traffic was 1 TPS; sampled queue maximum one.

`20261002T155724579646Z`: 5 TPS/600 seconds, 2,994 scored, six expired,
zero worker failures. Scored HTTP visibility p95 469.577 ms, maximum 1,947.835 ms.
This remains FAILED evidence, not authorization to activate.

The approved deadline is acceptance through durable decision storage, not HTTP
polling/response delay. Historical reports exposed pre-COMMIT decision/execution
timestamps; those are lower bounds, not durable commit-acknowledgement proof.
Deferred triggers run before final WAL flush/acknowledgement. Consequently the old
load reports cannot prove this durability requirement, even when all rows scored.
The postcommit-v1 protocol below closes that verification gap. The deadline,
expiry behaviour, model and thresholds remain unchanged.
Safe generated cold-history cases cover all three actual frozen-RF regions.

## Interrupted Run and Resume

`20261002T161025660602Z` spans 47,360.663 seconds (over 13 hours), not ten
minutes. Its producer lag reached 46,791.449 seconds. Durable outcomes are 2,536
scored and 464 expired; all 2,536 scored rows matched offline parity and no late
execution occurred. Six reported failures include ingestion timeouts and worker
dependency outages. Offered traffic was only 0.06335 TPS. This is interrupted,
FAILED evidence, not a valid sustained 5 TPS measurement or an activation pass.

The resumed harness requests Windows idle-sleep prevention only while the test
process runs, then restores its previous thread execution state. It does not
change the power plan, force the display on or override deliberate user sleep.
It also stops production after a scheduling pause over five seconds rather than
issuing a catch-up burst. Such a run retains its failure and cannot pass activation.
See [Microsoft's execution-state API](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).
The actual application still has eight migrations and zero events at this resume.

`20261003T053222006314Z`: resumed 1 TPS/60 seconds, 56 scored and four expired,
zero worker failures. This is FAILED evidence. Windows resource counters showed
Defender at 77% of one CPU and VM I/O pressure (10-second full pressure 3.62%).
This is evidence of competing load, not proof of a single root cause. Per-cycle
flushed diagnostics are now disabled in measured workloads to match serving;
failure logging, state/attempt audit, snapshots and latency evidence remain enabled.
No security software was disabled or excluded and no user applications were closed.

`20261003T054206354860Z`: production-equivalent logging, 1 TPS/60 seconds,
58 scored and two expired, zero worker failures; still FAILED. Removing diagnostic
logging alone did not establish deadline compliance.

An isolated Docker-network workload client now exercises the same HTTP ingestion,
publisher, Redis, frozen worker, durable storage and result retrieval, without
Windows-to-VM client traffic. Reports explicitly identify this controller topology;
they must not be presented as proof of Windows-client or public-network latency.
The controller refuses an application endpoint/database and generates only safe
label-free events. All 13 focused verification-tool tests pass. Model and scoring
worker logic are unchanged. The updated image still needs measured workload gates.

## Strict Activation Acceptance (Owner Receipt 2026-10-03)

The owner explicitly requires zero expiries during a controlled 1 TPS normal
test and a ten-minute 5 TPS test, with full offline/live parity and no late
execution. Activation stays blocked until both pass. This supersedes the earlier
unresolved expiry-tolerance question; do not request this approval again.
Profile queue waiting, features, inference and database writes. If the target
cannot be achieved, report the measured bottleneck and sustainable throughput
before proposing different limits. Never repeat the reserved model test.

Latest pre-fix peak: `20261003T060934687315Z`, exactly 5 TPS over 600 seconds:
2,915 scored, 85 Expired (2.83%), zero worker errors, exact parity for all 2,915
scored rows. Sampled queue maximum eight. This is FAILED activation evidence.
The preceding normal run `20261003T060619271668Z` scored 60/60 without errors,
but its old timestamps alone do not establish postcommit deadline compliance.

## Postcommit Deadline Proof

Migration 0009 adds immutable `scoring_predictions` and a run-scoped
`postcommit-v1` durability contract, preserving old fixture evidence unchanged.
The worker uses synchronous commit and refuses PostgreSQL with fsync disabled.
A prediction commits first, without any simulated effect. Only after its commit
acknowledgement may a separate transaction finalize the original probability
and decision. A database-clock witness checks the one-second deadline; existing
deferred execution guards still reject late effects. The database rejects a
same-transaction prediction/result shortcut and mismatched original evidence.

After a crash, a committed prediction is reused without inference. If its
confirmation is already late, the attempt expires with no result/execution.
Unfinalized/late predictions remain private audit evidence; they are not exposed
as scored results or used as feedback labels. The API becomes ready only for the
new contract. Runtime preparation rejects all precommit-only workload reports.
The scoring deadline ends at durable original prediction storage; confirmation
is conservative and also must precede expiry. Human review remains independent.
See [PostgreSQL synchronous commit semantics](https://www.postgresql.org/docs/16/wal-async-commit.html).

Opt-in stage profiling records safe event/run identity, acceptance-to-assignment
queue wait, history reads, feature calculation, inference, and transaction-context
completion including commit acknowledgement. No card tokens, payloads, labels or
feature values are logged. Non-blocking diagnostic logs can drop records; the
immutable database remains the authoritative outcome/history evidence.

## Latest Recovery Backup

The actual application's eight-migration backup is
`services/ml/artifacts/database-recovery/20261003/sentinel-schema8-before-activation.dump`.
SHA-256 `aff1d072fd7dce544f3a30f6c99b5aa2618a560ebe737aba0ecc3ccc0ff65c23`.
It restored successfully into NEW isolated database
`sentinel_application_schema8_recovery_20261003`: eight ledger entries,
17 public tables and zero events/results/executions. No application volume reset.

## Profiled Safety-Fix Verification

Actual `sentinel` now has migrations 0001-0009, applied by the repository runner
after isolated verification. Counts remain zero events, results and predictions;
no fixture traffic was inserted into the application target. Compose API,
publisher and worker all address the same original `postgres:5432/sentinel`
service, exposed as localhost:15432. Original volume and data are preserved.

39 focused worker/tool tests passed (40.57s), including actual delayed prediction
COMMIT, same-transaction bypass rejection, committed-prediction recovery, worker
crashes, Redis restart, retries, duplicates and per-transaction batch expiry.
The batch fixture's induced delays were separated more clearly (0.8s arrival
gap and 0.3s inference), preserving the real one-second deadline and assertions.
Prior failing test output is not presented as passing verification. Nine exact
readiness tests passed (1.527s); a prior sandbox cache permission failure was
resolved by specifying a fresh ignored cache, not deleting repository files.

Profile `20261003T070407238547Z`: 5 TPS/60s, 300/300 scored, zero expiries/errors,
300 parity checks and zero invalid/late executions; offered 5.0 TPS, sampled queue
maximum two. New-contract latency p95 480.011ms, maximum 781.983ms.
This short run is NOT the ten-minute peak activation gate.

| Profile Stage | p95 ms | Maximum ms |
| --- | ---: | ---: |
| Acceptance to assignment queue | 241.415 | 620.126 |
| History read | 6.107 | 20.491 |
| Feature calculation | 0.685 | 10.493 |
| Assignment including commit acknowledgement | 38.554 | 74.642 |
| Preparation including commit acknowledgement | 24.822 | 67.554 |
| Inference (284 already-waiting batches) | 149.429 | 312.427 |
| Prediction commit acknowledgement | 17.718 | 31.904 |
| Execution commit acknowledgement | 28.264 | 60.796 |

2,475 timing records are preserved in that ignored report directory's worker log.
Waiting and inference dominate this sample, not feature computation. Queue wait
includes upstream publication and scheduling; this does not establish one unique
host/VM root cause. The measured short-run throughput is 5 TPS with zero expiry;
long-run sustainable zero-expiry throughput remains unproven until the full gate.

## Failed Profile and Targeted Runtime Changes

`20261003T071947871634Z` requested 5 TPS/600s but the producer stopped after
845 attempts because its scheduling lag exceeded five seconds. The report's
600.210s observation window includes the remaining idle time, so average offered
traffic was only 1.4083 TPS. This is INVALID controlled peak evidence and FAILED
activation evidence: 528 scored, 317 expired, exact parity for 528 scored results,
zero invalid/late executions, one producer-pause failure and sampled queue max eight.

The 5,769 preserved stage records show queue p95 1,586.558ms/max 3,196.841ms;
assignment/commit p95 154.404ms/max 1,017.388ms; inference p95 246.470ms/max
431.085ms; result completion p95 85.498ms/max 1,224.397ms. Feature calculation
p95 was only 1.250ms. This points to waiting/scheduling and database completion
rather than feature arithmetic. It does not isolate a single kernel/host cause.
A host CPU sample reported 380% across four logical processors, with vmmem,
Docker backend, browser and system services competing for CPU. A separate
container sample recorded PostgreSQL 237.73%, API 83.74%, worker 44.28% and
publisher 15.98%; these snapshots are not synchronized averages or causal proof.

Ready-heartbeat writes now occur at most once per second, inside the existing
five-second readiness freshness window. Failure/blocked/stopped transitions remain
immediate, and durable assignment/decision/action writes are not throttled.
Optional profiling now buffers safe timing records and emits once per cycle,
instead of flushing every stage. It also records process CPU separately from wall
time to distinguish computation from waiting. Production load gates disable
optional tracing; failure/audit and immutable outcome/history evidence remain.

The new original-application backup is
`services/ml/artifacts/database-recovery/20261003/sentinel-schema9-before-activation.dump`,
SHA-256 `e049fd7126e12f8d4248e84ecd6766150ec5f63baa4224d0ba8ddaaf41018493`.
It restored into NEW isolated `sentinel_application_schema9_recovery_20261003`:
nine ledger entries, 18 public tables, zero events/predictions/results. Original
application storage was not overwritten. All 33 backend integration checks pass
after the isolated cleanup list was extended for the new prediction table.

## Optimized Production-Equivalent Load

40 worker/tool checks passed (43.22s) after heartbeat debouncing and buffered
profiling. Frozen model/code/thresholds and reserved-test report are unchanged.

Buffered profile `20261003T073718970398Z`: 150/150 scored at 5 TPS for 30s,
no expiries/errors and full parity. Decision-confirmation p95 357.210ms,
maximum 720.254ms. Inference p95 wall 104.202ms/process CPU 94.222ms;
assignment/commit p95 wall 43.853ms/process CPU 10.369ms. Inference is the largest
measured compute stage; database stages include additional waiting. This short
profile is diagnostic evidence, not a ten-minute peak pass.

Normal gate `20261003T073936474956Z`: 1 TPS/60s with optional tracing OFF,
60/60 scored, no expiries/errors, full parity and no invalid/late executions.
Decision-confirmation p95 225.101ms, maximum 299.568ms.

Peak gate `20261003T074208424602Z`: 5.0 TPS over 600.083s with optional tracing
OFF, 3,000 accepted/published attempts, 2,935 scored and 65 Expired (2.1667%).
No worker errors, observation timeouts or invalid/late executions; all 2,935
scored results match offline features/probabilities/actions. Sampled queue max six.
Scored-result decision-confirmation p95 307.550ms, maximum 988.704ms; these
conditional latency values exclude expired attempts. Strict peak gate FAILED.
Activation remains blocked; no acceptance criterion, deadline, model or threshold
was relaxed. The reserved test was not repeated.

Measured image IDs:
- Worker `sha256:33de6e976e64be8e92092077c49a647671cc6282b13bfc1317e9345703a15d8a`.
- API/publisher `sha256:c8429ea0f7c05270e8d483ad02fa8cae6f4dff0ef18e9eae9726bcff45e4a801`.

Sustained normal characterization `20261003T075511348355Z`: 1 TPS for ten minutes,
600/600 scored, zero expiries/errors/timeouts, full parity and no invalid/late
executions. Decision-confirmation p95 238.663ms, maximum 348.274ms. This establishes
measured zero-expiry throughput of 1 TPS over this ten-minute generated workload
on the recorded setup, not a future guarantee or a measurement of the maximum
sustainable rate. Intermediate rates were not tested.

Post-run peak audit: 34 expired before inference (average acceptance-to-first
pending audit 1,074.860ms; maximum 1,396.509ms; average publication 268.359ms).
31 expired after one inference attempt (average assignment wait 674.281ms;
maximum 932.787ms; average publication 155.011ms). Scored attempts averaged
75.538ms assignment wait and 55.908ms publication. The first-pending timestamp is
a pre-commit queue/assignment diagnostic, not a durability witness. These figures
identify waiting before assignment/publication and remaining inference/storage
budget as the immediate bottleneck; the observations do not prove one exclusive
host/VM root cause. Feature arithmetic is not the measured limiting stage.

The runtime checker accepts the sustained normal report and REJECTS the failed
peak report, as required. No runtime credentials/run identity were generated and
no application scoring was activated. No deadline, model, threshold or zero-expiry
acceptance limit was changed. Next work stays within Task 6: remove peak waiting
and latency stalls, rerun the full 5 TPS zero-expiry gate, then activate and verify
actual-application generated actions/review and same-run restart. Task 7 is not
started; no feedback learning, drift monitoring or retraining was implemented.

## Publication and Retry Waiting Fix

The runnable-job query previously selected unpublished jobs and retries not yet
due. Its nonzero work count suppressed the Redis idle wait, repeatedly polling
SQL while the publisher/retry timer had not made progress. The query now selects
only published/dead-letter work whose retry is due, already-expired jobs, or
jobs with committed predictions requiring recovery. Newly assigned history and
snapshots remain durable; expiry does not depend on publication succeeding.
No acceptance-order cursor, mutable history cache or model change was introduced.

43 focused worker/tool checks passed in 44.05s, including new publication/retry
waiting and unpublished-expiry tests, existing commit/restart/duplicate/Redis
recovery checks, and activation/report checks. Ruff lint/format passed. Existing
408 joblib/NumPy deprecation warnings remain. The worker Docker build passed.

Current worker image:
`sha256:3a18bbbbb61c84d4c14efb29a5e0ce2eaa50569a6d01686ef5d9c1e9dc1b71c5`.
API/publisher image remains
`sha256:c8429ea0f7c05270e8d483ad02fa8cae6f4dff0ef18e9eae9726bcff45e4a801`.

Normal `20261003T091824724813Z`: 1 TPS/60s, 60/60 scored, zero expiries/errors,
full parity and zero invalid/late executions. Durable confirmation p50 182.699ms,
p95 272.100ms, maximum 587.756ms. Runtime accepts this report.

Peak `20261003T092107475626Z`: 5 TPS/600s, 2,988 scored and 12 Expired out of
3,000. No worker errors/timeouts; exact parity for all 2,988 scored results and
zero invalid/late executions. Conditional scored latency p50 155.908ms,
p95 289.494ms, maximum 908.740ms. This remains FAILED evidence, not activation.
Runtime rejects it despite otherwise passing safety/parity checks.

Post-run audit: three expired before inference (average first-assignment audit
wait 938.80ms, maximum 1,142.71ms, mean publication 255.71ms); nine expired after
one attempt (mean wait 611.33ms, maximum 862.71ms, mean publication 259.47ms).
Scored jobs averaged 73.89ms assignment wait, 54.73ms publication and 55.92ms
inference. Eleven expiries occurred in one 30-second bucket near startup and
one in a later bucket. Audit timestamps are precommit queue diagnostics, not
the durable-decision witness. Failed attempts without committed predictions
have no inference_ms record; these aggregates do not measure every failed stage.

Read-only in-run resource snapshots: WSL CPU pressure avg10 12.39%; memory
pressure some/full avg60 1.53/1.05%; I/O pressure some/full avg60 3.34/2.37%.
A separate Windows sample had 1,640 MB available. A later CPU sample showed
vmmem 154%, Code process 84% and idle 144% across four logical processors.
The aggregate 398% includes idle and must NOT be called 398% busy CPU.
These are nonsynchronized diagnostic samples, not proof of one exclusive cause.
The correlated audit query is expensive and should be run AFTER timed traffic;
the confirmation run will omit extra SQL/resource probes during production.

Actual sentinel still has nine migrations and zero events/scoring runs.
No activation credentials were generated. Manifest SHA-256 remains
`1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`;
reserved-report SHA-256 remains
`abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2`.
The reserved model test was not accessed or repeated. Task 7 remains deferred.

## Isolated Gate Pass and Actual Application Qualification

The controlled isolated confirmation `20261003T093533066526Z` offered 5 TPS
for 600.169s: 3,000 accepted, published, scored and parity-checked; zero expiries,
failures or invalid/late executions. Durable confirmation p50 155.061ms,
p95 251.577ms, maximum 675.771ms. No extra profiling/resource queries ran during
its timed workload. Together with normal `20261003T091824724813Z`, it passed
the image-pinned runtime preparation checker. These are tmpfs fixture results,
NOT evidence of actual persistent-database peak performance.

Private ignored runtime configuration was then created for application run
`e7d43b39-fd79-4368-818d-899c2415434a`. API, publisher and worker address the
original sentinel database/Redis services. Credentials are not in this record.
The same run identity and credentials must be preserved through any new build.
The model and its authorized final-test report were clean-loaded/rechecked,
not re-evaluated on the reserved dataset.

Actual action smoke [report](../services/ml/reports/task6-application/20261003T095305015875Z/report.json):
real RF Pass/Review/Block probabilities match offline values within 1e-12;
simulated outcomes are allowed/pending_review/rejected. Authorized review allow
returns 201, identical retry 200, conflicting resolution 409 and unauthorized
access 401. The original Review decision remains immutable and no fraud label
is created. Duplicate ingestion returns the existing 200/duplicate receipt, not
a second action. A same-run worker restart and verify-report recheck passed.

Two earlier failed smoke records remain: `20261003T094840184452Z` is a genuine
cold-start expiry with no prediction/execution; `20261003T095107462276Z` is a
measurement-tool error that expected 202/accepted for a duplicate, whereas the
existing API correctly returns 200/duplicate. The latter checker was corrected
and covered by four additional regression tests; the API contract was unchanged.

## Actual Persistent-Database Load Evidence

Reports below are under `services/ml/reports/task6-application-load/`. Traffic
contains generated safe events, no dataset labels/card numbers, and fresh card
namespaces per workload. Tests append to original application storage; they do
not truncate history. Durable counts, publication, actions and parity queries
are scoped to each workload's event IDs.

| Report | Requested Workload | Durable Outcome | Status |
| --- | --- | --- | --- |
| normal-20261003 | Windows client, 1 TPS/60s | 60 scored, zero expiry/failure | PASS |
| peak-20261003 | Windows client, 5 TPS/600s | 693 accepted; 14 scored, 679 Expired | FAIL; producer stopped early |
| 20261003T102639520096Z | Docker client, 1 TPS/60s | 60 scored, zero expiry/failure | PASS |
| 20261003T102935674319Z | Docker client, 5 TPS/600s | 41 accepted, all Expired | FAIL; producer stopped early |
| 20261003T111514414326Z | Diagnostic Docker client, 5 TPS/30s | Four accepted, all Expired | FAIL; short diagnostic only |

Windows normal durable latency p50 433.481ms/p95 744.835ms/max 878.261ms.
Docker normal p50 368.034ms/p95 521.934ms/max 926.701ms. Both have exact
60-row offline/live parity and zero invalid/late executions; sampled pending
queue maximum one. This demonstrates observed 1 TPS for 60s on the actual
application, not the maximum sustainable rate or a long-term guarantee.

Windows peak production stopped after 143.602s; its 600.035s observation window
includes idle time. Mean offered traffic was only 1.155 TPS, so it is not valid
sustained peak evidence. Client outcomes: 14 scored, 657 expired, 22 observation
timeouts; durable storage resolves all 693. All were published. Exact parity
holds for the 14 scored rows, with no late/invalid execution. Conditional scored
p95 was 991.267ms, excluding expiries. Sampled pending queue reached 12 and
oldest waiting age 2.561s. No worker-error claim masks the deadline misses.

Docker peak stopped after 41 requests (13.957s production); its 600.042s
observation window has only 0.0683 TPS mean offered traffic. Client observed
25 expired and 16 timeouts; durable storage resolves 41 Expired. All were
published, zero were executed, and there are no scored rows on which to claim
probability parity. This is not a passing peak or proof of a networking fix.

## Stage Profile and Resource Preservation

The final short diagnostic followed preservation and shutdown of unused isolated
fixture services to release memory. It still stopped after four requests.
Sixteen safe stage records were retained; all attempts expired before inference.

| Stage | p50 Wall ms | p95 Wall ms | Maximum Wall ms | p50 Process CPU ms |
| --- | ---: | ---: | ---: | ---: |
| Queue before assignment | 1711.645 | 3368.079 | 3558.363 | n/a |
| History read | 1.867 | 62.909 | 73.680 | 0.909 |
| Feature calculation | 0.112 | 0.230 | 0.247 | 0.113 |
| Assignment including commit acknowledgement | 258.570 | 916.268 | 1012.358 | 4.276 |
| Preparation including commit acknowledgement | 350.623 | 719.285 | 763.621 | 3.544 |

No inference ran in this sample; RF computation is not the measured cause of
these four expiries. Admission-to-event-insert gaps were 116, 1730, 1084 and
134ms; publication lag reached 2286ms. All 863 application outbox rows were
published on attempt one. The immediate bottleneck is upstream queue/database
acknowledgement waiting before inference. These samples do not prove a unique
Windows/VM/storage cause. Fsync and synchronous_commit remained ON. A separate
idle server-local synchronous health-row update probe measured 23.849-52.967ms
for 12 commits; that is not a full-traffic throughput measurement.

Isolated fixture preservation archives (ignored/private):
- PostgreSQL dump SHA-256 `d34770cca74906a7fca62364892b334ed12fa5566bc0078a7f2513b734669c62`.
- Redis RDB SHA-256 `21e31738e29dd28d34c4eb7d66c726eab4b8bd7417c60581d8641e168c38b137`.
The fixture PostgreSQL archive was restored to the reinitialized EMPTY isolated
test database before backend integration tests. Original application volumes
were never reset, copied over or removed. No security software, user applications,
host RAM limit or power plan was changed during this checkpoint.

## Populated Application Recovery Checkpoint

With qualification scoring stopped, pg_dump captured the populated application
in ignored `artifacts/database-recovery/20261003/sentinel-populated-task6-checkpoint.dump`.
SHA-256 `8c28b15099864e5e4b83934c9e1e0b1ec983b34955dbb9b01656dd520748d40a`.
It restored with pg_restore --exit-on-error into NEW isolated database
`sentinel_application_populated_recovery_20261003`, never over sentinel.
Verified matching counts: nine migrations, 863 events/jobs/history/snapshots,
156 private predictions, 138 results/executions, one review; 138 Scored and
725 Expired. Private late predictions are audit evidence, not public scores.
Recovery for a failed deployment is to stop scoring, retain original storage,
restore the dump into a NEW isolated target, compare ledger/immutable records,
then explicitly review any target switch. Do not downgrade populated schemas
or overwrite the application as a test/recovery shortcut.

## Atomic Schema-v2 Ingestion Optimization

The accepted v2 path now needs four database calls instead of seven:
BEGIN, idempotency claim, one dependency-linked data-modifying CTE, COMMIT.
The CTE persists event/outbox/audit/receipt in the SAME transaction; any failed
write or missing claimed receipt rolls everything back. Receipt semantics,
quarantine, old schema events, durable commits and the model/deadline are unchanged.
PostgreSQL describes RETURNING-based dependencies for these statements in its
[official WITH documentation](https://www.postgresql.org/docs/16/queries-with.html).

Verification: 38 backend integration tests passed (183.226s), including four
outbox/audit/receipt/missing-claim failure cases, successful linked persistence,
concurrent idempotency, migration preservation and review/action guards.
All 154 backend unit tests passed (164.886s), ESLint and git diff --check passed.
This is correctness evidence, not yet measured performance of the new build.
Existing deployed images/runtime pins are not replaced without qualification.

## Latest Qualified Build and Application Peak Failure

The optimized API/publisher image is
`sha256:5a2bb17f7affd31a01be1818161b424357049962589e8178323f2f0a72ebeea7`;
worker remains
`sha256:3a18bbbbb61c84d4c14efb29a5e0ce2eaa50569a6d01686ef5d9c1e9dc1b71c5`.
The normal BuildKit build encountered a Docker proxy/DNS error. A legacy-builder
retry using the unchanged repository Dockerfile succeeded; no dependency or
global Docker configuration was changed. A separate offline diagnostic image
was also built but was not deployed. The build reported two dependency-audit
findings (one moderate, one high); they were not fixed or declared resolved.

Isolated opt-in profile `20261003T121732287095Z`: 5 TPS/60s, 281 Scored/19
Expired, full scored parity and no invalid/late execution. Queue p95 727.521ms,
max 1012.177ms; feature p95 0.370ms; assignment/commit p95 47.696ms;
preparation/commit p95 32.480ms; inference p95 162.241ms; prediction/commit
p95 19.372ms; execution/commit p95 23.628ms. This failed diagnostic is retained.

With optional tracing OFF, isolated peak `20261003T122320334099Z` passed:
3,000/3,000 accepted/published/scored at 5 TPS/600s, full parity, no expiry,
failure or invalid/late execution. Latency p50 163.787ms/p95 295.634ms/max
707.960ms; sampled queue maximum three. Isolated normal
`20261003T124044957240Z` passed 60/60 at 1 TPS/60s, zero expiry/failure,
full parity; p50 171.765ms/p95 312.164ms/max 473.753ms.

Both passing isolated reports were checked against the frozen package, passing
authorized model-test report and current image IDs. Existing runtime metadata
was refreshed atomically; its previous bytes were archived in ignored runtime
storage. Credentials and run ID stayed unchanged. Nine runtime tests passed,
including identity preservation, interrupted replacement and unexpected edits.
The new API/publisher were installed for temporary application qualification;
the original image remains tagged `sentinel-ai-api:task6-pre-cte`. The nine-entry
application ledger, original data and synchronous durability settings survived.

The populated backup's eight canonical table-content fingerprints matched
between actual and restored databases (events, snapshots, history, jobs,
predictions, results, executions and reviews), in addition to the dump SHA-256.
Unused isolated services were stopped before actual load measurements; original
application volumes were untouched.

Actual normal `20261003T124804883791Z` initially scored 59/60, one Expired,
full scored parity and no late execution. The expired attempt waited 792.805ms
for assignment; publication took 499.537ms. It expired at 1070.714ms before
inference, with no prediction or execution. This failed report remains intact.

The measurement client previously deserialized a second full RF before traffic,
although that model was only needed for offline parity afterward. It now checks
package integrity before traffic and defers reference-model loading/reference
checks until the timed workload and terminal observations end. No serving
model, features, policy or deadline changed. The controller-only source hashes
and this phase ordering are recorded in reports. Forty focused tool tests passed
in 7.30s, including the phase-order regression, runtime, benchmark and smoke guards.

Actual normal `20261003T125806294035Z` then passed: 60/60 scored at 1 TPS/60s,
zero expiry/failure, full parity, zero invalid/late execution; durable latency
p50 365.308ms/p95 541.302ms/max 634.560ms.

Actual full peak `20261003T130023513748Z` FAILED: 3,000 accepted at 5 TPS/600s,
67 Scored and 2,933 Expired. The 2,133 zero-attempt expiries and 800 one-attempt
expiries identify waiting/preparation and remaining inference/storage budget as
the performance blocker. Expired transactions receive no action. Conditional
scored latency p50 967.560ms/p95 996.343ms/max 996.867ms excludes expiries and
is not evidence that the whole workload met its deadline.

General activation remains BLOCKED. The qualification worker was stopped and
readiness marked false with workload_gate_failed. The measured zero-expiry
application rate remains 1 TPS for a controlled 60s sample; maximum sustainable
throughput has not been measured. Further worker/database-path performance work
is required, not another owner approval or another reserved-model evaluation.
Assignment/preparation fusion was considered but NOT implemented before the
owner redirected this checkpoint to committing/pushing ritwik. Task 6 is NOT
complete and Task 7 has not started. Keep historical failure evidence and all
accumulated application records; do not relax the one-second/zero-expiry gates.

## 2026-10-04 Durable Batch Qualification

Task 5 remains COMPLETE; Task 6 remains INCOMPLETE, with general activation
BLOCKED. Docker initially had no engine pipe; work resumed after the owner
started the existing engine. Original application volumes and all nine migration
entries were verified. No application reset, new model fit, reserved-test access,
deadline/threshold change, or system-resource setting change occurred.

### Implementation

New published jobs persist history, immutable feature snapshots and first-attempt
preparation in one transaction. Groups of at most four already-waiting events
share the assignment checkpoint; there is no batch-fill delay. Private predictions
share one synchronous COMMIT. Only AFTER its acknowledgement does a separate
transaction create public results and once-only simulated executions. A failed
prediction batch rolls back and rechecks individual deadlines; a deferred
execution deadline failure rolls back every effect before individual recovery.
Retries use existing checkpoints and never add duplicate history. The frozen
feature, preprocessing, model, calibration and policy files were not edited.

Candidate history is retained: fusion-only worker
`sha256:3d10de55b8a39f2e14dcc9d8f8767fba902b7a5e362198b63a0324793c93fcb7`
passed isolated rates but actual normal scored 59/60 and the short profile scored
20/150. Both failures remain in private reports. The batched worker now pinned
by runtime metadata is
`sha256:39dfd04e02bfa75b8e4ec2ea138ad6752dd2dd2928d8eec24eb0f06915602683`.
API/publisher remain
`sha256:5a2bb17f7affd31a01be1818161b424357049962589e8178323f2f0a72ebeea7`.
Previous worker is retained as `sentinel-ai-scoring-worker:task6-before-fusion`.
Runtime requalification archived previous metadata and retained credentials and
run ID `e7d43b39-fd79-4368-818d-899c2415434a`.

### Load Evidence

Report paths below are relative to `services/ml/reports/`; generated reports are
private local artifacts, not Git content. Every row has full scored-row parity,
zero invalid/late execution, no operational errors and no reserved-test access.

| Target / Report | Rate / Seconds | Scored / Expired | Durable p95 / Max ms | Gate |
| --- | --- | --- | --- | --- |
| Isolated `task6-worker/20261004T151547461481Z` | 1 / 60 | 60 / 0 | 258.817 / 317.139 | PASS |
| Isolated `task6-worker/20261004T151818362911Z` | 5 / 600 | 3000 / 0 | 257.949 / 748.729 | PASS |
| Actual `task6-application-load/20261004T153215710833Z` | 1 / 60 | 60 / 0 | 583.246 / 856.493 | PASS |
| Actual `task6-application-load/20261004T153400606949Z` | 5 / 600 | 2409 / 591 | 957.365 / 999.511 | FAIL |
| Actual diagnostic `task6-application-load/20261004T154851323542Z` | 3 / 60 | 179 / 1 | 708.325 / 991.490 | FAIL |
| Actual diagnostic `task6-application-load/20261004T155052666948Z` | 2 / 60 | 120 / 0 | 778.165 / 844.083 | PASS, diagnostic only |

Peak offered exactly 5 TPS for 600s; queue sampled maximum seven, producer maximum
schedule lag 407.667ms. Expiry rate was 19.7%, not zero. Conditional scored
latencies exclude 591 expiries and must not be called whole-workload compliance.
The highest observed zero-expiry rate is 2 TPS for a 60s sample; maximum or
long-duration sustainable throughput is NOT established. CLI rates 2-4 are now
available for diagnostics, but activation checks still require exactly 1 and 5.

The opt-in batched profile `task6-application-load/20261004T154611367858Z`
scored 115/150 with 35 Expired at 5 TPS/30s. Queue p95/max 982.918/1398.154ms;
history p95 3.873ms; feature calculation p95 0.404ms; inference p95 141.401ms.
Batch assignment/commit p95 193.559ms (CPU p95 40.272ms), prediction/commit
p95 124.103ms (CPU p95 12.639ms), execution/commit p95 119.909ms (CPU p95
25.036ms). Nested per-event timings exclude the outer batch commit; use the
batch stages for acknowledgement timing. These are diagnostics, not gate passes.
Full peak audit averages: scored publication/assignment waits 161/408ms;
expired publication/assignment waits 267/810ms. Queue/database waits consume
most remaining deadline budget; feature arithmetic is not the dominant cost.
No revised deadline or traffic requirement has been proposed or applied.

### Actions, Recovery and Hold

Actual [action report](../services/ml/reports/task6-application/20261004T155259827723Z/report.json)
passed Pass/Block/Review execution, authenticated review resolution, idempotent
duplicate handling and conflict/unauthorized rejection. It was rechecked after
a same-run worker restart with all recorded final results unchanged. An earlier
action smoke failure remains retained; it was not rewritten as a pass. Human
resolution remains separate from model decisions and creates no confirmed label.

Fresh pre-change backup SHA-256:
`737cffa9861947a48a09ad63c4c17d6f673236b6c9f0084c3b3d8f062a33f184`.
Local file `services/ml/artifacts/database-recovery/20261003/sentinel-before-worker-fusion-20261004.dump`
restored successfully into NEW isolated `sentinel_application_recovery_20261004`:
nine migrations, 3983 events/jobs/history/snapshots, 324 Scored/executions and
3659 Expired. The backup and prior checkpoints remain retained. Never restore
over the application as a test shortcut; recovery requires a new isolated target,
content verification and explicit review before any target switch.

After all current measurements, actual application has 7707 events/jobs/history/
snapshots, 3289 Scored and 4418 Expired, including historical failure evidence.
Scoring worker is STOPPED; health is not ready, error `workload_gate_failed`.
Original data and volumes remain intact. Task 7 has not started. Further
database-path/queue performance engineering and a zero-expiry actual ten-minute
peak pass remain required; existing owner approvals need not be requested again.

Final verification: 72 worker/runtime/benchmark/action-tool checks passed in
45.80s, with explicit isolated Redis restart enabled and no skips. Coverage
includes checkpoint rollback/visibility, batch prediction commit visibility,
delayed batch COMMIT expiry, timely-peer preservation, process death/uncertain
commit recovery, duplicate effects/history, history restoration, Redis loss and
restart, and rejection of diagnostic-rate activation evidence. Ruff check of
all ML source/tests and git diff --check passed. There were 408 pre-existing
NumPy/joblib deprecation warnings plus one pytest cache permission warning;
neither was hidden or counted as a test failure. Backend code was not changed
this turn; its previously recorded integration/unit passes were not rerun.
Frozen manifest and authorized final-test report SHA-256 still match exactly
`1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696` and
`abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2`.
Changes remain local on `ritwik`; no new commit/push/merge was authorized or done.

## Candidate Index and Bulk Finalization Checkpoint

Task 5 remains COMPLETE. Task 6 remains INCOMPLETE and activation BLOCKED.
The current publisher protocol still uses a committed claim followed by a
separately committed publication outcome. A proposed change to one bounded
row-lock transaction spanning Redis publication and durable outcome storage
requires owner approval; it has NOT been implemented. The asynchronous approval
question remains unanswered. Existing policy/evaluation/deadline/database gates
remain approved and must not be requested again.

### Changes and Verification

The former idle candidate query touched 4869 shared buffers and took 14.516ms
in one EXPLAIN ANALYZE sample, scanning all 7707 historical events every poll.
Migration `0010_scoring-candidate-index` adds a partial `(created_at,event_id)`
index for schema 2.0. A materialized candidate-ID query now limits payload reads
to unassigned events, preserving acceptance order and finding late commits;
it does NOT advance a cursor that could silently skip an earlier commit.
The first cold new-plan sample touched 608 shared buffers plus 39 reads, used
an index-only candidate scan, and took 15.296ms. This is buffer/plan improvement,
not proof of lower elapsed time. Do not claim it solved the load bottleneck.

Batch finalization uses one dependency-linked data-modifying statement. It locks
jobs, separately marks expired jobs, inserts results from previously COMMITTED
private predictions and completes only jobs whose result insertion succeeded.
Existing postcommit, immutable, once-only execution and deferred deadline guards
remain active. An expired peer does not cause a timely peer to lose its decision;
an abort rolls effects back before individual recovery. No prediction and
execution commits were merged, and no durability setting was weakened.

Seventy-three ML worker/runtime/benchmark/tool checks passed in 49.70s with
explicit isolated Redis restart, no skips and 408 existing NumPy/joblib warnings.
The same-transaction prediction rejection now tests both individual and bulk
finalization. Five schema/migration integration checks passed in 31.854s,
including populated-data preservation and isolated index rollback. Ruff check
of all ML source/tests and ESLint on the changed backend test passed.

API, publisher and worker targets were independently checked as
`postgres:5432/sentinel`. After a fresh backup, the repository migration runner
applied only migration 0010 to the application; its ledger has ten entries and
all 7707 preexisting events remained intact. No database/volume reset or
application schema downgrade occurred. The deployable backend image includes
the migration, not just a successful isolated test or ephemeral SQL copy.

### Exact Workloads

Current worker: `sha256:f5fcba36304c0400509b0694342a6296ef7df51e644d39e09e6493fee0afa5bc`.
Current API/publisher: `sha256:b6d0d7e396c067a434312905cbb7278c26974bcd8ecd7793257da8f59f5f9c6e`.
Previous images are tagged `sentinel-ai-scoring-worker:task6-before-candidates`
and `sentinel-ai-api:task6-before-index10`. Runtime pins were refreshed only
after passing isolated qualification, with previous metadata archived and
credentials/run identity unchanged.

All paths below are relative to `services/ml/reports/`. Every workload retained
full scored-row offline/live parity, no invalid/late execution, no operational
errors and no reserved-test access. No model, feature, calibration or threshold
changes were made.

| Target / Report | Rate / Seconds | Scored / Expired | Durable p95 / Max ms | Gate |
| --- | --- | --- | --- | --- |
| Isolated `task6-worker/20261004T162758734524Z` | 1 / 60 | 60 / 0 | 289.887 / 442.451 | PASS |
| Isolated `task6-worker/20261004T163033573408Z` | 5 / 600 | 3000 / 0 | 270.288 / 626.956 | PASS |
| Actual `task6-application-load/20261004T164608670040Z` | 1 / 60 | 60 / 0 | 570.536 / 921.955 | PASS |
| Actual `task6-application-load/20261004T164751054593Z` | 5 / 600 | 2418 / 582 | 962.101 / 999.877 | FAIL |

Actual peak offered 5 TPS for the entire 600s: expiry rate 19.4%, sampled queue
maximum seven, producer maximum schedule lag 675.467ms. Conditional scored
latencies exclude expiries and cannot establish whole-workload compliance.
Query/finalization changes did not materially resolve peak throughput versus
the prior 2409/591 result. The highest earlier observed zero-expiry diagnostic
rate remains 2 TPS for 60s, not a proven maximum or revised requirement.

### Storage Evidence and Recovery

The installed native `pg_test_fsync` utility tested a verified nonexistent,
uniquely named synthetic file in the original PostgreSQL volume, OUTSIDE load
measurements. It removed its own probe file; its absence was verified. With one
8KiB write, default `fdatasync` measured 28.464 ops/s (35.132ms/op); with two
8KiB writes, 28.635 ops/s (34.922ms/op). Other sync methods also showed latency;
this was a short diagnostic, not a tuning recommendation or application capacity
guarantee. `wal_sync_method=fdatasync`, `fsync=on` and `synchronous_commit=on`
were verified and remain unchanged, as do host/Docker resource settings.

Pre-index backup SHA-256:
`ad950c1e686ccc96af7d6c1348b3e7a516063e3d1b9e3cc40ea185f317ba1110`.
It restored into NEW isolated `sentinel_preindex_recovery_20261004`: nine
migrations and 7707 events/jobs/history/snapshots, with 3289 Scored/4418 Expired.

After measurements and action/restart checks, the application has 10770
events/jobs/history/snapshots, 5770 Scored/results/executions, 5000 Expired,
6324 private predictions and three human review resolutions. Historical failed
runs remain intact. Current populated schema-10 backup:
`services/ml/artifacts/database-recovery/20261003/sentinel-schema10-task6-checkpoint-20261004.dump`.
SHA-256: `50adbb07ca5b8efcb8519c0018561d90dc58448bcadfc501eb17112fad1d93ce`.
It restored successfully into NEW isolated `sentinel_schema10_recovery_20261004`.
All eight canonical table-content MD5 fingerprints/counts matched actual versus
restored events, snapshots, history, jobs, predictions, results, executions and
reviews. MD5 here is a content-comparison check; the dump integrity pin is SHA-256.

Actual action report `task6-application/20261004T165900589090Z/report.json` passed
Pass/Block/Review, authorized human resolution, duplicates/conflicts/unauthorized
requests, and was reverified unchanged after a same-run worker restart. Review
resolution creates no fraud label. Scoring is STOPPED and health marked not ready
with `workload_gate_failed`. General activation remains blocked. Do not reset
storage, overwrite the application with a restore, repeat the reserved evaluation
or start Task 7. The dependent publisher change is paused pending explicit owner
approval, followed by recovery tests and new exact-image workload qualification.

## Publisher Commit Reduction

Owner approved baseline measurement, a recovery-safe commit reduction, changed
failure-boundary tests and progressive benchmarks on 2026-10-04. No activation,
deadline extension, relaxed durability or reserved-model reevaluation was
authorized. Task 5 stays COMPLETE; Task 6 stays INCOMPLETE.

### Environment and Baseline

Host: Intel i5-6200U, two physical/four logical cores, about 8 GiB Windows RAM.
Docker reports four CPUs and 1,998,868,480 memory bytes (1.862 GiB). Original
database volume is `sentinel-ai-postgres-data`, mounted at
`/var/lib/postgresql/data`, backed by Docker's
`C:/Users/lenovo/AppData/Local/Docker/wsl/disk/docker_data.vhdx` on the C-drive
SATA HDD (ST1000DM003-1ER162, 1 TB). No storage/resource/security settings changed.
`fsync=on`, `synchronous_commit=on`, `wal_sync_method=fdatasync` were verified.

Initial host free memory was 978,004 KiB; before the clean baseline, 1,097,824 KiB.
A three-second competing-CPU sample measured Docker Desktop 0.609 CPU seconds,
Docker backend 0.547, VS Code 0.109 and the inspection PowerShell 0.922. VS Code,
Defender and Docker remained running; no applications were closed or excluded.
Builds and test suites completed before measured traffic; isolated test services
were stopped for application measurements. A few read-only progress queries ran
during isolated qualification; no schema/code/configuration changed mid-workload.

The first instrumented baseline, application report
`20261004T173236488879Z`, failed with a producer pause: only 22 durable acceptances
(5 Scored/17 Expired), despite 150 configured attempts. Offered traffic was only
0.733 TPS. It is retained, NOT a valid sustained 5 TPS comparison.

Clean baseline `20261004T174303369268Z` offered 5 TPS for 30s: 112 Scored/38 Expired.
Per-event queue wait and worker stages are in `worker-profile.log`; Redis and
publication stages are in `publisher-profile.log`. Logs contain safe UUID/timing
records, not payloads, card tokens, labels or probabilities. Non-blocking logging
may drop records; durable database outcomes remain authoritative.

### Protocol and Measured Improvement

See [publisher protocol](publisher-recovery-protocol.md). The active entrypoint
no longer durably commits a claim before sending. It fences concurrent publishers
with a transaction-scoped advisory lock, locks at most four already-waiting rows
in canonical acceptance order, publishes sequentially with bounded Redis calls,
records outcomes on the SAME PostgreSQL client and commits once. It never waits
to fill a batch. A blocked retry/legacy claim prevents later rows overtaking it.

Failed batches roll back wholly. Separate compare-and-set failure storage preserves
retry/dead-letter evidence without regressing published rows. Redis acceptance
and PostgreSQL commit are NOT atomic: accepted prefixes or lost commit replies
can cause canonical-ID redelivery. Existing worker uniqueness/checkpoints preserve
once-only history, features, predictions, results and separate execution.

| Actual application timing, ms p95 | Clean baseline | Candidate |
| --- | ---: | ---: |
| Claim transaction including commit / new lock preparation | 133.964 | 16.497 |
| Claim COMMIT acknowledgement | 122.519 | Removed |
| Redis publication | 15.326 | 15.831 |
| Per-event committed outcome / new uncommitted outcome statement | 132.034 | 7.253 |
| New batch COMMIT acknowledgement | Not applicable | 111.428 |
| Acceptance-to-worker-assignment queue | 991.451 | 660.256 |
| Feature calculation | 0.451 | 0.347 |
| Inference | 173.702 | 119.780 |
| Worker assignment checkpoint, including batch commit | 175.968 | 142.201 |
| Worker prediction batch commit | 148.980 | 128.733 |
| Worker execution batch commit | 110.593 | 116.609 |

Rows comparing committed versus uncommitted statements are deliberately labelled;
do not sum overlapping timing scopes or treat p95s as additive per-event times.
Baseline used 143 nonempty claim commits plus 150 outcome commits; candidate used
150 nonempty batch commits (48.8% fewer publisher durable commits).

Baseline PostgreSQL active-state samples included 429 WALSync, 273 WALWrite-lock
and six WALWrite observations, versus 270 CPU/Running. Together WAL sync/write
states were 708/1002 samples (70.7%). Publisher commit CPU p95 was under 2.3ms.
This confirms substantial durable-write waiting in the persistent database;
sampling counts are not exact stage wall-time percentages or a sole-cause proof.
Feature calculation is not a dominant measured cost.

Candidate application diagnostic `20261004T174543566781Z` offered the same 5 TPS
for 30s: 147 Scored/3 Expired, full scored parity, zero late execution or operational
errors. Queue maximum fell five to three. Conditional scored latency p95 fell
947.904 to 886.254ms; expiries are excluded, so neither run passes activation.

### Verification and Workload Gate

Candidate API/publisher image:
`sha256:92aac19cd94749b2cdbc17561424f37e4bc6c19c3f4503fbbaae9c43903de013`.
Frozen worker unchanged:
`sha256:f5fcba36304c0400509b0694342a6296ef7df51e644d39e09e6493fee0afa5bc`.
The instrumented old-protocol baseline and previous qualified backend are retained
under `task6-publisher-baseline` and `task6-before-publisher` image tags.

12 publisher integration checks passed: concurrent publishers/order, bounded
batch size, failed-prefix rollback/ordered recovery, Redis accepted/reply lost,
uncertain successful COMMIT, real Redis pause/timeout/socket closure/reconnect,
abandoned legacy claim and actual publisher process death before COMMIT. All 46
backend integration and 154 unit checks passed on the production changes.
76 focused ML/runtime/tool checks passed (50.49s), including actual Redis restart,
uncertain commits, history restoration, late-result prevention and a direct
active-publisher-death/independent-ready-publisher-to-worker recovery test.
That test proves canonical same-card replay feature parity and exactly one
history/snapshot/prediction/result/execution per event across all three actions.
Process setup finishes before event acceptance; the one-second deadline remains
unchanged. Its first cold-setup attempt failed and was not counted as a pass.
408 existing NumPy/joblib deprecation warnings remain. No checks were skipped.

| Isolated report under `services/ml/reports/task6-worker/` | Workload | Scored / Expired | Durable p95 / Max ms | Result |
| --- | --- | --- | --- | --- |
| `20261004T174801323927Z` | 1 TPS / 60s | 60 / 0 | 303.482 / 360.265 | PASS |
| `20261004T175032012752Z` | 5 TPS / 600s | 2940 / 60 | 602.229 / 998.784 | FAIL |
| `20261004T180330925508Z` | Profile, 5 TPS / 30s | 150 / 0 | 281.133 / 511.000 | Diagnostic only |

Full isolated peak offered exactly 5 TPS, with queue maximum five, no operational
failures, 2940 exact parity checks and zero late executions. Observed timely
output was 4.9 TPS, but 2% expiry is NOT sustainable deadline-compliant acceptance
at 5 TPS. Scored mean publication/terminal times were 44/202ms; expired means
114/1097ms. The publication timestamp precedes its COMMIT acknowledgement; these
means do not exclude a publisher commit/scheduling tail. Full-run profiling was
off, so the precise location of those tail delays is not established by this
comparison alone.

One VM pressure sample during peak showed CPU some avg60 15.10%, I/O full avg60
0.36%, memory full avg60 0.03%; Windows free memory was 1,567,824 KiB. The subsequent
short tmpfs profile had queue p95 145.124ms, inference p95 139.147ms and assignment
checkpoint p95 28.424ms. It did NOT reproduce the full-run failures. Their exact
tail-delay root cause remains unresolved; do not attribute all of them to HDD
flushes or claim a successful short run proves sustained reliability.

Qualification failed. Candidate runtime pins were NOT promoted, and the dependent
full actual-application peak gate was NOT bypassed. Short unqualified-image
application diagnostics are explicitly marked `diagnostic_only`; runtime loading
rejects that evidence even if its traffic/outcomes otherwise pass. No arbitrary
follow-up performance edits, model changes or revised limits were applied.

### Actual Normal-Rate Feasibility and Hold

Candidate application report `20261004T181449763174Z` offered exactly 1 TPS for
60 seconds on original persistent storage: 58 Scored/2 Expired, 58 exact parity
checks, zero late executions, no operational errors and queue maximum one.
Conditional scored durable p95/max were 646.724/968.029ms. This is explicitly
unqualified-image diagnostic evidence, not an activation pass. Active database
samples included 311 WALSync, 39 WALWrite-lock, one WALWrite, 72 DataFileRead and
348 CPU/Running observations. These show continued write/read waiting but do not
isolate the precise cause of the two expiry tails.

No zero-expiry sustainable actual-storage rate has been established for this
candidate: even controlled 1 TPS failed. The observed 4.9 timely TPS during full
isolated peak is output WITH expiry losses, not acceptable admission capacity.
Earlier 2 TPS/60s zero-expiry evidence belongs to a previous build and remains
short-window evidence, not a proven maximum or new limit. Running a higher-rate
feasibility test after the current normal-rate miss would not establish reliable
capacity. No further small optimizations or blind full-run repetitions were made.

Candidate full actual peak was not run: isolated exact-image qualification and
actual normal feasibility both failed. Runtime pins remain at the previous
qualified backend, and the general scoring hold remains mandatory. Further
engineering needs a trace of the sustained/normal tail failures rather than
assuming that publisher commits, features or model weights are the sole cause.
The tested commit reduction remains local and in its separately retained image;
it was not promoted as a qualified deployment. Task 7 has not started.

### Final Recovery and Deployment State

Fresh populated schema-10 recovery dump:
`services/ml/artifacts/database-recovery/20261003/sentinel-after-publisher-engineering-20261004.dump`.
SHA-256: `8d6f593f6e6422fb811b10b6d98bba171ea6f58d490d4eed980b55c29977c537`.
The same hash was verified after copying into the isolated container. It restored
into verified-new `sentinel_publisher_recovery_20261004`, with ten ledger entries.
Nine canonical row-count/content-MD5 comparisons matched actual versus restored:

| Table | Rows | Content fingerprint |
| --- | ---: | --- |
| authorization_event_outbox | 11152 | 170aacb9dbbb04e53aac053e2452eb0a |
| authorization_events | 11152 | 707d2d8904c202e1a163eb14bdb1783a |
| review_resolutions | 3 | e0014fe65465794c53b6417a36ef3113 |
| scoring_feature_snapshots | 11152 | 65f42f718ac467543c16d7941800863c |
| scoring_history | 11152 | 9c821e76c94be7ca832cdef4de3dc02e |
| scoring_jobs | 11152 | 1b63b2557812f365c757126a3167662a |
| scoring_predictions | 6661 | 33a5324942b70f9b247775ff0b5597df |
| scoring_results | 6092 | 6cac231cfe355473015ffe979a33ee1e |
| simulated_executions | 6092 | 4e3b587e2707f0bc6a8954de496f01bd |

MD5 here compares canonical row content; the dump integrity pin is SHA-256.
Original application has 6092 Scored and 5060 Expired, including retained prior
failures. All old backups and original volumes remain intact. Recovery remains:
stop scoring, preserve original storage, restore into a NEW isolated target,
verify ledger/content, and obtain explicit review before any target switch.
Never restore over the application or downgrade/reset populated storage.

Previous qualified backend image
`sha256:b6d0d7e396c067a434312905cbb7278c26974bcd8ecd7793257da8f59f5f9c6e`
is restored for API/publisher, matching existing private runtime pins. Candidate
and baseline images are retained separately. Worker is STOPPED, health is false
with `workload_gate_failed`; no activation occurred. Isolated services are stopped
after verification (their tmpfs restore is disposable; the verified dump remains).
Final backend integration rerun passed all 46 checks in 25.798s. Frozen manifest
and reserved-report integrity remain unchanged; no new commit/push/merge or Task 7
work was performed.
