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

## Sparkov replay contract

The same ingestion endpoint accepts schema `2.0` with origin `sparkov_replay`.
Its exact required allowlist is `schema_version`, `data_origin`, `event_id`,
`authorization_id`, `occurred_at`, `amount_minor`, `currency`, `card_token`,
`merchant_id`, `merchant_category`, `time_basis`, and `currency_basis`.
Unknown fields, including null-valued fields, are rejected. Raw source identities,
personal fields, coordinates, `unix_time`, and `is_fraud` are rejected recursively.

The source adapter owns deterministic UUID derivation, HMAC card tokenization,
merchant hashing and exact decimal-cent conversion. The API validates UUIDs,
`card_` plus 64 lowercase hex digits, `merchant_` plus 64 lowercase hex digits,
nonnegative safe integer cents, and a trimmed category of 1-128 characters.
`currency=USD` and `currency_basis=simulation_assumption` are explicit simulation
assumptions. `time_basis=source_wall_clock_as_utc` identifies source text time
interpreted as UTC, exactly `YYYY-MM-DDTHH:mm:ssZ` without fractional seconds;
no offset from the source Unix clock is applied here.
The existing future-time quarantine rule still applies.

No channel, account, entry mode, terminal, device, balance or country is inferred.
Unavailable database columns are NULL and absent from the original JSON payload.
Dashboard totals include v2, while the two channel counts describe only observed
v1 channel values. Stream envelopes retain their six existing evidence fields.

Migration `0004` preserves v1 rows, immutable triggers, outbox/receipt foreign
keys and receipt identities. It requires a transaction and uses a five-second
lock timeout. Downgrade refuses any v2 accepted, quarantined or idempotency
evidence. Existing application Docker startup runs forward migrations; deploy
only at the authorized migration gate. Never downgrade the application database
or disable triggers to rewrite retained events.

## Isolated verification

Integration tests require an explicit `TEST_DATABASE_URL` naming
`sentinel_task4_test` on `127.0.0.1`, `localhost`, or `[::1]`, with no query
parameters or fragment. The connected
database is checked before destructive setup. Stream tests additionally require
`TEST_REDIS_URL` on those same loopback hosts, Redis database 0, and
`TEST_REDIS_PORT` (default 26379), without query parameters or fragments;
they use unique test keys and never flush Redis.
`infrastructure/compose.test.yaml` is standalone and uses tmpfs, with no retained
application volumes. Both repository verification scripts use this test stack
for the empty migration cycle and integration tests; application migrations
remain forward-only.

From the repository root in PowerShell, using installed dependencies:

```powershell
docker compose -p sentinel-task4-test -f infrastructure/compose.test.yaml up -d --wait --wait-timeout 60 --pull never
$env:DATABASE_URL = 'postgresql://sentinel:sentinel_test_only@127.0.0.1:25432/sentinel_task4_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:TEST_REDIS_URL = 'redis://:sentinel_test_only@127.0.0.1:26379/0'
npm.cmd --prefix backend run migrate:up
npm.cmd --prefix backend test -- --no-cache
npm.cmd --prefix backend run test:integration -- --no-cache --testTimeout=15000
docker compose -p sentinel-task4-test -f infrastructure/compose.test.yaml down
```

Delivery is at least once with deduplicated receipt effects. Existing limits
remain: stream trimming can remove unprocessed entries, publisher claims are not
fenced, and receipt conflicts do not compare hashes. These tests demonstrate
the covered recovery paths, not lossless delivery under arbitrary outages.
Data/feature parity remains a prerequisite for training; stream receipts are
not fraud decisions.

## Task 6 preparation

Migration 0005 adds version-assigned jobs, immutable safe feature snapshots
and original prediction/decision records. Deferred checks require result and
scored status to commit together. Application migrations 0001-0006 were verified;
0007 durable worker history and 0008 query indexes still require application
migration after Docker recovery. The Python worker exists but is not active.

`GET /api/v1/transactions/{eventId}/result` reads stored state, never derives
an action from acceptance. Access requires private `RESULT_API_TOKEN` (at least
32 characters) and UUID `SCORING_RUN_ID`; both default to unconfigured. Compose
passes these optional values only to the API. Do not expose the prototype
publicly; this token boundary is not tenant/user authorization.

`GET /ready/scoring` returns 503 until the approved worker is connected.
`/ready` still checks infrastructure only; `/health` is process liveness.
Schema-v2 acceptance now includes pending processing and a result location.
Migration 0006 implements once-only simulated execution and separate authorized
review resolution. No fixture or application scoring worker is activated.

See `../docs/task-6-worker-status.md`, `../docs/task-6-requests.http` and OpenAPI
for actual routes, states, test coverage and the remaining activation gates.
