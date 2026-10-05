# Storage and Pipeline Correction - 2026-10-05

Task 5 remains COMPLETE. Task 6 remains INCOMPLETE. The approved deadline is
1000ms from server acceptance through durable decision storage. The two-second
diagnostic was not adopted. This correction achieved a full normal-load pass,
but the final short peak check still failed. General scoring activation is held.

## Physical Storage and Recovery

Windows reports one physical disk: ST1000DM003-1ER162, SATA HDD, approximately
1TB. No suitable SSD is available. C: and D: use the same physical drive.
Docker Desktop's virtual disk is
`C:\Users\lenovo\AppData\Local\Docker\wsl\disk\docker_data.vhdx`.
The named local-driver volume `sentinel-ai-postgres-data` resides at
`/var/lib/docker/volumes/sentinel-ai-postgres-data/_data` in that Linux ext4 disk.
PostgreSQL data_directory is `/var/lib/postgresql/data`; pg_wal resolves to
`/var/lib/postgresql/data/pg_wal` on the same filesystem. It is not a Windows
bind-mounted PGDATA directory. No storage move was performed.

Docker has four CPUs and 1.862GiB; Windows has approximately 8GiB RAM, with
684MiB free during setup. Docker, VS Code, browser and Windows background work
remained present. No resource/storage or durability setting was changed.
Earlier native fdatasync measurement on this application storage was about
35ms/flush. Current stage timings and WAL waits are stronger workload evidence
than an isolated tmpfs test; filesystem/host scheduling cannot be apportioned
precisely from wait samples alone.

All application writers were stopped for a consistent logical backup:
`services/ml/artifacts/database-recovery/20261003/sentinel-storage-pipeline-20261005.dump`.
SHA-256: `8be4543d3d8f6d5e97edce051b0830beff0e8579cee2bb595beea8047ab054db`.
It restored with exit-on-error into NEW `sentinel_storage_recovery_20261005`.
All 18 table counts/content SHA-256 fingerprints matched, including 15412
events/jobs/history/snapshots, 43091 scoring audit records, three reviews and
11 migrations. Both targets have 106 constraints. One restored category CHECK
has equivalent regrouping of three AND clauses; no constraint was removed.
After the new workloads, all original rows still match this restored backup.
Evidence: `services/ml/reports/task6-storage-pipeline/20261005-recovery-evidence.json`.
This is a logical recovery check on the existing instance, not an SSD target
or proof of independent physical disaster-recovery storage.

## Measured Corrections

- The old sequential HTTP generator caught up after slow requests. Its prior
  full two-second peak had 34 acceptance gaps below 100ms, minimum 44ms, and
  one second with 10 arrivals. The new bounded sender pool separates paced
  arrivals from HTTP completion, serializes same-card sends and enforces spacing
  at the actual send boundary. Actual send/acceptance records are retained.
- New-run recovery processed thousands of retained older stream messages,
  synchronously committing each outside-run audit separately. An initial paced
  baseline expired 150/150 while this recovery competed with scoring. This is
  startup evidence, not steady 5 TPS capacity. Audit writes now use one bounded
  transaction per delivery batch; Redis acknowledgements follow acknowledged
  COMMIT. Unique message IDs retain deduplication after uncertain COMMIT/ACK.
  Startup readiness waits for durable history and retained stream reconciliation.
- The steady baseline created 32 preparation commits for 150 events because
  it committed history before publication completed. The worker now waits for
  durable publication or expiry before the first checkpoint; it stops at an
  unready predecessor to preserve acceptance/per-card history order. Acceptance
  remains durable in PostgreSQL. Expired unpublished history and its terminal
  state commit together. Existing legacy pending/retry recovery remains supported.
- A premature 100ms Redis per-call cancellation inside an existing 200ms total
  publication budget caused a rolled-back publication and two-second ordered
  retry wait; ten transactions expired before inference. A single call now uses
  the remaining total 200ms budget. The shared fence, ordered publication,
  synchronous commit, rollback/CAS recovery and retry audit are preserved.
- Opt-in ingestion profiling records pool wait, statements and COMMIT ACK using
  safe event UUIDs; logging is deferred after release. Docker logs are configured
  non-blocking. The worker reuses a PostgreSQL session; Express/publisher reuse
  pools. Existing ordered-event, accepted-at and card/time indexes are present.
  History returns the 24-hour feature window but still counts per-card history
  for the durable sequence. Its measured cost is small; no speculative counter
  cache, new index, extra concurrency or model change was introduced.

## Actual Application Results

Held candidate run: `c5b2dab3-0330-4a32-9ba7-82c85d311b40`, immutable 1000ms.
Original application run/private configuration are preserved. The final worker
is `sha256:c0391f4e8af4aab4127ee889b7e3e4527d80679392e3c04a788f1756f94c1990`;
final API/publisher image is
`sha256:958c9efe4fa88f9213005b8cf4020585bfb131218c0fab46d41fada8a0c54fe2`.

| Test | Scored / Expired | Scored durable p50 / p95 / p99 / max, ms |
| --- | --- | --- |
| Steady baseline 5 TPS/30s | 144 / 6 | 524.190 / 851.222 / 946.273 / 984.764 |
| First corrected worker 5 TPS/30s | 139 / 11 | 409.663 / 712.088 / 905.411 / 972.772 |
| Final normal 1 TPS/60s | 60 / 0 | 352.897 / 513.781 / 551.480 / 558.133 |
| Final peak 5 TPS/60s | 294 / 6 | 428.480 / 783.330 / 942.922 / 983.161 |
| Final normal 1 TPS/600s | 600 / 0 | 395.912 / 549.259 / 685.000 / 951.522 |

All scored rows have exact offline/live parity; no expired transaction executed,
and no operational/observation failures occurred in the final runs. The full
normal pass proves observed normal capacity for this ten-minute workload, not
a maximum rate or a guarantee for future traffic. The final short peak failed
zero expiry (6/300, 2%); a full peak was not run after that failure. The earlier
two-second full peak is not substitute qualification.

Final peak actual offered rate was 4.975/s. Send intervals min/median/p95/max were
200.045/200.307/204.169/213.367ms. Server acceptance intervals were
92/200/221.1/311ms: one sub-100ms server gap, zero producer catch-up sends.
Normal full send intervals minimum 1000.047ms, median 1000.241ms and maximum
1031.880ms. Full normal parity was 600/600; no decision exceeded 1000ms.

At peak, sampled pending counts were 0,2,2,1,2,3 at 0..50s; sampled oldest age
reached 0.790s. Work drained afterward. These are transient tails, not evidence
of monotonically growing sustained backlog. Periodic sampling can miss short
spikes; the per-event assignment queue maximum was 1186.748ms. Normal periodic
samples had zero pending at their sampling phase; this is not continuous zero
queue occupancy.

## Remaining Bottleneck

Final peak p95 stage durations in milliseconds: ingestion pool wait 0.285,
ingestion event/audit statement 32.909, initial COMMIT ACK 134.317, publisher lock
15.848, Redis publication 12.938, publication COMMIT ACK 141.804, history query
7.658, feature calculation 0.350, inference 127.161, combined checkpoint/private
prediction COMMIT scope 279.870, and execution COMMIT ACK 116.149. Batch scopes
include other work and overlap; they cannot be added into a per-event budget.

For the six expired peak events, initial COMMIT p95/max was 253.098/254.085ms,
publication COMMIT 227.398/245.004ms, assignment queue 1140.611/1186.748ms,
history query 12.941/14.278ms, and feature calculation 0.275/0.278ms. Four reached
inference (p95 187.328ms); two expired before it. Pool wait maximum was 0.115ms.
The combined checkpoint/prediction scope maximum was 391.178ms.
No Redis publication rollback occurred in this final peak check.

Database active samples: WALSync 711, WALWrite lock 317, CPU/Running 514,
DataFileRead six. No blocking backend was sampled. PostgreSQL recorded 1105 WAL
syncs and 1119 WAL writes in the peak window. WAL timing counters were disabled;
zero time counters are not zero storage latency. Pool exhaustion and feature
arithmetic are not the measured bottleneck. Persistent-HDD durable-write and
queue tails, with inference/scheduling consuming the remaining budget, still
break the strict deadline. A software guarantee on this hardware is unsupported.

## Evidence and Hold

Reports under `services/ml/reports/task6-application-load/`:

- Startup baseline: `20261005T024837536711Z/report.json`.
- Steady baseline: `20261005T030118295827Z/report.json`.
- First correction: `20261005T030348910012Z/report.json`.
- Final short normal/peak: `20261005T031332472770Z/report.json` and
  `20261005T031524428781Z/report.json`.
- Full normal: `20261005T031745589285Z/report.json`.

Full normal report SHA-256:
`13d4f2dd4e3f9750e5799f7ee9c9080d0b9123adf9c1830f7c7783a27dc5ddef`.
Final peak report SHA-256:
`f1a4e392aa621ff01bfd5bcc0d3fa927f4bbddc068f632e595cb70c62120614c`.
Correlated event-stage traces include expired cases and ingestion profiles.

Checks passed: 64 worker/tool recovery tests plus the separate startup test;
25 final tool checks; 13 final publisher recovery/budget integration checks;
the final backend unit and lint results are recorded in the verification record.
An actual same-run restart completed reconciliation with identical fingerprints
for all six history/decision/action tables (1410 jobs/history/snapshots, 1243
predictions, 1237 results/executions). Original data preservation was rechecked.

Frozen manifest remains
`1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`;
sigmoid RF, Review 0.10, Block 0.25 and Task 5 evidence are unchanged. Reserved
model evaluation was not repeated. No feedback learning/retraining was added.

Candidate worker is stopped with restart disabled and workload_gate_failed.
Previous qualified API/publisher configuration is restored; scoring readiness
must remain HTTP 503. Application contains 16822 events/jobs, including 1410
new candidate jobs (1237 Scored, 173 Expired across retained diagnostics).
No database/volume was reset, no model/runtime pins promoted, and no Git push
or commit was made. Task 7 has not started.

## Concrete Next Step

Provide an SSD-backed Linux/Docker database target, or an engine whose virtual
disk is on SSD; no such target exists on this machine. Keep PGDATA/WAL on
suitable Linux storage. With writers stopped, restore a fresh verified backup,
compare ledger/constraints/content, retain the original database and rollback
configuration, then switch API/publisher/worker together with old writers held
off. Do not move C: to D: as an SSD substitute. Rerun short checks, then ten
minutes at both rates on that exact target before activation. An SSD is a
feasible hardware option, not guaranteed qualification.

A lower workload requirement is a separate owner decision; observed 1 TPS is
not approval to replace the 5 TPS target. No deadline increase is proposed.
After both performance gates pass, final public readiness, Pass/Block execution,
authorized Review resolution and final deployment restart checks still need
verification. Existing owner model/policy/test approvals must not be repeated.
