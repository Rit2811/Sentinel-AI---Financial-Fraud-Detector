# Repository Instructions

LOCAL BRANCH RECONCILIATION (2026-10-06): owner explicitly approved LOCAL
checkpoint/merge/testing only, NOT pushing or main changes. PC checkpoint8619787
is retained at recovery/pc-checkpoint-20261006; laptop commit410472e is reconciled
on ritwik. Four Compose conflicts retain the already-tested canonical names.
Isolated sentinel-test keeps Compose-generated names and legacy DNS aliases;
no fixed container names that break worker_benchmark/restart tests. Laptop docs
are preserved with historical-status headers. Their Task7 feature-verification
scope is recorded, NOT started; current deployment status remains authoritative.
Tests:180backendunit,49integration,126focusedPython PASS; lint/format/Compose
PASS; real container DNS probe and opted-in isolated Redis restart PASS.
Initial Python run125pass/1fail exposed a stale clock stub; test-only repair,
then full126pass. Production clock/deadline/model untouched;816existing NumPy
deprecation warnings. All43private runtime/frozen/gate-file hashes unchanged.
Secrets/cache/artifacts excluded from Git. Test fixtures stopped after checks;
application writers remain stopped, Task5 COMPLETE,Task6 INCOMPLETE/hold remains.
Read docs/branch-reconciliation.md. Do NOT push or merge main without separate
approval. Git does not transfer images, secrets, model artifacts or Redis data.

LAPTOP HANDOFF PREPARATION (2026-10-06): owner reports Windows Ryzen laptop,
16GB RAM,512GB SSD,Docker installed; exact CPU/Docker storage/limits unverified.
This workspace is STILL on i5-6200U/about8GB/HDD. No transfer or destination test
has occurred. Read docs/laptop-handoff.md. Private ignored transfer inventory
services/ml/artifacts/laptop-handoff/transfer-manifest.json has43 requiredfiles
(about28.34MB) and hashes, including frozen/gate/runtime/config/CA evidence.
Current dirty code and Redis AOF/group state need separate safe transfer; a remote
clone alone is insufficient. No credentials printed or new archives exported.
Keep source writers STOPPED; don't run both deployments. Same Mumbai target,
model,thresholds,1000msdeadline,held activation. Verify laptop clocks/TLS/paths/
images/Redis/history before shortchecks; BOTH600s zero-expiry tests still required.
Task5 COMPLETE;Task6 INCOMPLETE; no new commit/push/main change.

LATEST CONTROLLED DEPLOYMENT CHECK (2026-10-06): clock setup is COMPLETE.
Windows StateMachine Sync, 64s polling, NTP phase -1.889ms; Docker/DB midpoint
about -3ms. Parallel actual normal 1TPS/30s report 20261006T161643262336Z
FAILED: 24 Scored/6 Expired of30, all accepted/published, all24 offline/live
scores match, zero invalid/late executions or correctness failures. Clock checks
passed before/after. Prior 20261006T153146964136Z FAILED12/18 is retained.
Do NOT run full qualification after these failed prechecks or repeat a blind
optimization loop. Expired assignment wait median745.401ms; feature math <2ms;
checkpoint/prediction/commit median461.106ms (overlapping scopes, not additive).
Pacing0.998TPS, no catch-up; sparse queue samples0, no sampled lock blockers.
WAL/IO timing disabled: disk dominance is NOT established. Intermittent remote
round-trip and local CPU/inference/publication spikes remain measured limits.
Owner has NO existing nearby server; none provisioned or bought.
Task5 COMPLETE; Task6 INCOMPLETE/activationHELD. Model/calibration/Review.10/
Block.25/deadline1000ms/durability unchanged; reserved evaluation NOT repeated.
Actual Mumbai target070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2,
run c5b2dab3-0330-4a32-9ba7-82c85d311b40, parallel workerb218/API692b.
Actual17762events/allpublished,12ledger,2350candidatejobs(1662Scored/688Expired),
zero duplicate effects/late executions/prohibited payloads. API readiness503
verified; all application writers subsequently STOPPED, PG/Redis preserved.
New backup mumbai-after-controlled-normal.dump SHA
605bcca7b04937b5623c800d5829f746ba63c7bfc9d19433d39079dc1a15d74c:
archive and FULL isolated PG17 restore PASS;18hashes/catalog/sequences/RLS match.
Read docs/pipeline-qualification.md and ignored controlled-normal-stage-analysis/
controlled-normal-final-state.json. Remaining: meaningful measured correction,
short zero-expiry checks, BOTH600s1/5TPS zero-expiry/parity qualification, then
final SAME-deployment actions/review/restart/Redis/readiness and activation.
No new sync/admin approval needed. Earlier checkpoints below are HISTORICAL.
No new commit/push/main change; Task7 not started.

LATEST OWNER CLOCK VERIFICATION (2026-10-06): owner ran stabilize-clock.ps1;
report PASS, effective 64s polling, fresh successful NTP updates. Windows verified
TLS probes initially ~35ms midpoint offset, Docker ~26ms; Windows held ~23-27ms
across a 70s interval, within existing RTT/2+25ms check. Full-load clock stability
is NOT proven by this short check. Owner clock action is COMPLETE; don't request
the canceled UAC/admin action again. Earlier cancellation notes are HISTORICAL.
Current request asked whether extending the deadline would break the app and to
check the command, NOT to adopt a revised deadline. Keep 1000ms, frozen scorer,
thresholds and reserved results unchanged. No new traffic/writers/activation.
Task5 COMPLETE, Task6 INCOMPLETE: resume held parallel candidate for short1/5TPS,
then BOTH full600s zero-expiry qualifications only if promising, then final same-
deployment action/review/Redis/restart/readiness checks. Evidence in ignored
reports/mumbai-deployment/owner-clock-{verification,stability-verification}.json.

LATEST checkpoint: read docs/pipeline-qualification.md FIRST. CLOCK STABILITY
ADMINISTRATOR PROMPT WAS CANCELED; no polling settings changed. Parallel actual
precheck 20261006T142814197995Z refused before traffic for ~815ms skew. All writers
STOPPED; no further invalid tests. Owner said NO existing remote server; none
provisioned/bought. Pending admin clock-stability approval, then short1/5TPS and
full600sBOTH zero-expiry checks, final exact-deployment actions/review/recovery.
Task5 COMPLETE; Task6 INCOMPLETE/activationHELD. New0012 checkpoint function was
runner-applied to Mumbai; all existing data/guards preserved, browser exec denied.
Single-statement finalization/read-only terminal delivery and initialized API pool
passed180unit/49integration. Two-session per-card parallel candidate passed62
combinedprotocol/actualfrozenmodel checks;67gate/tool checks;9TLSsessions verified.
Selected worker mumbai-parallel b218, API/pub mumbai-ready692b, concurrency2, same
c5b2dab3-0330-4a32-9ba7-82c85d311b40 target070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2.
SERIAL last actual short1TPS30/30max993.319,5TPS110/150,2TPS107/120 NOT activation
or sustainable max. Newparallel workload UNMEASURED dueclock refusal; don't claim
it failed/passed yet. Actual serial actions/reviewPASS20261006T132931925320Z.
Current17702events/allpublished,12ledger;2290candidatejobs terminal1626/664;
zero late effects/prohibited fields. FinalbackupSHA088f28b543b8f0ccc7283f98f7c6bddf35112a99be4599ed08b84ca383e6c3ca.
Private normalizedenv/model/test approvals retained; no retrain,reservedrerun,
deadline/threshold/durabilitychange,commit/push/mainchange. New stability helper
requiresadministrator approval aftercancellation; do NOT relaunch canceled UAC
without renewed approval. Earlier checkpoints below are HISTORICAL.

LATEST 2026-10-06 checkpoint: read docs/mumbai-deployment.md FIRST. Owner supplied
Mumbai URI; verified migration from preserved Tokyo is COMPLETE, all 18 hashes,
catalog/ledger/RLS/role protections matched; runner found no missing migrations.
Actual target is ap-south-1 Session pooler:5432/postgres, pin
070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2.
Current cloud has 17309 events, all published; candidate c5b2dab3-0330-4a32-9ba7-82c85d311b40
has 1897 terminal jobs. Keep .env.application.local plus ignored
.env.supabase-mumbai.runtime.local; original Tokyo/local configs remain rollback only.
Bounded ordered worker grouping/recovery tests passed; normal short 30/30 scored,
peak short 17/150 scored, no late/duplicate effects. Outer pipeline experiment
failed and was removed after read-only pooler probe showed 203ms vs120ms; private
resume selects mumbai-batched image9569, API/pub2ff. All application writers STOPPED.
Windows is UNSYNCHRONIZED AGAIN (Leap3/Stratum0); Windows/Docker ahead of DB ~460ms.
Agent resync returned Access denied; owner was asked for Administrator resync.
This is NEW measured drift, not the previously completed sync request. Await
reply/recheck clocks; don't run another invalid full workload or promise sync
alone fixes peak. Controller now rejects skew before traffic; normal gate600s.
Latest Mumbai backup SHA6605fe5995a071c687e239a804713cba4a4a78ae17f740f4b1255426471aa9ee
fully restored into NEW isolated PG17; all18 hashes/catalog/sequences/RLS matched.
Task5 COMPLETE; Task6 INCOMPLETE/activationHELD. Need valid-clock prechecks,
full600s1 AND5TPS zero-expiry qualifications, final action/review/readiness/restart
checks and Mumbai-pinned deployment evidence before activation. No retrain,
reserved re-evaluation, deadline/model change, commit/push/main change. Older
checkpoints below are historical and do not authorize returning writers to Tokyo.

## Component Names

Owner explicitly requires purpose-based names, not task numbers, for files,
images, containers, environment files and new generated reports. Use roles
(api, publisher, scoring-worker, replay, dashboard), deployment names (local,
supabase, mumbai) and meaningful experiment/version labels. Task numbers remain
valid in planning/gate discussions, NOT as new component names.
Current runtime config is .env.application.local; .env.task6.local is retained
only as an unchanged private rollback copy and compatibility fallback. New load
reports use replay-load/scoring-load/replay-actions and role-named containers.
Canonical image aliases local/dashboard/replay/supabase refer to the SAME
immutable image IDs as before. Historical image aliases, frozen packages,
authorization JSON, audit reports, migration names, Redis/run identities and
legacy test safety identifiers are not rewritten/deleted merely for naming.
The isolated test project is sentinel-test, retaining legacy DNS aliases and
sentinel_task4_test solely for immutable-image/fixture safety compatibility.
Read docs/component-naming.md for the mapping. No performance/model gate is
waived by a naming change; do not start stopped writers during this cleanup.

Latest 2026-10-06 valid-clock checkpoint: read docs/supabase-clock-resume.md FIRST.
Owner confirmed time sync; Windows NTP is synchronized and Windows/Docker-to-DB
midpoint offsets are now a few ms (with RTT/2 uncertainty). Do NOT ask for time
sync again. Original Docker engine/volumes recovered after a slow cold start;
no resets, resource-limit changes or source writes. Same cloud images/run/model,
1000ms deadline, Review 0.10/Block 0.25 and durability are unchanged.
Valid-clock normal 1 TPS/30s FAILED 0 Scored/30 Expired, all accepted/published.
Short nominal peak 5 TPS/10s FAILED: 50 attempts, 44 accepted/all Expired,
six ingestion errors, actual offered 3.908 TPS, not a sustained 5 TPS test.
No full 600s tests after failed prechecks. No new executions/labels/score-parity
PASS. All 1607 candidate features/hashes reproduce; all 74 new records settled.
Client DB calls take ~145-160ms versus server history/UPDATE mean ~0.27/0.33ms;
earliest normal assignment 1179.54ms, queue waits grow to seconds. Network,
serial pipeline and pool costs are measured; do not blindly optimize/increase
deadlines or promise clock correction alone solves performance.
Cloud has 17019 events/history/snapshots, all outbox published, ledger 11;
source still matches ALL 18 hashes and is read-only. Rollback delta is now 197
cloud-only events, not 123. New native backup SHA-256
1e21694caf6a5005e1c9c001c613cb86bbb372477e32462360e38aae87c78bff
validated all archive blocks; previous full cloud restore proof is retained.
All cloud writers STOPPED; scoring health workload_gate_failed, activation held.
Task 5 COMPLETE; Task 6 INCOMPLETE; Task 7 not started. No code/model changes,
retraining, reserved evaluation, runtime promotion, commit/push or main change.
Owner was asked to select/provide a closer DB project (e.g. Mumbai) OR an
existing host near Tokyo for API/publisher/worker/Redis. No choice/paid resource
is assumed. Test the proposed target's latency/TLS BEFORE any further migration,
preserve all data/configs, then controlled short checks before full 1/5 TPS and
final deployment action/review/readiness/recovery gates. Prior clock-blocker
instructions below are HISTORICAL; existing ML approvals need no repetition.

Historical Supabase checkpoint (2026-10-05): owner explicitly resumed after the PC
shutdown. Read docs/supabase-database-migration.md FIRST; all older preparation,
missing-CA and no-import statements below are HISTORICAL. Cloud import and full
recovery verification PASSED. Supabase Session pooler ap-northeast-1:5432/postgres
is the confirmed application target, verified TLS with supplied CA; non-secret
target pin 084cfe3ed139d7af8191b42278c4947dcf399fa01256041711a844e1d428e28f.
All 18 imported hashes/binary floats match; ledger 0001-0011, migration runner
returned no migrations. Built-in schemas preserved; app RLS/role revocations
applied atomically. Explicit SET extra_float_digits=3 is required per session;
Node startup options alone were ineffective on the pooler. New cloud images
and ignored .env.supabase.local are separate from original qualified runtime.
Cloud retains 16945 events/history/snapshots: original 16822 plus 123 accepted
diagnostic events, all Expired. Normal 30 attempts/30 accepted, peak 150/93;
zero new scoring results/executions. No new score-parity PASS is established.
All 123 ultimately published with no dead letters. The measured publisher
single-connection retry defect was fixed by releasing after rollback before
CAS recovery; cloud batch size is ONE, same 200ms budget/fence/durability.
175 backend unit, 49 integration, 80 combined Python and a separately enabled
isolated Redis-restart check passed. Actual expired-event duplicates added no
effects; same-run restart reproduced all 1533 feature/history/job records.
Final cloud backup 9230e04bd119978dc68d8e333bb036649c0ae8230701532f23c52cf7f9b959d3
restored into NEW isolated PG17, all 18 hashes and complete catalog/sequence/RLS
checks matched. Original local source still matches ALL 18 hashes, database
read-only; original volumes/config/images/source backup preserved. No split
writes or volume deletion. Local rollback MUST reconcile the cloud-only delta.
BLOCKER: Windows and Docker clocks are about 1090ms behind Supabase, Windows
Leap Indicator 3/Stratum 0 (unsynchronized); w32tm /resync was access-denied.
Owner was asked to run that command in ADMINISTRATOR PowerShell. Performance
tests are paused until offsets are rechecked, not authorized for a longer
deadline. 150-195ms DB round trips and pool/backlog costs also remain measured;
do not promise clock synchronization alone fixes throughput. All cloud writers
are STOPPED and scoring health is clock_sync_required with activation hold.
Task 5 COMPLETE, Task 6 INCOMPLETE/activation BLOCKED, Task 7 not started.
No frozen model/threshold/1000ms deadline change, reserved reevaluation, runtime
promotion, commit or push. Main remains b767e1cc4a232edd9fdc790b843f1e3c809e26c3,
work remains on ritwik. Resume with both private env files/cloud override; wait
for history/Redis recovery, run valid-clock short checks before full 600s 1/5 TPS
qualifications, require zero expiries/parity/once-only/no-late behavior, then final
action/review/readiness/restart checks. Do not request recorded ML approvals again.

Historical interruption checkpoint: owner reported an unexpected PC shutdown during
Supabase migration preparation. Heavy work is STOPPED; do not launch parallel
builds or benchmarks before checking stability and recovery. Owner supplied
Downloads/prod-ca-2021.crt; it is copied to ignored secrets/supabase-root.crt.
CA file SHA-256 is 700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7.
Verified Node TLSv1.3 authentication passed on Windows AND Docker; eight
concurrent Session pooler sessions passed. Free-plan 500 MB quota was supplied
in the owner's screenshot. Destination PostgreSQL 17.11 has empty public,
fsync/synchronous_commit on, server max_connections 60. Backend pg_stat_ssl is
false for the pooler's INTERNAL hop, not the authenticated encrypted client
socket; both were reported separately. Python connected/query succeeded but
the probe then hit an AttributeError for info.ssl_in_use: correct the probe,
do not weaken TLS. No cloud application RESTORE was launched and no cloud data
was written. Original source remains preserved, with writers held off before
the shutdown. The remote-before-import backup and both image builds were running
when the host restarted; their tool sessions are unavailable. Inspect outputs
and validate source recovery before resuming; do not assume those jobs finished.
No remaining matching build clients were found. Windows logged Kernel-Power 41
and 6008, BugcheckCode 0; the cause is unresolved, not proven memory/heat/power.
Original .env.task6.local is unchanged; ignored .env.supabase.local and the
native-client environment were generated separately. Task 5 complete, Task 6
incomplete and activation blocked. Older missing-CA statements are historical.

Historical Supabase migration preparation (2026-10-05): read
docs/supabase-database-migration.md first. Owner supplied DATABASE_URL in ignored
backend/.env and authorized migration, but verified TLS fails on Windows/Docker
with SELF_SIGNED_CERT_IN_CHAIN. Root CA and dashboard quota/pooler limits are
requested; no import or target switch occurred. All application writers are
stopped; original PG/Redis run on preserved volumes. A fresh public-schema dump
77ea93b7b9126cadf01e58b60a8feddea9e59fb8b012772d622808c1277eebe9
restored into NEW sentinel_supabase_recovery_20261005 with all 18 table hashes,
33 indexes, 12 functions, 23 triggers and sequence states matching. All 106
constraints remain (one reviewed equivalent CHECK parenthesis regrouping).
Source has 16822 events; all outbox published, all jobs terminal, Redis pending
zero. Remote configuration/security tests and an inactive Supabase override are
prepared. Do not enable it before verified TLS/capacity/import comparisons.
Task 5 remains complete; Task 6/activation remain blocked. Do not repeat the
reserved evaluation or weaken the approved one-second deadline/durability.

Latest 2026-10-05 storage/pipeline checkpoint: read
docs/storage-and-pipeline-correction.md before older records. Only one SATA HDD
exists; Docker data/WAL use its Linux ext4 virtual disk. No SSD target is
available, so no storage move was performed. A writers-stopped backup restored
into a NEW isolated recovery database: all 18 content fingerprints matched;
all original rows still match after testing. All 106 constraints are retained.
Paced sends no longer catch up; stream recovery audits batch before ACK,
startup readiness waits for reconciliation, and unpublished predecessors no
longer create redundant history commits. Publisher recovery protocol and total
200ms publication budget are preserved; premature 100ms call cap was removed.
Final actual one-second 1 TPS/600s PASSED 600/600, max 951.522ms. Final paced
5 TPS/60s FAILED 294 Scored/6 Expired, exact parity and no late execution.
No full peak was run after the failed short check. Observed normal capacity is
1 TPS for ten minutes, not an established maximum or revised acceptance target.
No further speculative optimization/deadline increase. Task 5 COMPLETE; Task 6
INCOMPLETE. Candidate worker is stopped with restart disabled; previous qualified
API/publisher restored. Scoring readiness stays 503. Actual sentinel has 16822
events/jobs, ledger 0001-0011; original private configuration/run and all data
are preserved. No frozen model/threshold/durability change, reserved-test rerun,
activation, commit or push. Task 7 not started. Older checkpoints are historical.

Previous 2026-10-05 diagnostic checkpoint: read docs/two-second-diagnostic-trial.md.
Owner authorized a TWO-SECOND diagnostic, not adoption or activation. Immutable
run 9b8fc17d-dc22-49d8-8668-2cdc0afe9414 uses 2000ms; original run
e7d43b39-fd79-4368-818d-899c2415434a remains 1000ms. Combined-commit
worker tests passed 85/85. Actual full 1 TPS/600s passed 600/600 with zero
expiry; actual full 5 TPS/600s FAILED 2927 Scored/73 Expired, exact scored
parity, zero late executions and queue max 11. The original one-second
requirement remains unmet; even the two-second trial failed peak acceptance.
Task 5 COMPLETE; Task 6 INCOMPLETE. Diagnostic worker is STOPPED. Qualified
API/publisher image b6d0d7e3 was restored and verified; scoring readiness is
HTTP 503. Application ledger 0001-0011, 15412 events/jobs and existing volumes
are intact. No deadline/model/threshold/durability change or reserved-test
rerun. No new commit/push. Older checkpoints below are historical.

## Scope

This repository is for a real-time adaptive financial-fraud detection platform. The planned system has six future boundaries: streaming ingestion, real-time feature engineering, adaptive class-imbalance handling, hybrid ensemble scoring, concept-drift monitoring with incremental updates, and decision/alerting.

The application has Express ingestion, PostgreSQL audit/outbox, Redis and an operational dashboard. Active data is `kartik2112/fraud-detection/versions/1`; Task 4 and Task 5 gates passed. The owner approved sigmoid RF (r=0.1, b=0.25), then separately authorized one evaluation of frozen manifest `1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`. That final test passed without tuning; do not repeat it. Read `docs/task-5-final-test-record.md` and `docs/scoring-verification.md` first. The connected Python worker exists but application activation and Task 6 remain incomplete. Actual `sentinel` on localhost:15432 has migrations 0001-0009, verified on 2026-10-03. Never reset volumes. Preserve failed load reports and existing work. Do not request recorded approvals again or confuse receipts with fraud decisions.

Read available authoritative material in `docs/planning/` before planning multi-step work. The user-supplied dataset-switch-through-Task-6 PDF defines this migration's gates; the old planning directory is absent in the inspected checkout. Explicit user instructions take precedence over stale task boundaries.

Latest 2026-10-04 publisher checkpoint: owner explicitly approved the local
publisher commit-reduction implementation/testing, NOT activation or weaker
durability. Read docs/publisher-recovery-protocol.md and the latest verification
record. Candidate sha256:92aac19cd94749b2cdbc17561424f37e4bc6c19c3f4503fbbaae9c43903de013
uses one bounded sequential publication transaction, a shared ordering fence,
and rollback/CAS failure recovery. 46 backend integration, 154 unit and 76 ML
checks passed, including actual publisher death and direct worker replay proving
once-only features/history/results/actions. Matched actual 5 TPS/30s diagnostics
improved 112 Scored/38 Expired to 147/3, but strict zero expiry did NOT pass.
Candidate isolated normal passed 60/60; full 5 TPS/600s FAILED 2940/60. Candidate
actual normal diagnostic FAILED 58/2. No candidate runtime-pin promotion or full
actual peak bypass occurred. No reliable zero-expiry actual throughput is proven
for this candidate. Remaining tail cause is unresolved; avoid arbitrary tweaks
or blind workload repetitions. Previous qualified backend is restored and scoring
is STOPPED/workload_gate_failed. Model, thresholds, deadline, volume and reserved
test remain unchanged. Task 5 COMPLETE; Task 6 INCOMPLETE; Task 7 not started.
All earlier pending-publisher-approval statements are now historical. Preserve
candidate/baseline images, failures, private credentials/run and original data.
No commit/push/merge was authorized or performed.
Application now retains 11152 events/jobs/history/snapshots, 6092 Scored and 5060
Expired, 6661 private predictions and three review resolutions. Ledger 0001-0010
is verified. Fresh recovery dump SHA-256
8d6f593f6e6422fb811b10b6d98bba171ea6f58d490d4eed980b55c29977c537 restored into
NEW isolated sentinel_publisher_recovery_20261004: nine table-content fingerprints
matched, including the outbox. The isolated restore is disposable, dump retained.

Previous 2026-10-04 evening checkpoint: read `docs/scoring-verification.md`.
Candidate-ID-first polling and a covering partial index were added; batch
finalization now uses one dependency-linked statement with unchanged guards.
Application ledger is 0001-0010; existing data/volumes are intact. Current worker
is sha256:f5fcba36304c0400509b0694342a6296ef7df51e644d39e09e6493fee0afa5bc;
API/publisher are sha256:b6d0d7e396c067a434312905cbb7278c26974bcd8ecd7793257da8f59f5f9c6e.
Both isolated rates passed. Actual normal 20261004T164608670040Z passed 60/60;
actual full peak 20261004T164751054593Z FAILED: 2418 Scored/582 Expired.
All scored parity and no late execution passed. 73 ML checks including Redis
restart passed; five schema/migration integration checks passed. Actual actions
and same-run restart passed on this build. Native pg_test_fsync measured default
fdatasync about 35 ms/flush (28 ops/s); settings were not changed.
Actual has 10770 events/jobs/history/snapshots, 5770 Scored and 5000 Expired.
A fresh schema-10 populated dump restored into a NEW isolated target; eight
table-content fingerprints matched. Worker is STOPPED, readiness is false with
workload_gate_failed. Task 6 remains INCOMPLETE; Task 5 checksums are unchanged.
Owner approval is PENDING for changing the publisher to one bounded row-lock
transaction spanning Redis publication and durable outcome storage, rather than
separately committing its claim. That protocol change was NOT implemented.
Do not infer approval from a preselected async-question option. Existing model,
policy, deadline, database and zero-expiry approvals need not be requested again.
Preserve private credentials/run identity, all failed reports and original data.
No commit/push was done this turn. Task 7 has not started.

Previous 2026-10-04 checkpoint:
Worker assignment/first preparation are fused; batches of at most four already
waiting transactions share durable checkpoints and prediction/execution commits.
Prediction COMMIT acknowledgement still precedes a separate execution transaction;
per-transaction expiry and recovery guards remain unchanged. Qualified worker is
sha256:39dfd04e02bfa75b8e4ec2ea138ad6752dd2dd2928d8eec24eb0f06915602683.
Both isolated rates passed. Actual normal 20261004T153215710833Z passed 60/60;
actual full peak 20261004T153400606949Z FAILED with 2409 Scored/591 Expired.
Full scored parity and no late execution passed. Diagnostic 2 TPS/60s passed
120/120; 3 TPS/60s missed one of 180. These do not replace the required 5 TPS gate.
Actual actions/review and same-run restart passed again. Application now has
7707 events/jobs/history/snapshots; no original data or volumes were reset.
Worker is STOPPED and readiness is workload_gate_failed. Activation remains
blocked; Task 6 is NOT complete. Task 5 package/test checksums are unchanged.
The fresh 3983-event backup restored into a NEW isolated recovery database.
Read the verification record for exact reports and final test results.

Previous 2026-10-03 checkpoint: original
application storage is restored and migrations 0001-0009 are verified. The owner
now requires zero expiries at controlled normal load and at 5 TPS for ten minutes.
Precommit-only load timestamps are not activation proof; new runs use postcommit-v1.
Forty-three worker/tool checks passed including delayed COMMIT safety and
non-busy waiting for publication/retry. Atomic v2 ingestion reduces seven DB
calls to four; 38 backend integration and 154 unit tests passed. Its new image
passed isolated 60/60 normal and 3,000/3,000 ten-minute peak qualification.
Reference model loading is now deferred until after benchmark traffic, retaining
pre-traffic package integrity checks. Forty focused tool tests passed.
ACTUAL persistent application normal report 20261003T125806294035Z scored all
60 at 1 TPS/60s with zero expiry, but full 5 TPS/600s report
20261003T130023513748Z scored only 67 and expired 2,933 of 3,000. No expired
transaction executed. Do not substitute isolated performance for application
qualification. General activation remains blocked and the worker is stopped.
Actual actions/review and same-run restart passed. Preserve private
.env.task6.local, its credentials and durable run
e7d43b39-fd79-4368-818d-899c2415434a. Preserve all accumulated application data;
no reset/truncation is permitted. The populated 863-event recovery checkpoint
restored into a NEW isolated database, with eight table-content fingerprints
matching. Runtime requalification archives previous metadata and preserves
credentials/run identity. No worker assignment/preparation fusion was applied;
the user redirected work to committing/pushing ritwik before that change.
The reviewed 2 GB WSL cap is unchanged. Zero expiries at BOTH rates remain
mandatory. Do not repeat the completed reserved test or claim failed/early-stop
load runs are passing evidence. Task 7 is not defined by the supplied guides;
their G7 is a Task 6 recovery/handoff gate, not Task 7.

## Working agreements

The owner requested independent RF and four-model ensemble development tracks.
Read `docs/model-tracks.md`. RF selection never approves an ensemble policy;
keep artifacts, results and policy proposals track-scoped. Both share the
existing source/feature contract and locked-test gates. Neither is live.

- Inspect before editing and preserve existing user files.
- Keep changes within the approved task; do not begin the next task implicitly.
- Prefer the smallest maintainable solution and avoid premature frameworks or production dependencies.
- Never add real secrets, credentials, raw financial data, local datasets, model binaries, caches, logs, build output, or generated artifacts to Git.
- Use placeholders in `.env.example`; real values belong only in ignored local environment files.
- Explain and obtain approval before system-level installation, destructive work, architecture decisions, or expanded permissions.
- Do not commit, push, merge, configure branch protection, or modify remote state without separate owner approval.
- Review the final diff and report only checks that were actually run.

## Future engineering conventions

- Python projects should use `pyproject.toml` and a reproducible lock strategy selected in the task that introduces Python code.
- Node projects should use one approved package manager and commit its lockfile when frontend work begins.
- Formatting, linting, static typing, and tests must be introduced with the relevant implementation task.
- Docker Compose configuration belongs under `infrastructure/` and must retain project isolation, explicit image tags, localhost-only ports, health checks, and non-destructive default shutdown/cleanup behavior.
- `make verify` is the unified repository verification command. Keep it truthful and extend it only with checks required by an approved task.

## Manual-blocker protocol

When safe progress depends on a human action, continue only independent inspection and pause the affected operation. Do not guess, simulate, or silently replace the missing step. Use:

```text
MANUAL ACTION REQUIRED - [short title]
Status: BLOCKING or NON-BLOCKING
Why it is needed: [one precise explanation]
What I verified: [evidence already checked]
Your exact action: [numbered steps or exact UI path/command]
Expected confirmation: [what the user should reply or provide]
Safety note: [credential, destructive-action, or permission warning]
Codex state: Paused before [specific operation]. I will resume from [specific step] after confirmation.
Reply with: Done - [requested confirmation] or describe the problem encountered.
```

Never request a password, token, private key, or secret value in chat. Manual actions include missing planning inputs, authentication, external account access, admin installation, unresolved ownership/product decisions, destructive operations, and commit/push/merge authorization.

## Verification and handoff

Verify the repository tree, Git status, ignore behavior, instruction discovery, and the final diff as applicable. Confirm no dependent task starts before its evidence gate. Run destructive integration fixtures only against explicitly isolated test services; never truncate application data or downgrade populated application schemas for verification.

Every task handoff must state the status, outcome, changed files, checks and exact results, scope confirmation, risks/deviations, and the next task (not started). It must end with both sections below, using `None` explicitly when appropriate:

- `PENDING MANUAL ACTIONS - BLOCKING`
- `PENDING MANUAL ACTIONS - NON-BLOCKING`
