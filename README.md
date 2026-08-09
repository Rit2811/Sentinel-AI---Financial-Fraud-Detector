# Sentinel AI — Adaptive Financial Fraud Detection

Sentinel AI is planned as a real-time, self-adapting platform for detecting fraudulent financial transactions. Its intended architecture combines streaming ingestion, online feature engineering, adaptive class-imbalance handling, heterogeneous ensemble scoring, concept-drift monitoring, incremental updates, and configurable allow/review/block decisions.

## Current phase

Task 2 provides a local operational shell: FastAPI liveness/readiness, a neutral React/TypeScript/Vite page, PostgreSQL and Redis health, and an isolated Docker Compose stack. It contains no transaction processing, business schema, stream, fraud logic, dataset pipeline, model, ML, or AI capability.

## Repository map

- `backend/` — Python 3.12/FastAPI operational API shell and tests.
- `frontend/` — Node 22/React/TypeScript/Vite neutral web shell and tests.
- `packages/` — future shared contracts and reusable packages.
- `infrastructure/` — isolated four-service local Compose stack.
- `scripts/` — unified Task 2 verification implementation.
- `tests/` — future cross-component and acceptance tests.
- `data/` — data-handling policy only; raw/local datasets are not committed.
- `docs/` — repository documentation and authoritative planning inputs.

Read `AGENTS.md` before making changes and consult `docs/planning/` before architectural work.

## Prerequisites

Install Git, Docker Desktop with Compose, Python 3.12 managed by `uv`, Node.js 22 with npm, GNU Make, Bash, and curl.

## Local workflow

The default ports are deliberately separate from other local projects:

| Service | Local URL/port |
| --- | --- |
| Web | `http://127.0.0.1:15173` |
| API health | `http://127.0.0.1:18000/health` |
| API readiness | `http://127.0.0.1:18000/ready` |
| PostgreSQL | `127.0.0.1:15432` |
| Redis | `127.0.0.1:16379` |

Copy `.env.example` to an ignored `.env` only when local overrides are needed. The checked-in defaults are safe placeholders and allow startup without that file.

```bash
make bootstrap  # install exactly locked host dependencies
make up         # build and start four healthy services
make ps         # show service and health state
make logs       # show the most recent bounded logs
make verify     # run all Task 2 checks and smoke/failure/restart tests
make down       # stop containers; preserve volumes
make clean      # remove generated caches/builds; preserve volumes
```

Compose uses the fixed project name `sentinel-ai`, dedicated named volumes, a dedicated project network, and localhost-only ports. It does not connect to or operate on UniHub resources.

## Data and secrets

Never commit financial datasets, `creditcard.csv`, real environment files, credentials, model artifacts, logs, caches, or generated output. `.env.example` is documentation only and must never contain real values.

## Development status

Local toolchain and container foundation: Task 2 implementation. The transaction event contract and ingestion boundary has not started.
