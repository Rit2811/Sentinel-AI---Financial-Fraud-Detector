# Repository Instructions

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

The application has Express ingestion, PostgreSQL audit/outbox, Redis and an operational dashboard. Active data is `kartik2112/fraud-detection/versions/1`; Task 4 and Task 5 gates passed. The owner approved sigmoid RF (r=0.1, b=0.25), then separately authorized one evaluation of frozen manifest `1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`. That final test passed without tuning; do not repeat it. Read `docs/task-5-final-test-record.md` and `docs/task-6-verification-record.md` first. The connected Python worker exists but application activation and Task 6 remain incomplete. Actual `sentinel` on localhost:15432 has migrations 0001-0009, verified on 2026-10-03. Never reset volumes. Preserve failed load reports and existing work. Do not request recorded approvals again or confuse receipts with fraud decisions.

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

Previous 2026-10-04 evening checkpoint: read `docs/task-6-verification-record.md`.
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
