# Teammate Local Setup

Each teammate runs an independent local PostgreSQL/Redis application. Their Git
checkout does not connect to the owner's database, Supabase or laptop. GitHub
pushes deliver code; they do not deploy a shared server or transfer private files.
Use a branch containing this setup kit; these instructions are not available in
older checkouts until the owner publishes the current code changes.

## Requirements

- Git and Docker Desktop with Compose v2 and **Linux containers**. On Windows,
  enable its WSL2 backend and hardware virtualization; use SSD-backed Docker data.
- These prebuilt application images target Linux **amd64**. ARM machines need
  compatible builds or emulation and their own checks.
- The measured laptop has 16 GB RAM; six services sampled about 629 MiB together,
  excluding Docker/WSL, development tools and load generation. This is an observed
  sample, not a minimum or a performance guarantee for another computer.
- Internet for cloning/pulling/building, or privately supplied images for offline
  use. No Supabase account or remote PostgreSQL URI is needed for this setup.
- Host Node 22/npm and Python 3.12/uv are optional for editing/testing outside
  Docker. Docker contains the application runtimes; GNU Make is not required here.

Full scoring additionally needs a **trusted private runtime package** from the
owner. Do not retrain or run reserved-dataset evaluation to replace missing files.

## Clone and Create Your Own Configuration

From Windows PowerShell:

```powershell
git clone --branch ritwik https://github.com/Rit2811/Sentinel-AI---Financial-Fraud-Detector.git
cd Sentinel-AI---Financial-Fraud-Detector
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/new-teammate-env.ps1 -ReviewerId your_name
```

The helper writes ignored `.env.teammate.local` with four different random
64-character secrets, a fresh UUID run, your reviewer identity and your actual
checkout path. Existing credential files are never overwritten. No secret values
are printed. Use `infrastructure/teammate.env.example` as the non-secret reference.

The four secrets are `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `RESULT_API_TOKEN`
and `REVIEW_API_TOKEN`. They are generated locally, not obtained from Supabase.
Each authorized reviewer uses their own identity and review token. URIs are
derived by Compose; keep database passwords and API tokens out of React/Git/chat.

On Linux/macOS, copy the reference template to `.env.teammate.local`, generate
four independent 32-byte random secrets, fill a new UUID run/reviewer/path, and
use the equivalent explicit Compose commands below. Do not copy the owner's env.

## Full Scoring: Private Inputs

The owner must transfer only the required approved files through a trusted
private channel. Git intentionally excludes them:

1. **Complete frozen bundle**, with original bytes, under
   `services/ml/artifacts/frozen/random-forest/20261002T075558874195Z/`.
2. **Passing gate `report.json`**, under
   `services/ml/reports/final-test/1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696/`.
3. Optionally, the **three approved application images** in a Docker archive.
   This avoids rebuilding the verified serving runtime. Public PG17/Redis images
   can be pulled separately. No source datasets, credentials, owner DB/Redis
   backups, runtime approval metadata or personal task docs are needed.

Expected SHA-256 pins:

| Item | Expected value |
| --- | --- |
| Bundle `manifest.json` | `1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696` |
| Gate `report.json` | `abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2` |
| API image ID | `sha256:692b5d9e6657d32ace5aa4e70286105b0db7ef2f755fc78b9975e14970559361` |
| Scoring image ID | `sha256:2eb38fae2ef49430af0088743d78e60e8845cac4acdb9d199457f1b458500d23` |
| Dashboard image ID | `sha256:fcbaa797517ceb88a9c1548a310e1b2bcd78a6e91d89c9f88a4a31dcc06095d5` |

After loading a privately supplied archive, use image IDs to assign the dedicated
teammate tags. The names in the archive may differ; IDs must match:

```powershell
docker load -i 'D:\Private Transfer\sentinel-approved-images.tar'
docker tag sha256:692b5d9e6657d32ace5aa4e70286105b0db7ef2f755fc78b9975e14970559361 sentinel-ai-api:development
docker tag sha256:2eb38fae2ef49430af0088743d78e60e8845cac4acdb9d199457f1b458500d23 sentinel-ai-scoring-worker:random-forest-development
docker tag sha256:fcbaa797517ceb88a9c1548a310e1b2bcd78a6e91d89c9f88a4a31dcc06095d5 sentinel-ai-dashboard:development
```

The owner can prepare that image archive locally with `docker image save -o
<private-path>/sentinel-approved-images.tar` followed by the three image IDs above.
Share its SHA-256 through the trusted transfer channel and verify it before load.
Never transfer Docker volumes or the owner's filled env for independent development.

Alternative: build from this checkout with the supplied locked dependencies:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 build -Scoring
```

A new build is a different deployment image and does not inherit someone else's
performance qualification. The worker still requires exact trusted model/package,
runtime, gate and executing feature/scorer bytes. Failure is an error to investigate,
not permission to train, bypass hashes or invent a probability.

## Start, Check and Stop

Full scoring, after the private files/images are present:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 start -Scoring
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 health
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 status
```

The helper uses project `sentinel-team`, new persistent volumes
`sentinel-team-postgres-data` / `sentinel-team-redis-data`, and the three Compose
files `compose.yaml`, `compose.postgres-local.yaml`, `compose.teammate.yaml`.
It starts PG/Redis, waits for API forward migrations, starts publisher/dashboard/
scorer, and checks scorer initialization/reconciliation before ingestion.
The optional proof consumer remains off: **six services**, not 17.
The database is fresh and initially empty; each teammate sees their own events.

Container names follow Compose's `<project>-<service>-<instance>` convention:
`sentinel-team-api-1`, `sentinel-team-publisher-1`,
`sentinel-team-scoring-worker-1`, `sentinel-team-dashboard-1`,
`sentinel-team-postgres-1`, `sentinel-team-redis-1`.
Repositories name the component; tags distinguish application/development use
or the Random Forest scorer. Official database/Redis images retain version tags.

| Endpoint | Address |
| --- | --- |
| Dashboard | `http://localhost:15173` |
| Infrastructure readiness | `http://localhost:18000/ready` |
| Scoring readiness | `http://localhost:18000/ready/scoring` |
| OpenAPI UI | `http://localhost:18000/docs` |

The independent development configuration keeps `SCORING_ACTIVATION_HOLD=1`.
Infrastructure/dashboard should return 200; scoring readiness correctly remains
503 while held. The initialized worker can be used for controlled synthetic
development checks. General activation and workload acceptance must be verified
on that exact machine/run/images/settings before clearing the hold; another
computer's successful qualification does not establish this machine's throughput.
The developer helper deliberately rejects hold0 rather than silently activating.

Result retrieval uses the private result token; review resolution uses the separate
review token and preserves the original model decision. The current dashboard
shows ingestion/stream activity, not a complete scoring/review case-management UI.

For API/dashboard development without private model files:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 start
```

This runs five services and has no ML scoring worker; unavailable scoring does
not become Pass. Do not describe this mode as full fraud scoring.

Stop either mode, preserving data:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/teammate.ps1 stop
```

Do not use `down -v`, flush Redis, reset migrations or run the owner's laptop
provisioning/activation scripts. If ports are occupied, change only the four host
port values in your env; the internal `postgres:5432/sentinel` identity remains
unchanged. Startup should not be run alongside the owner's stack on the same host
using its ports; use separate ports if developing a separate fixture there.

On other shells, the equivalent Compose prefix is:

```bash
docker compose -p sentinel-team --env-file .env.teammate.local \
  -f infrastructure/compose.yaml -f infrastructure/compose.postgres-local.yaml \
  -f infrastructure/compose.teammate.yaml --profile scoring
```

Append commands such as `build api dashboard scoring-worker`, `up -d --no-deps
--no-build --wait postgres redis`, then `up -d --no-deps --no-build --wait api`,
then `up -d --no-deps --no-build --wait publisher dashboard scoring-worker`. Verify
scorer health before sending events. Use `stop` to preserve volumes.

## Code Changes and Sharing

Commit only source, safe templates and public documentation. Keep filled env,
model binaries, datasets, gate reports, local evidence and personal planning docs
private. After code updates, rebuild only the relevant teammate images and restart
your independent deployment while retaining volumes. Qualification needs a new
review when serving behavior or deployment settings change.

These localhost bindings do not publish a server for teammates to share. A shared
host needs its own deployment, network/authentication configuration and approval;
a GitHub push does not do that automatically.
