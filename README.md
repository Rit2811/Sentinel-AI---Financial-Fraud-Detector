# Sentinel AI

Sentinel AI is a local prototype for receiving synthetic financial authorization events, moving them through a reliable event stream, and displaying operational activity in a web dashboard. The repository also contains a separate offline machine-learning workspace for fraud-model experiments.

This is not a production payment system. The offline ML ensemble is not connected to the live API, so the application does not currently return fraud scores or Allow/Review/Block decisions.

## What is implemented

- A Node.js and Express API for validated, idempotent authorization-event ingestion.
- PostgreSQL persistence for accepted events, rejected attempts, quarantined events, the transactional outbox, and processing receipts.
- Redis Streams publisher and consumer workers with retries, deduplication, idle-message recovery, and dead-letter handling.
- A React and Vite dashboard showing ingestion and stream-processing aggregates.
- An offline Python workspace for dataset checks, four baseline models, probability calibration, ensemble comparison, and threshold analysis.
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

The ML workspace runs separately and does not participate in this live flow yet.

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
- validation-only probability calibration and ensemble comparison;
- generation and verification of local model bundles.

Datasets, credentials, reports, and model artifacts are intentionally ignored by Git. See `services/ml/README.md` for commands and current evaluation boundaries.

## Current limitations

- No live ML inference or transaction fraud score.
- No approved production decision thresholds.
- No authentication or analyst case-management workflow.
- No concept-drift monitoring or automated retraining.
- No production deployment, compliance approval, or real card-data processing.

The next major integration step is to define a live feature pipeline and connect an approved model bundle to the event-processing flow.

## Data safety

Use only synthetic or tokenized authorization events. Do not commit raw financial datasets, real credentials, cardholder data, generated reports, or model artifacts.
