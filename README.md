# Sentinel AI

Sentinel AI is a local prototype for receiving synthetic financial authorization events, moving them through a reliable event stream, and displaying operational activity in a web dashboard. The repository also contains a separate offline machine-learning workspace for fraud-model experiments.

The active dataset is Sparkov-derived `kartik2112/fraud-detection/versions/1`. This is not a production payment system. Task 5's frozen Random Forest passed its authorized final test. Task 6's connected worker is implemented, but application activation and full workload acceptance remain pending.

The application database is now migrated to Supabase Mumbai, with source databases
preserved and a verified restore. Activation is still blocked by workload gates;
writers are paused after renewed clock drift. See [current deployment evidence](docs/mumbai-deployment.md).

## What is implemented

- A Node.js and Express API for validated, idempotent authorization-event ingestion.
- PostgreSQL persistence for accepted events, rejected attempts, quarantined events, the transactional outbox, and processing receipts.
- Redis Streams publisher and consumer workers with retries, deduplication, idle-message recovery, and dead-letter handling.
- A React and Vite dashboard showing ingestion and stream-processing aggregates.
- An offline Python workspace for pinned Sparkov source auditing, shared point-in-time features and four chronological baseline models.
- An approved frozen, sigmoid-calibrated Random Forest, a separate development-only four-model ensemble, and a prepared durable Python scoring worker.
- Immutable scoring/history evidence, separate simulated actions, protected result retrieval, and authorized idempotent human review resolution.
- Docker Compose, migrations, automated tests, formatting, linting, and verification scripts.

## Repository structure

- `backend/` - Express API, database migrations, stream workers, and backend tests.
- `frontend/` - React dashboard, styles, API adapter, and frontend tests.
- `services/ml/` - offline Python model-development and evaluation code.
- `infrastructure/` - Docker Compose configuration.
- `scripts/` - setup, verification, and cleanup scripts for Windows and Bash.
- `docs/` - checked-in technical documentation.
- `data/` - data-handling guidance; datasets are kept out of Git.
- `packages/` and `tests/` - placeholders for future shared code and system-level tests.

## Local architecture

Docker Compose runs six processes:

1. `postgres` stores events, audit records, outbox entries, and dashboard data.
2. `redis` provides the local event stream.
3. `api` validates and stores authorization events and serves dashboard data.
4. `publisher` moves committed outbox entries from PostgreSQL to Redis Streams.
5. `consumer` processes stream messages and records deduplicated receipts.
6. `web` serves the compiled dashboard through Nginx and proxies API requests.

The optional `scoring-worker` Compose profile adds Python inference. Application activation is gated by the frozen package, passing model evaluation and zero-expiry workload evidence; ordinary `make up` does not authorize scoring. See `docs/scoring-verification.md` for the current deployment status.

Runtime names describe their purpose: API images use `local`/`supabase`, worker
images use `replay`/`supabase`, and private settings use `.env.application.local`.
See `docs/component-naming.md` for the naming map and protected rollback aliases.

## Requirements

- Docker Desktop with Docker Compose
- Node.js 22 and npm
- Python 3.12 and `uv`
- GNU Make
- Git

## Run locally

```bash
make bootstrap
make up
```

Local endpoints:

| Component | Address |
| --- | --- |
| Dashboard | `http://127.0.0.1:15173` |
| API health | `http://127.0.0.1:18000/health` |
| API readiness | `http://127.0.0.1:18000/ready` |
| API documentation | `http://127.0.0.1:18000/docs` |
| PostgreSQL | `127.0.0.1:15432` |
| Redis | `127.0.0.1:16379` |

Useful commands:

```bash
make ps       # show service status
make logs     # show recent logs
make verify   # run repository checks and integration tests
make down     # stop containers and preserve data volumes
make clean    # remove generated local files and preserve data volumes
```

Copy `.env.example` to `.env` only when local overrides are needed. The default configuration uses local placeholder credentials and binds published ports to `127.0.0.1`.

## ML workspace

The ML code is under `services/ml/`. It currently supports:

- dataset auditing and chronological splitting;
- Logistic Regression, Linear SVM, Random Forest, and KNN baselines;
- chronological calibration, measured model/policy comparisons and one completed owner-authorized frozen-RF reserved-test evaluation;
- historical/replay feature parity, without raw card numbers or scoring labels.

Datasets, credentials, reports, and model artifacts are intentionally ignored by Git. See `services/ml/README.md` for commands and current evaluation boundaries.

## Current limitations

- Application scoring activation remains blocked until Task 6's workload gates pass; the worker/result/action path exists and is tested in isolation.
- RF thresholds are approved for this local synthetic prototype, not production banking traffic. The four-model ensemble is not selected for serving.
- Result/review APIs have local bearer-token authorization; full user authentication, role-based access and analyst case-management UI are not implemented.
- The existing dashboard reports ingestion/stream activity, not a complete scoring/review workflow.
- No concept-drift monitoring or automated retraining.
- No production deployment, compliance approval, or real card-data processing.

Task 4 gates passed on 2026-10-01. Task 5 passed on 2026-10-02: approved sigmoid RF (Review 0.10, Block 0.25), frozen package, clean-load parity and one authorized reserved-test evaluation without tuning. The actual application database has migrations 0001-0009 with verified isolated backup restoration. Task 6 still needs zero-expiry peak-load evidence followed by actual application activation/action/restart verification. See `docs/task-5-final-test-record.md` and `docs/scoring-verification.md` for current evidence; earlier planning documents are historical checkpoints. Task 7 is not started or precisely specified by the supplied Task 5/6 guides.

## Data safety

Use only synthetic or tokenized authorization events. Do not commit raw financial datasets, real credentials, cardholder data, generated reports, or model artifacts.
