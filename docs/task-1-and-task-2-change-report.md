# Sentinel AI — Task 1 and Task 2 Change Report

**Prepared for:** Ritwik Dhull  
**Date:** 9 August 2026

## Executive summary

Task 1 established a safe, documented monorepo foundation. Task 2 converted it into a reproducible local shell with exactly four isolated services: FastAPI, React/TypeScript, PostgreSQL, and Redis. Transaction processing, business schemas, streams, fraud scoring, datasets, ML, and AI remain deferred.

## Task 1 — Repository foundation

- Added `AGENTS.md` with durable scope, safety, review, manual-blocker, verification, and handoff rules.
- Added the root project README and documentation indexes.
- Collected the patent and controlled execution guides under `docs/planning/`.
- Created documented boundaries for `backend`, `frontend`, `packages`, `infrastructure`, `scripts`, `tests`, `data`, and `docs`.
- Added placeholder-only `.env.example`.
- Added `.gitignore` coverage for environment files, credentials, raw/derived data, model artifacts, dependencies, caches, logs, coverage, builds, IDE files, and OS files.
- Verified representative sensitive/generated paths are excluded from Git.

**Outcome:** an organized, agent-ready repository without application, database, fraud, ML, or AI implementation.

## Task 2 — Local toolchain and container foundation

### Backend

- Added a Python 3.12 project managed and locked with `uv`.
- Added a minimal FastAPI service.
- Added `GET /health` for process liveness.
- Added `GET /ready` for read-only PostgreSQL and Redis checks.
- Readiness uses short timeouts and HTTP 503 when either dependency is unavailable.
- Added Ruff, strict mypy, pytest, five backend tests, and a versioned Dockerfile.

### Frontend

- Added a Node.js 22, React, TypeScript, and Vite project with an exact npm lockfile.
- Added a neutral operational shell with no product workflow.
- Added Prettier, ESLint, TypeScript checking, Vitest, a test, production build, and versioned Dockerfile.

### Docker platform

- Added one Compose project named `sentinel-ai` with exactly API, web, PostgreSQL, and Redis.
- Bound published ports to `127.0.0.1` only.
- Used dedicated Sentinel AI resources with no UniHub network or volume attachment.
- Added explicit base-image and local application-image tags.
- Added health checks, dependency-aware startup, and persistent PostgreSQL/Redis volumes.
- Ensured ordinary shutdown and cleanup do not delete volumes.

| Service | Address |
| --- | --- |
| Web | `http://127.0.0.1:15173` |
| API health | `http://127.0.0.1:18000/health` |
| API readiness | `http://127.0.0.1:18000/ready` |
| PostgreSQL | `127.0.0.1:15432` |
| Redis | `127.0.0.1:16379` |

### Commands

- `make bootstrap` — install locked dependencies.
- `make up` — build and start four services.
- `make ps` — show service health.
- `make logs` — show bounded recent logs.
- `make verify` — run the complete acceptance gate.
- `make down` — stop services and preserve volumes.
- `make clean` — remove only explicit repository caches/builds.

Windows PowerShell and Bash implementations are supplied for bootstrap, verification, and safe cleanup.

## Locked baseline

### Python

- Python 3.12.13 and uv 0.12.2
- FastAPI 0.141.1, Uvicorn 0.52.1
- asyncpg 0.31.0, redis 6.4.0, pydantic-settings 2.15.0
- Ruff 0.16.2, mypy 1.20.2, pytest 8.4.2

### Frontend

- Node.js 22.14.0 and npm 10.9.2
- React/React DOM 19.2.8
- Vite 8.2.1, TypeScript 5.9.3, Vitest 4.1.10

### Containers

- Python `3.12.13-slim-bookworm`
- uv `0.12.2`
- Node `22.14.0-alpine3.21`
- PostgreSQL `16.4-alpine3.20`
- Redis `7.2.5-alpine3.20`
- Local images `sentinel-ai-api:task2` and `sentinel-ai-web:task2`

## Verification evidence

- Locked `make bootstrap` passed.
- Ruff, strict mypy, Prettier, ESLint, and TypeScript checks passed.
- Five backend tests and one frontend test passed.
- Vite production build passed; npm audit reported zero vulnerabilities.
- Compose validation, image builds, startup, and all four health checks passed.
- Web, API health, and API readiness smoke tests passed.
- With Sentinel Redis paused, `/health` remained HTTP 200 and `/ready` correctly returned HTTP 503.
- Redis recovery, full restart, dedicated-volume persistence, bounded logs, and clean shutdown passed.
- Final `make verify` passed and preserved both named data volumes.

## Explicitly deferred

- Transaction event contracts and ingestion APIs
- Business schemas and migrations
- Redis Streams, workers, and consumer groups
- Authentication and product workflows
- Fraud rules, scoring, alerts, and decisions
- Dataset ingestion and profiling
- Models, ML, AI, and production deployment

## Current handoff

Task 1 and Task 2 are complete. No commit or push had been performed when this report was prepared. The next planned task is the versioned transaction event contract and ingestion boundary; it has not started.
