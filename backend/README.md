# Authorization API

Node 22/Express service for validated synthetic/tokenized authorization events,
durable PostgreSQL audit/outbox records and operational dashboard queries.
Use [teammate setup](../docs/teammate-setup.md) for the Docker environment.

| Route | Purpose |
| --- | --- |
| `GET /health` | Process liveness |
| `GET /ready` | PostgreSQL and Redis reachability |
| `GET /ready/scoring` | Held/eligible scoring readiness |
| `GET /api/v1/dashboard?range=24h` | Non-sensitive ingestion/stream aggregates |
| `POST /api/v1/authorization-events` | Validated idempotent acceptance |
| `GET /api/v1/transactions/{eventId}/result` | Stored scoring/action state; private result token |
| `POST /api/v1/transactions/{eventId}/review-resolution` | Authorized idempotent manual resolution; separate reviewer token |
| `/docs`, `/openapi.json` | Current versioned API contract |

The publisher moves committed outbox entries to Redis Streams. The Python worker
scores schema-v2 Sparkov replay events using the exact frozen package. Stream
delivery is at least once; durable history/actions are deduplicated. A receipt or
acceptance is not a fraud decision. Review resolution preserves the model evidence.

Schema-v2 payloads contain event/authorization IDs, whole-second simulation time,
integer minor-unit amount, currency assumptions, card/merchant tokens and category.
Raw card numbers, labels, PII and unsupported invented fields are rejected.
No credentials belong in frontend code or logs.

Use unit tests for pure logic and explicit isolated PostgreSQL/Redis fixtures for
integration tests. The guarded fixture database is `sentinel_task4_test` on ports
25432/26379. Integration setup can truncate fixture data; never point it at an
application database. Forward migrations preserve existing application records;
do not downgrade/reset an application volume to run a test.
