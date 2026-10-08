# Laptop Deployment Handoff

## Status

This is preparation, NOT a completed migration or activation approval.
The source remains the i5-6200U Windows PC, about 8 GB RAM and HDD. The owner
reports a Ryzen laptop, 16 GB RAM, 512 GB SSD, Windows and installed Docker.
Verify its exact CPU, available memory, Docker limits, Linux-container mode,
SSD-backed Docker storage and clocks on that machine before benchmarking.
Faster hardware may reduce local spikes; it does not remove remote DB round trips.

Task 5 remains complete. Task 6 remains incomplete after the valid-clock actual
normal precheck scored 24/30 with six expiries. See pipeline-qualification.md.
Keep the Mumbai database, exact frozen package, Review 0.10, Block 0.25,
1000 ms deadline and durability unchanged. Never repeat the reserved evaluation.

## Transfer Inventory

Use the same destination repository path to preserve private absolute paths:
`C:\Sentinel AI\Sentinel-AI---Financial-Fraud-Detector`.

The ignored `services/ml/artifacts/laptop-handoff/transfer-manifest.json` inventories
43 required private files with SHA-256 checksums, about 28.34 MB total: active
environment files, CA, frozen package, passing model gate evidence and original
runtime/load records. No connection strings or passwords were printed while
generating the inventory. Its checksums are NOT authorization to activate.

Transfer the CURRENT working tree, including its uncommitted work and untracked
implementation files, plus every inventoried file. A remote `ritwik` clone alone
does not contain these changes or ignored model/configuration files. Preserve Git
metadata separately if continuing on the same branch; main must remain unchanged.
Do not transfer `.venv`, `node_modules`, caches, raw CSVs or unrelated credential
files just to run scoring. Required replay diagnostics and the latest verified
database backup may be retained separately for handover/recovery.

Private environment files and any archives containing them must stay local and
Git-ignored. Use a trusted private transfer method, not a public link or commit.
Do not paste URI/password values into chat. Keep the original PC and its volumes
intact for rollback. The cloud DB already contains the application data: do NOT
restore its backup into Mumbai again or recreate that database on the laptop.

## Preserve Images And Redis

Do not run two publisher/worker deployments. The source application writers are
already stopped. Recheck they have not restarted before this procedure. From
the source repository root, archive the exact serving images rather than rebuilding:

```powershell
docker image save -o services/ml/artifacts/laptop-handoff/application-images.tar sentinel-ai-api:mumbai-ready sentinel-ai-scoring-worker:mumbai-parallel redis:7.2.5-alpine3.20
```

Redis has persistent stream/group state in volume `sentinel-ai-redis-data`.
Before exporting it, stop Redis cleanly AFTER all application writers are stopped:

```powershell
docker compose --env-file .env.application.local --env-file .env.supabase-mumbai.runtime.local -f infrastructure/compose.yaml -f infrastructure/compose.supabase.yaml --profile scoring stop api publisher scoring-worker consumer redis
docker run --rm --mount type=volume,source=sentinel-ai-redis-data,target=/data,readonly --mount "type=bind,source=$((Get-Location).Path)/services/ml/artifacts/laptop-handoff,target=/backup" redis:7.2.5-alpine3.20 tar -cf /backup/redis-data.tar -C /data .
Get-FileHash services/ml/artifacts/laptop-handoff/application-images.tar,services/ml/artifacts/laptop-handoff/redis-data.tar -Algorithm SHA256
```

Retain hashes privately and verify after transfer. Never flush streams, reset
Docker storage, delete the source volume or copy an actively written AOF directory.
See [Docker volume backup/restore](https://docs.docker.com/engine/storage/volumes/).
Do not run the source export commands on the laptop against an unrelated volume.

## Destination Checks

1. Verify working-tree contents and all inventoried file hashes at the expected
   path. Check ignore rules before staging anything. Keep writers stopped.
2. Load `application-images.tar` with `docker image load -i ...`; verify IDs:
   worker `sha256:b21861472e2695ed3d3b9019a1a9fe8e81b1fd07ca2216a794a592ccedc468db`,
   API/publisher `sha256:692b5d9e6657d32ace5aa4e70286105b0db7ef2f755fc78b9975e14970559361`.
3. Restore Redis ONLY into a confirmed NEW, empty laptop volume before starting
   Redis. If `sentinel-ai-redis-data` already exists with data, stop and inspect;
   never overwrite it. Keep AOF files, stream IDs, groups and pending deliveries.
4. Inspect Docker effective configuration without displaying secrets. Use both
   `.env.application.local` and `.env.supabase-mumbai.runtime.local` with
   `infrastructure/compose.yaml` and `infrastructure/compose.supabase.yaml`.
   Hold stays on; run remains `c5b2dab3-0330-4a32-9ba7-82c85d311b40`, target pin
   `070281d038846b47c4ee2d30ab19b04eeef69fdb59c1f65f66c0873c995574b2`.
5. Check Windows NTP and Docker/DB offsets, authenticated verified TLS, migration
   ledger 12, fsync/synchronous_commit on and fresh recovered worker health.
   Do not start an unnecessary local application PostgreSQL database. Start only
   selected cloud services after destination/Redis verification, using `--no-deps`
   to avoid the base configuration's local PostgreSQL dependency.
6. Recreate host tooling with Python 3.12 and locked dependencies, not the old
   PC's virtual environment. Check existing installations first. If available,
   `uv sync --locked --extra worker --group dev` in `services/ml` prepares tools.
   Do not alter a system-wide memory cap or install missing system software silently.
7. Verify restored Redis identity and durable DB history before any traffic.
   Wait for history reconciliation and initialized scorer readiness; activation
   remains held even when the diagnostic worker becomes ready.

Do not blindly run the general `verify.ps1` against the cloud: its migration and
fixture smoke operations have separate local-target assumptions. Use explicitly
isolated test services for destructive fixture verification.

## Acceptance

Begin with paced 30-second 1 TPS, then 5 TPS diagnostics only if promising.
Use the existing `fraud_ml.application_benchmark` with the candidate run and
external target pin above. Keep stage traces, expired events, clock checks,
actual arrival intervals, queues and offline/live parity. A better laptop is not
proof that sustained capacity has passed.

Only zero-expiry, correctness-passing prechecks justify `--qualification`
600-second tests at BOTH 1 TPS and 5 TPS on this actual laptop configuration.
Then bind exact deployment evidence, verify actions/manual review/Redis/same-run
restart/readiness and follow the existing activation gate. No deadline increases,
threshold tuning, retraining or reserved-test evaluation. If it fails, report
measured remaining costs instead of declaring Task 6 complete.
