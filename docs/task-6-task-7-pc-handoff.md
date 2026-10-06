# Original-PC handoff: Task 6 and Task 7

Imported laptop handoff, preserved during local reconciliation of `410472e`.
Deployment/storage/clock measurements below are historical. Current Task 6
status is authoritative in [pipeline-qualification.md](pipeline-qualification.md):
Mumbai is already migrated, clocks are synchronized, but actual parallel normal
prechecks still failed. Neither branch reconciliation nor this Task 7 scope
description activates scoring or starts another implementation stage.

The owner explicitly defined Task 7 on 2026-10-05 as verification of the frozen
scorer's historical/live features. This supersedes older statements that Task 7
is undefined. It does not authorize activation, learning or a new model.

Current status: Task 5 complete; Task 6 incomplete because actual peak
qualification failed; Task 7 defined but not started. Shared-server hosting
remains undecided, with a zero-cost requirement; no deployment is authorized
by this handoff.

## Before continuing on the original PC

1. Inspect Git status and preserve local edits. Fetch `origin/ritwik` and
   fast-forward the local branch only when safe; do not reset or discard work.
2. Read `AGENTS.md`, `storage-and-pipeline-correction.md`,
   `scoring-verification.md`, `task-5-final-test-record.md`,
   `model-tracks.md`, and `task-6-evidence-availability.md`.
3. Locate the original ignored reports, frozen model bundle, private
   `.env.task6.local`, runtime metadata and database backup/evidence. Keep
   credentials local and out of Git/chat. Inspect available authoritative
   planning inputs without treating missing older guides as a new task definition.
4. Verify the actual Docker context, database identity, existing volume,
   migration ledger and stopped worker state. Do not treat this laptop's
   September 21 volume or NVMe storage as the original application checkpoint.
5. Read `docker-naming.md` before using Compose. New image tags do not transfer
   through Git. Tag existing exact images locally under the new purpose names,
   or use supported explicit image overrides. Verify image-ID equality; do not
   rebuild or promote an unqualified image merely to satisfy a new name.

## Task 6: resolve the remaining peak failure

Baseline: original one-second requirement; final peak report
`services/ml/reports/task6-application-load/20261005T031524428781Z/report.json`
has 294 Scored / 6 Expired over 60s at 5 TPS. Normal report
`20261005T031745589285Z/report.json` passed 600 / 0 over ten minutes at 1 TPS.
The peak report's expected SHA-256 is
`f1a4e392aa621ff01bfd5bcc0d3fa927f4bbddc068f632e595cb70c62120614c`.

1. Correlate all six expired event UUIDs with successful same-run events using
   `event-stage-traces.json`, report timings and worker/publisher/ingestion logs.
   Produce ingestion, publication, queue, history, feature, inference and commit
   timelines, including available pool/lock waits. Mark missing timestamps
   explicitly. Deferred log timestamps are not stage boundaries; shared batch
   scopes overlap and cannot be added as independent per-event latency.
2. Identify the dominant delay before editing. If the existing evidence lacks
   needed boundaries or blocking identities, add focused timing instrumentation
   and run a short diagnostic on the verified application target first.
3. Apply only the measured fix. For lock/pool delays, identify the blocker or
   exhaustion. For history delays, examine query plans/indexes without changing
   feature meaning. For queue delays, distinguish growing backlog from polling
   or serialization; preserve ordering and introduce concurrency only where safe.
4. If storage is the measured limit, verify physical PGDATA/WAL backing. An
   available SSD target may be used only through verified backup/restore into a
   NEW isolated database. Retain the original, compare ledger, constraints and
   content fingerprints, then align every component to the verified target with
   old writers held off. If no SSD exists, report the constraint and observed
   passing throughput; 1 TPS is not an established maximum or revised target.
5. Run short diagnostics first. Only after the targeted delay is resolved, run
   the full ten-minute 5 TPS test. BOTH final 1 TPS/600s and 5 TPS/600s must have
   zero expiries. Requalify final normal load and affected recovery boundaries
   after deployment/storage/protocol changes; reuse existing valid evidence only
   when it applies to the exact final configuration.
6. Verify exact offline/live parity, duplicate protection, durable ordering,
   no expired execution, affected crash/retry recovery, readiness, Pass/Block
   execution, authorized Review resolution and final restart. Activate only
   after all agreed checks pass. If a targeted attempt still fails, return its
   slow-event traces and stop the speculative optimization loop.
7. Report cause, exact changes, before/after timings, scored/expired counts and
   remaining blockers. Preserve every failed and successful report.

## Task 7: verify the frozen scorer's feature contract

Task 7 can proceed independently of Task 6 peak acceptance. It needs the exact
frozen bundle/manifest for final verification; Task 6 performance logs are not a
prerequisite. Task 4 shared history features and replay evidence should be reused.

1. Read the actual frozen feature list and compare offline preprocessing, live
   worker, simulator and replay inputs. Record each feature's implementation and
   verification status; identify gaps without rebuilding correct features.
2. Produce a feature dictionary covering meaning, source fields, calculation,
   units, transformations, history window, ordering and missing-history behavior.
   Use code/artifacts; do not invent device, balance or other absent input fields.
3. Verify only prior available history contributes to the current transaction.
   Check first events, timestamp ties, unseen categories, event-time units,
   duplicate/retry once-only history, restart reconstruction before scoring and
   replay-speed independence. Include both feature-vector and scorer-level
   offline/live parity where applicable.
4. Use development data or safe fixtures. Repair only live-path deviations from
   the frozen contract; preserve its meaning. Run focused feature/parity checks
   across duplicate and restart boundaries using explicitly isolated fixtures.
5. Deliver the dictionary, gap checklist, exact changes, checks/results and
   remaining blockers. If the contract is already satisfied, demonstrate that
   with existing valid evidence and focused checks instead of adding code.
6. Report Task 7 separately. Its completion neither completes Task 6 nor permits
   scoring activation. Feedback learning, drift monitoring, automatic retraining
   and frontend work remain outside scope.

## Boundaries for both tasks

Keep the frozen RF/calibration and Review 0.10 / Block 0.25 unchanged. Frozen
manifest: `1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`.
Do not retrain or repeat the completed reserved evaluation. Keep the one-second
deadline, fsync, synchronous commits, duplicate protection, historical-feature
parity and no execution after expiry. Keep labels outside scoring and raw card
numbers outside application data/logs. Preserve all records, credentials, run
identities, volumes and failures; never reset/truncate the application database.
Document new-feature ideas separately as future proposals. No subsequent commit,
push, merge or server provisioning is authorized by this handoff alone.
