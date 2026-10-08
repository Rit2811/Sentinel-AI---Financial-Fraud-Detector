# Local Infrastructure

[Teammate setup](../docs/teammate-setup.md) documents independent local operation.
Combine `compose.yaml`, `compose.postgres-local.yaml` and `compose.teammate.yaml`
with ignored `.env.teammate.local`, project `sentinel-team` and dedicated volumes.
Use `scripts/teammate.ps1` on Windows to select them consistently.

Application images are `sentinel-ai-api:application`,
`sentinel-ai-scoring-worker:random-forest`, `sentinel-ai-dashboard:application`.
Developer builds use `development` / `random-forest-development` tags. Compose
generates role-based names such as `sentinel-team-dashboard-1`; no fixed
`container_name` overrides prevent independent projects from sharing an engine.

Full local scoring has six services: PostgreSQL 17, Redis, API, publisher,
scoring worker and dashboard. The proof consumer stays disabled. Published ports
bind to localhost. The profile preserves fsync/synchronous commits and starts
independent scoring held until that deployment is verified.

Base Compose alone selects legacy PostgreSQL/volume defaults and is not the
current teammate or owner deployment. The isolated `compose.test.yaml` uses
tmpfs and guarded test database/Redis targets; never substitute application volumes.
