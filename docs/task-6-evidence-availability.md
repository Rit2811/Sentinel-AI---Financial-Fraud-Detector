# Task 6 peak investigation: evidence availability

Status on 2026-10-05: blocked before per-event attribution, performance changes,
backup restoration, diagnostic traffic and activation. Task 6 is incomplete.
The owner authorized a trace-supported fix and verified SSD migration if
applicable. The required original evidence and frozen package are absent from
this checkout; they must not be replaced with reconstructed or fixture inputs.

## Current environment, inspected read-only

- Windows physical disk: `KINGSTON OM8PDP3512B-AI1`, MediaType `SSD`, BusType
  `NVMe`, 512110190592 bytes. C: maps to disk 0 with that model.
- Docker context: `desktop-linux`; 12 CPUs, 7999795200 bytes memory.
- Docker data virtual disk exists at
  `C:\Users\ritwi\AppData\Local\Docker\wsl\disk\docker_data.vhdx` on C:.
- `sentinel-ai-postgres-data` is a local-driver volume at
  `/var/lib/docker/volumes/sentinel-ai-postgres-data/_data`.
  Read-only volume inspection reports ext4 on `/dev/sde` for both the data
  directory and `pg_wal`. WAL is a directory, not a symlink; `pg_tblspc` is empty.
- The volume contains PostgreSQL 16. Control metadata: cluster system identifier
  `7672632817307590690`, state `shut down`, latest checkpoint
  `Mon Sep 21 04:33:12 2026` as printed by `pg_controldata`.
- No containers are present after inspection. Read-only, network-disabled helpers
  were removed on exit; PostgreSQL itself was never started.

These observations differ from the recorded October 5 HDD machine, whose Docker
data disk was under `C:\Users\lenovo`, with four CPUs and 1.862GiB memory.
The present volume cannot be assumed to contain the recorded 16822-event,
migration-0011 application checkpoint. Its logical contents were not queried
or migrated. Both original named data volumes remain present.

An SSD-backed Docker disk exists here, but moving or starting this older volume
does not establish continuity with the failed application run. A verified source
backup and comparison evidence are prerequisites to using this as a target.

## Missing local inputs

The `services/ml/reports` and `services/ml/artifacts` directories are absent.
The private `.env.task6.local` file is absent. Specifically unavailable:

- Failed peak directory
  `services/ml/reports/task6-application-load/20261005T031524428781Z/`, including
  `report.json`, `event-stage-traces.json`, and worker/publisher/ingestion logs.
- Full normal directory
  `services/ml/reports/task6-application-load/20261005T031745589285Z/`.
- Frozen RF bundle and its separately authorized final-test report.
- Preserved runtime configuration, original run identity/configuration files,
  recovery dump and table-content/constraint comparison evidence.

The tracked records name the peak report hash
`f1a4e392aa621ff01bfd5bcc0d3fa927f4bbddc068f632e595cb70c62120614c`,
normal report hash
`13d4f2dd4e3f9750e5799f7ee9c9080d0b9123adf9c1830f7c7783a27dc5ddef`,
and source backup hash
`8be4543d3d8f6d5e97edce051b0830beff0e8579cee2bb595beea8047ab054db`.
Those are expected hashes, not checks newly passed here. A later source backup
must retain its own provenance and hashes.

## Historical comparison available from tracked documentation

All values below come from `storage-and-pipeline-correction.md`, not a new run.
The six expired event UUIDs and individual timings are unavailable here.

| Measurement | Same-run overall p95, ms | Expired-event p95 / max, ms |
| --- | ---: | ---: |
| Ingestion pool acquisition | 0.285 | not recorded / 0.115 |
| Initial COMMIT acknowledgement | 134.317 | 253.098 / 254.085 |
| Publication COMMIT acknowledgement | 141.804 | 227.398 / 245.004 |
| Accepted-to-assignment queue age | not recorded | 1140.611 / 1186.748 |
| History read | 7.658 | 12.941 / 14.278 |
| Feature calculation | 0.350 | 0.275 / 0.278 |
| Inference | 127.161 | 187.328 / not recorded (four reached inference) |
| Combined checkpoint/prediction scope | 279.870 | not recorded / 391.178 |
| Execution COMMIT acknowledgement | 116.149 | not recorded |

The documented publisher-lock p95 is 15.848ms. Database samples recorded
711 WALSync, 317 WALWrite-lock and six DataFileRead observations, with no
blocking backend sampled. These are run-level samples, not per-event wait
durations or proof that no transient blocking occurred. No publication rollback
was recorded in the final peak run. Stage and batch scopes overlap; adding them
would produce an invalid end-to-end timeline.

This supports investigating commit and serialized-queue tails, while pool wait
and feature arithmetic were small. It does not establish which delay dominated
each of the six expiries. No optimization was selected from these aggregates.

The historical load results remain 294 Scored / 6 Expired at 5 TPS for 60s,
and 600 / 0 at 1 TPS for 600s. One TPS is observed passing throughput on the
recorded HDD environment, not a measured maximum, a revised acceptance target,
or a result on this SSD machine. Current sustainable throughput is unmeasured.

## Timestamp limitations of the existing profiling code

Worker, publisher and ingestion stage records retain monotonic elapsed durations
but do not retain absolute start/end timestamps for each stage. Correlation uses
event UUIDs and shared batch IDs. The benchmark preserves some relative database
timestamps; several are explicitly pre-COMMIT witnesses. Database wait probing
aggregates wait categories, rather than retaining each event's blocking PID and
timestamped wait history. Deferred log emission is not the stage's timestamp.

After original artifacts are restored, the investigation must distinguish
observed timestamps, durations and unavailable boundaries. Exact unrecorded
stage timestamps or event-specific lock waits cannot be retroactively invented.
If the restored evidence lacks the necessary boundaries, a short instrumented
diagnostic on the verified target is necessary before selecting a fix.

## Checks and preserved scope

- Inspected current physical storage, Docker resources, volume metadata,
  filesystem/WAL placement and PostgreSQL control metadata.
- Confirmed required artifact directories and private environment file are absent.
- Confirmed report, artifact and private-environment paths are Git-ignored.
- Reviewed profiling/correlation code and its timestamp limitations.
- Reviewed Git status and diff; `git diff --check` passed.
- This investigation adds only this document. Existing Docker naming edits
  remain intact. No executable code, model, policy, deadline, durability setting,
  database row, schema, volume or runtime configuration was changed.
- No tests, benchmark, restoration, reserved-model evaluation, commit, push or
  activation were performed. Before/after timings cannot be reported without
  original inputs and a verified target. Task 7 was not started.

## Resume point

Recover original local evidence and frozen artifacts without sharing secrets in
chat. Verify report/package/backup hashes, then produce the six-event comparison
with explicit missing-timestamp markers. Establish source database continuity
before restoring into a new isolated SSD target; retain this existing volume and
the original source. Compare migration ledger, constraints and table-content
fingerprints, and align all components to the verified target. Run affected
recovery checks and short diagnostics. Full ten-minute 5 TPS and final 1 TPS
qualification follow only when the targeted delay is resolved. Activation stays
held until all agreed checks pass.
