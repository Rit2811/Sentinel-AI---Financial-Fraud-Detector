# Authorization ingestion API

Node.js 22 and Express service for the Task 3 authorization-event boundary.

- `GET /health` proves the API process can respond.
- `GET /ready` checks PostgreSQL and Redis reachability.
- `POST /api/v1/authorization-events` validates and atomically persists synthetic/tokenized authorization events.
- `GET /openapi.json` exposes the versioned API contract; `/docs` renders it locally.

The service does not score fraud, make payment decisions, process real card data, or publish Redis streams.
