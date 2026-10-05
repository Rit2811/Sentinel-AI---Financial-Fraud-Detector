# Two-Second Diagnostic Trial

Later one-second storage/pipeline evidence is recorded in
[the correction record](storage-and-pipeline-correction.md). Normal 1 TPS/600s
passed 600/600; final peak 5 TPS/60s still failed 294/300. The two-second
trial was not adopted. Current deployment state is in the newer record;
the results below remain retained historical diagnostic evidence.

## Authorization and Holds

Owner authorized this trial on 2026-10-05 (Asia/Calcutta), not adoption of a
revised requirement or activation. The original one-second requirement remains
unmet. Task 5 stays complete; Task 6 stays incomplete while workload evidence and
owner review are pending. No reserved-model evaluation is repeated.

Frozen manifest remains
`1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`.
RF sigmoid calibration, Review 0.10 and Block 0.25 are unchanged. PostgreSQL
fsync/synchronous commits, canonical-ID duplicate protection, point-in-time
features and no execution after expiry remain unchanged.

## Trial Isolation

Migration 0011 allows a two-second deadline only on a new immutable
`diagnostic_only=true` run. Normal runs retain exactly 1000ms. Existing jobs and
the original application run are not edited. Diagnostic job deadlines must match
their run. Restart cannot change the recorded deadline or diagnostic flag.

`infrastructure/compose.deadline-trial.yaml` is an explicit overlay on the existing
private configuration and original application volumes. It uses separately tagged
images, an explicit new run ID and profiling. Private environment/runtime metadata
are not promoted or overwritten. `/ready/scoring` returns 503 for diagnostic runs
even when the worker is internally ready to process controlled trial traffic.
Diagnostic reports remain ineligible for the activation loader.

## Measurement

Short actual-application checks precede any full workloads. If promising, use
600 seconds at both 1 and 5 TPS with the deadline fixed at 2000ms. No code,
migration, image or host/Docker resource changes occur during timed workloads.
Isolated tests establish correctness, not equivalent storage performance.

Worker/publisher logs contain safe UUID-correlated stage durations and CPU time.
Batch timings are shared scopes, not additive per-event costs. Reports retain
queue samples, p50/p95/p99/max latency, WAL counters, bounded database-wait
sampling and blocking observations. Event traces correlate expired outcomes with
available queue, publication, feature, inference and write scopes. Missing stage
records are never represented as zero. Most database timestamps precede COMMIT;
the original postcommit prediction witness and measured COMMIT acknowledgements
must not be confused with those timestamps. WAL time counters are not meaningful
when `track_wal_io_timing=off`; its setting is reported, not silently changed.

## Recovery

Before-trial populated backup:
`services/ml/artifacts/database-recovery/20261003/sentinel-before-two-second-trial-20261005.dump`.
SHA-256: `e54afe9afeecc00973b64bbb32657c43fec605db358d7363a0977fb0436c4d8a`.
Existing verified backups remain retained. Never reset volumes or restore over
the application. Recovery uses a new isolated target, ledger/content comparison
and explicit review before any application target switch.

Before the combined-commit worker trial, another populated application backup
was taken at
`services/ml/artifacts/database-recovery/20261003/sentinel-after-two-second-trial-20261005.dump`.
Its SHA-256 is
`02d1d7cdc1ceaae3a4e8208f0f8a9341629d9b3168c09d446f5fd8d1251aff70`.
No backup was restored over the live application during these tests.

After measurement, stop the diagnostic worker and restore the original API/run
configuration and qualified image tags. Keep activation held pending review.

## Latest Combined-Commit Diagnostic (2026-10-05)

After the first short trial failed, an isolated worker change combined the first
history/feature/prediction checkpoint into one synchronous PostgreSQL transaction.
The frozen model, thresholds, feature implementation, publisher durability and
two-second diagnostic deadline did not change. A failed or uncertain COMMIT rolls
back the combined checkpoint and canonical-ID replay remains deduplicated.
Focused ML/recovery checks passed 85/85, including deferred-COMMIT failure,
clean replay and Redis restart. The new worker image is
`sha256:4e08e8982fdd0851880315fc7fb9fece6083085315a31c3405ee91600fa1ca8f`.
The separately retained API/publisher trial image is
`sha256:6ae9d39fd28bc7168e56660687396b5e1cae960e3e408454ee59adbe80fe2a85`.

An isolated tmpfs 5 TPS/30s check scored 148/150 and expired two, with exact
scored parity and no late execution. The matched persistent-application checks
then scored 30/30 at 1 TPS/30s (maximum 1418.852ms) and 300/300 at 5 TPS/60s
(maximum 1743.682ms), both with zero expiry. These short checks justified the
full tests but were not activation proof.

| Actual application diagnostic | Scored | Expired | Scored durable p50 / p95 / p99 / max, ms | Queue max | Scored parity | Invalid/late execution |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 TPS / 600s | 600 | 0 | 348.407 / 551.532 / 805.773 / 1452.532 | 1 | 600/600 | 0 |
| 5 TPS / 600s | 2927 | 73 | 520.782 / 1124.671 / 1706.231 / 1999.129 | 11 | 2927/2927 | 0 |

Both full runs accepted every scheduled transaction, had zero failed/observation-
timeout records and no operational or database probe errors. The normal run's
two scored decisions above 1000ms and the peak run's 196 show the original
one-second requirement is still unmet. Peak scored throughput was 4.876/s,
not a proven sustainable zero-expiry capacity; 73/3000 (2.43%) expired at the
two-second deadline. The peak queue sampled one pending item at start and three
at 590s, with maximum 11 and maximum oldest age 2.235s. The queue did not grow
monotonically, but transient waiting caused deadline misses.

Peak assignment-queue wait p95 was 857.880ms and maximum 2414.448ms. Of 73
expired transactions, 64 had no inference start, 47 had publication precommit
witness later than 1000ms, and 20 had feature-snapshot witness later than
1000ms. Available peak stage profiles: publisher lock p95 15.578ms, Redis
publication p95 14.576ms, publisher batch COMMIT acknowledgement p95 127.794ms,
feature calculation p95 0.748ms, inference p95 135.585ms, and combined worker
checkpoint/prediction COMMIT acknowledgement p95 265.086ms. Profiles may drop
records and batch scopes overlap; these timings cannot be summed into a single
event budget. Database active wait samples included WALSync 7659, WALWrite lock
3473 and CPU/Running 5376, with no sampled blocking backend. PostgreSQL counted
11219 WAL syncs and 11324 WAL writes during peak; WAL time tracking was off.
This implicates queueing and persistent-HDD durable-write tails, not feature
arithmetic alone. C: and D: are partitions of the same physical SATA HDD;
moving the volume between them would not establish an SSD test.

Full reports and correlated safe-ID traces:

- `services/ml/reports/task6-application-load/20261004T193910706267Z/report.json`
- `services/ml/reports/task6-application-load/20261004T195106458639Z/report.json`
- Short application checks: `20261004T193528560973Z` and
  `20261004T193644151033Z` under the same report directory.
- Isolated check: `services/ml/reports/task6-worker/20261004T193020011284Z/report.json`.

The full normal and peak report SHA-256 values, in that order, are
`28785f3c8e3f6e4a2a8327bfe2192bd213c93a89a6fdd4ef4b35757cf3be0626`
and `b67407892c4a4cbb2e4a456cd5474666d13986481aa7a52c9c909d3732ac6da7`.

The full normal workload passed, but the full peak workload failed the agreed
zero-expiry condition. Do not adopt the two-second requirement or activate this
diagnostic package. No further deadline increase, model tuning, durability
change or reserved-model evaluation was performed.

## Earlier Trial Results

Diagnostic run: `9b8fc17d-dc22-49d8-8668-2cdc0afe9414`. The original run
`e7d43b39-fd79-4368-818d-899c2415434a` still has 1000ms and
`diagnostic_only=false`; its 11152 pretrial events and jobs were preserved.
Application ledger 0001-0011 was applied with the repository runner after a
fresh backup. No application volume was reset or replaced.

| Actual application load | Scored | Expired | Scored p50 / p95 / p99 / maximum, ms | Queue maximum | Parity | Late execution |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 TPS / 30s | 30 | 0 | 413.508 / 1254.822 / 1613.413 / 1678.668 | 1 | 30/30 | 0 |
| 5 TPS / 60s | 280 | 20 | 710.944 / 1509.824 / 1716.983 / 1917.254 | 11 | 280/280 | 0 |

Both offered the requested rate, accepted all generated requests and reported no
operational errors or database probe errors. The normal check had three scored
decisions above 1000ms. The peak check had 63 above 1000ms. These confirm the
original one-second requirement remains unmet. Report files:

- `services/ml/reports/task6-application-load/20261004T190152194775Z/report.json`
- `services/ml/reports/task6-application-load/20261004T190345824030Z/report.json`

Each report directory also has `worker-profile.log`, `publisher-profile.log` and
`event-stage-traces.json`. Safe event IDs associate available stages with final
outcomes. A missing stage record means missing instrumentation, never zero time.
The resource snapshot is
`services/ml/reports/task6-deadline-trial/20261005-resource-baseline.json`.

At 5 TPS, sampled pending work grew 1, 5, 2, 11, 3, 2 at 0, 10, 20, 30, 40,
50 seconds; the oldest pending item reached 2.262s at 30 seconds. Among the
20 expired events, assignment queue time reached 2.155s (p95 1.985s), with seven
above one second and one above two seconds. Three were published after their
deadline. Three had a private prediction; none had a public result/execution.
Available expired-event stage durations include feature calculation p95 0.350ms,
inference p95 192.393ms, publisher COMMIT acknowledgement p95 167.547ms,
assignment batch COMMIT acknowledgement p95 474.445ms and prediction COMMIT
acknowledgement p95 178.805ms. Batch scopes overlap individual scopes and are
not additive. At 1 TPS, queue maximum was one but p95 scored latency still
exceeded one second.

Database active samples at peak: WALSync 784, WALWrite lock 477, WALWrite 6,
CPU/Running 505, DataFileRead 40. No blocking backend was observed in sampled
`pg_blocking_pids()`. PostgreSQL recorded 1108 WAL syncs and 1122 WAL writes
during that trial; `track_io_timing=off` and `track_wal_io_timing=off`, so their
time counters are unavailable. This supports a measured queue and durable-write
tail bottleneck on the persistent application volume. Samples and pre-COMMIT
witnesses cannot apportion every delayed event to storage alone. The isolated
fixture uses tmpfs, unlike the application's Docker volume backed by the
C-drive SATA HDD. Before traffic, Docker reported 4 CPUs and 1.862GiB, Windows
had 8GiB total and about 1.03GiB free. VS Code, browser, Defender and Docker
remained in place; no resource, storage or durability setting was changed.

Backend integration: 46/46 passed on a serial rerun; backend unit: 155/155.
ML serial suite: 83/84 passed; one original one-second process-death fixture
expired under load. Its focused rerun passed 5/5, including the two-second
deadline, expiry/no-execution, immutable run configuration and process-death
recovery cases. All 17 affected benchmark/tool tests passed. The earlier
overlapping backend/ML integration attempts interfered in their shared isolated
database and are not counted as evidence. No reserved-model evaluation ran;
frozen manifest and final-test report SHA-256 pins remained unchanged.

The short 5 TPS diagnostic failed zero expiry, so the conditional ten-minute
1 TPS and 5 TPS trials were not run. The trial does not support adopting a
two-second requirement or activating scoring. The original one-second requirement
remains unmet. No longer deadline or speculative optimization was applied.

## Deployment Hold

After the full tests, the diagnostic worker was stopped, then the publisher was
stopped, and both API/publisher containers were recreated from the retained
qualified backend image
`sha256:b6d0d7e396c067a434312905cbb7278c26974bcd8ecd7793257da8f59f5f9c6e`.
Both image IDs were verified. `/ready/scoring` returned HTTP 503. The original
run remains non-diagnostic at 1000ms; the new run remains diagnostic at 2000ms.
The application has 15412 events/jobs and all 11 migrations. New diagnostic
jobs total 4167 Scored and 93 Expired (the 20 earlier plus 73 full-peak misses);
the original 11152 jobs were not edited. The private environment SHA-256 remains
`417f2b96755f5e41fcec8034191fe46d7fd37d6e6b6bd778c0cc9b3170f2538a`.
No database volume was reset or restored over the application. Scoring activation
remains blocked and the diagnostic worker is stopped.
