# Repository Instructions

## Scope

This repository is for a real-time adaptive financial-fraud detection platform. The planned system has six future boundaries: streaming ingestion, real-time feature engineering, adaptive class-imbalance handling, hybrid ensemble scoring, concept-drift monitoring with incremental updates, and decision/alerting.

The application has Express ingestion, PostgreSQL audit/outbox, Redis and an operational dashboard. Active data is `kartik2112/fraud-detection/versions/1`; Task 4 and Task 5 gates passed. The owner approved sigmoid RF (r=0.1, b=0.25), then separately authorized one evaluation of frozen manifest `1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`. That final test passed without tuning; do not repeat it. Read `docs/task-5-final-test-record.md` and `docs/task-6-verification-record.md` first. The connected Python worker exists but application activation and Task 6 remain incomplete. Actual `sentinel` on localhost:15432 has migrations 0001-0009, verified on 2026-10-03. Never reset volumes. Preserve failed load reports and existing work. Do not request recorded approvals again or confuse receipts with fraud decisions.

Read available authoritative material in `docs/planning/` before planning multi-step work. The user-supplied dataset-switch-through-Task-6 PDF defines this migration's gates; the old planning directory is absent in the inspected checkout. Explicit user instructions take precedence over stale task boundaries.

Latest checkpoint: read `docs/task-6-verification-record.md` first. Original
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
