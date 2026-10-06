# Connected Scoring Worker

Latest deployment/gates: [Mumbai deployment](mumbai-deployment.md). Cloud migration
and backup restore passed. Workload acceptance and final activation remain pending;
writers are paused after renewed clock drift. Older checkpoints below are historical.

Current verification is in `scoring-verification.md`. Application migrations
and backup restore are verified. The worker's 20 connected checks pass; sustained
peak deadline acceptance still fails under observed host resource pressure.
The preparation/history notes below are retained as earlier checkpoints.

## Current Gate Status

Latest recovery checkpoint: original WSL containers/volumes returned after the
owner re-enabled the WSL engine and Docker Desktop restarted. The six-migration
backup restored successfully into `sentinel_worker_recovery_probe` in isolated
PostgreSQL: six ledger entries, 12 public tables, zero events/results/executions.
The repository runner then applied 0007/0008 to the ORIGINAL `sentinel` database
on port 15432. Its eight ledger entries and zero events were verified. No volume
or application database was replaced. Historical interruption notes below are
retained; the application migration and backup-restore gates are now passed.

The worker image built successfully with locked dependencies, image ID
`sha256:fcd4abdffc577e30798fe89ab25a9dc5715a9fd6af27ae17897362603c51d92e`.
Runtime verification/activation and load acceptance remain pending.

The first post-recovery worker run returned 12 passed, 4 failed, 1 setup error:
one DB connection timeout, one missing timely RF result, two child-process startup
timeouts and sandbox denial of the Docker restart test. Build activity and only
426,952 KiB free host RAM were observed. These are not passing recovery evidence.
Tests must be rerun with required Docker access and without concurrent builds.
The RF test now performs the same pre-traffic reference verification as production.

Task 5 passed its owner-authorized frozen-package evaluation; see
`task-5-final-test-record.md`. Task 6 is NOT complete and the application scoring
worker has NOT been activated. Earlier preparation documents describe their
historical checkpoint; this document supersedes their missing-worker statements.

The connected worker exists in `services/ml/src/fraud_ml/worker.py`.
It loads the frozen RF, verifies package/reference checks and requires an externally
pinned passing final-test report before connecting in application mode.
`--fixture` is restricted to the disposable loopback database and Redis ports.
The four-model track is not served by this worker.

## Implemented Path

Express ingestion persists canonical events and outbox entries. The publisher
delivers safe envelopes to Redis. One Python worker owns a PostgreSQL session
lock per run, assigns attempts in database acceptance order and constructs
point-in-time features from durable, deduplicated history. Snapshots and their
hashes are stored before inference. Same-second peers are excluded; expired and
failed attempts still contribute to later history. Late per-card source events
block the run instead of changing earlier decisions.

Actual calibrated probability, thresholds, correlation identity, versions and
timestamps are committed with terminal job state. A deferred database trigger
performs the simulated action once: allowed, pending_review or rejected.
Authorized human review adds a separate immutable resolution, never overwriting
the original decision or creating a confirmed fraud label.

One-second expiry is measured from acceptance, not when the worker picks up a
job. Late inference produces Expired without execution. Transient inference
failures retry only before expiry, at most three times. Pending, unavailable,
failed and expired are not Pass/Review/Block. Express exposes stored truth and
scoring readiness requires a fresh, unblocked application-worker heartbeat.

Redis ACK follows durable completion or a durable poison-message failure record.
Lost Redis state can be reconciled from PostgreSQL outbox/jobs/history. Restart
must use the SAME run ID and package. History is checked/reconstructed against
stored feature snapshots before readiness. A new run starts with newly accepted
events and cold history; it is not a mechanism to rescore historical transactions.

## Database and Recovery

Immediately before this session's Docker interruption, the actual target was
confirmed as `sentinel` at 127.0.0.1:15432, with migrations 0001-0006 and zero
events/results/executions. Host API and Compose API/publisher/worker target the
same database. Application migrations 0007 and 0008 remain pending.

0007 adds immutable run registry, durable history, attempt audit, terminal failure
and worker-health records. 0008 adds accepted-at lookup and pending-job indexes.
Both applied successfully to the explicitly isolated test database. This is NOT
proof of migration on the application target.

Fresh six-migration backup:
`services/ml/artifacts/database-recovery/20261002/sentinel-before-worker-migrations.dump`

SHA-256: `9e241a1a150e6d716d09ef467ce42762f6aa57040db24616cbece96720cc8774`.
The dump command completed, but its isolated restore verification was interrupted
by Docker errors. Do not call this backup recovery-verified yet. The older empty
baseline backup and its successful restore remain documented in
`scoring-execution-recovery.md`.

The owner reported changing Docker's RAM limit from 2 GB to 1 GB and restoring
it to 2 GB. During this transition the daemon returned 500/502 errors and empty
container/image/volume listings. No volume reset, database drop or application
replacement was performed. Verify original storage returns, verify the fresh
backup by restore into a NEW isolated database, then use the repository migration
runner for application 0007/0008 and inspect the actual ledger.

Follow-up diagnosis: Docker settings report `MemoryMiB=2048` but
`WslEngineEnabled=false`. The active non-WSL engine has zero containers, images
and volumes. Historical logs show the original WSL engine running before the
settings change; `docker-desktop` WSL is now stopped. The original
`Docker/wsl/disk/docker_data.vhdx` still exists (21,541,945,344 bytes).
This supports an engine switch, not a proven loss of database data. The owner
was asked to re-enable the WSL 2 engine using Docker Desktop Settings > General.
Do not recreate the application database on the empty alternate engine.

## Workload Evidence

All benchmarks use label-free generated events, not the reserved dataset. They
exercise real HTTP ingestion, PostgreSQL, Node outbox publisher, Redis, frozen RF
worker and authenticated HTTP result observation. They do not measure fraud
quality. The benchmark uses publisher polling 50 ms (production default is 500
ms); configure `STREAM_POLL_MS=50` explicitly for a matching activation profile.
Fixture database storage is tmpfs, not the persistent application volume.

Earlier normal run:
`services/ml/reports/task6-worker/20261002T085321411192Z/report.json`

60/60 scored at 1 TPS; HTTP-observed p95 347.39 ms, maximum 455.88 ms;
all scored rows matched offline features/probabilities/actions.

Earlier full peak run FAILED:
`services/ml/reports/task6-worker/20261002T085639747649Z/report.json`

3,000 accepted at 5 TPS for 600 seconds; HTTP observed 251 scored, 20 expired and
2,729 observation timeouts. These are observation counts, NOT final durable
database status totals. Queue sample maximum 733. The report preserves 683
failures including missing unassigned snapshots and one SQL constraint error.
Do not hide or replace this failed run.

Follow-up changes: accepted-at index, indexed pending-job ordering, fewer scoring
query round trips, database-clock result timestamps, HTTP polling reduced from
25 ms to 100 ms. The benchmark now reports durable job counts and checks for
invalid/late execution separately. These changes have NOT yet passed a fresh
full peak run. Neither the deadline nor model thresholds were relaxed.

## Verification Limits

Earlier worker tests exercised duplicate delivery, lost ACK, actual process death
before commit and after commit/before ACK, missing-history restoration, stream
loss, all three actions, ordered features, retries and late inference. This session
first ran 15 tests: 14 passed; frozen-RF parity timed out. Its extra offline
prediction was moved after live scoring so it no longer consumes the deadline.
The rerun was interrupted by Docker failure; it is not a passing rerun.

Additional tests now cover database connection termination and an explicitly
opted-in restart of ONLY the disposable Redis container. These require a fresh
successful connected run. Infinite hung inference has no hard process watchdog:
readiness becomes stale and recovery requires a process restart. Delayed results
remain protected by database deadline checks. Do not claim this is production HA.

Latest independent checks: 153 backend unit tests passed; 84 ML tests passed
with 15 explicitly skipped connected-worker tests (isolated services unavailable).
Ruff and backend ESLint passed. The skips do NOT count as Task 6 recovery proof.

Opt-in Compose service `scoring-worker` uses readonly model/gate mounts and is
not started by default. Its image build remains unverified after network errors.
No feedback learning, drift monitoring, automatic retraining or bank execution
was implemented.

## Resume Commands

From `services/ml`, with explicit isolated URLs in the environment:

```powershell
$env:TEST_DATABASE_URL='postgresql://sentinel:sentinel_test_only@127.0.0.1:25432/sentinel_task4_test'
$env:TEST_REDIS_URL='redis://:sentinel_test_only@127.0.0.1:26379/0'
$env:TEST_REDIS_RESTART='1'
.venv/Scripts/python.exe -m pytest tests/test_worker.py -q
```

Do not run integration cleanup/restarts or model evaluation concurrently with
benchmarks. After tests pass, invoke `python -m fraud_ml.worker_benchmark` with
the frozen package directory and manifest pin recorded in the Task 5 record,
first `--tps 1 --seconds 60`, then `--tps 5 --seconds 600`.
Keep every report, compare queue growth/failures/parity and report deadline misses.
Do not repeat the reserved test; its authorized one-time evaluation is complete.
