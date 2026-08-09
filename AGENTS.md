# Repository Instructions

## Scope

This repository is for a real-time adaptive financial-fraud detection platform. The planned system has six future boundaries: streaming ingestion, real-time feature engineering, adaptive class-imbalance handling, hybrid ensemble scoring, concept-drift monitoring with incremental updates, and decision/alerting.

The current baseline is the Task 2 local platform shell: FastAPI `/health` and `/ready`, a neutral React/Vite page, PostgreSQL and Redis health, and Docker Compose tooling. Do not add transaction APIs, business schemas, Redis Streams/workers, authentication, product workflows, fraud rules, scoring, dataset processing, machine learning, or AI unless a later task explicitly authorizes it.

Read the authoritative material in `docs/planning/` before planning multi-step work. Prefer the patent for product and architectural intent and the Task 1 guide for repository-foundation controls.

## Working agreements

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

Verify the repository tree, Git status, ignore behavior, instruction discovery, and the final diff as applicable. Confirm that the change contains no premature application or ML/AI implementation.

Every task handoff must state the status, outcome, changed files, checks and exact results, scope confirmation, risks/deviations, and the next task (not started). It must end with both sections below, using `None` explicitly when appropriate:

- `PENDING MANUAL ACTIONS - BLOCKING`
- `PENDING MANUAL ACTIONS - NON-BLOCKING`
