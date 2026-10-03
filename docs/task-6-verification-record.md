# Task 6 Verification Record

## Current Status

Task 5 passed for the immutable sigmoid RF package; its reserved test was
evaluated once with owner authorization. Task 6 remains incomplete. Application
storage is migrated and connected functionality is tested, but sustained peak
deadline compliance on the actual persistent application database has failed.
Application qualification ran with a stable identity; general scoring activation
is blocked and the qualification worker is stopped between measurements.

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
