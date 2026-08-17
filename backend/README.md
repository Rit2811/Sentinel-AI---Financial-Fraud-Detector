# Authorization ingestion API

Node.js 22 and Express service for the Task 3 authorization-event boundary.

- `GET /health` proves the API process can respond.
- `GET /ready` checks PostgreSQL and Redis reachability.
- `GET /api/v1/dashboard?range=24h` returns non-sensitive PostgreSQL-backed operational aggregates for `1h`, `24h`, or `7d`.
- `POST /api/v1/authorization-events` validates and atomically persists synthetic/tokenized authorization events.
- `GET /openapi.json` exposes the versioned API contract; `/docs` renders it locally.

Accepted events are also written to a transactional PostgreSQL outbox. Separate
Node.js publisher and consumer workers under `src/stream/` reliably move those
envelopes through Redis Streams, record deduplicated proof receipts, retry
failures, reclaim idle messages, and dead-letter messages that exhaust retries.
The dashboard contract reports ingestion and stream-processing state only. The
API itself does not score fraud, make payment decisions, or process real card
data.
