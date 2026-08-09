# API shell

Python 3.12 FastAPI service for platform liveness and dependency readiness only.

- `GET /health` proves the API process can respond.
- `GET /ready` performs read-only PostgreSQL and Redis reachability checks.

No transaction, authentication, fraud, scoring, schema, stream, ML, or AI behavior belongs in this Task 2 shell.
