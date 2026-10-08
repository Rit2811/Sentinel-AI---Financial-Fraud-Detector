# Authorization Event Ingestion

The local API accepts only synthetic/tokenized version 1 authorization events at
`POST /api/v1/authorization-events`. It records accepted events, quarantines future-dated
semantic anomalies, and uses PostgreSQL uniqueness for concurrency-safe idempotency. No response
is a fraud score, payment approval, or card-network decision.

## Contract summary

- `schema_version` is exactly `1.0`.
- `amount_minor` is a non-negative safe integer; floating-point money is rejected.
- `occurred_at` is ISO 8601 UTC.
- Card-present events require `terminal_token` and a physical entry mode.
- Card-not-present events require `device_token`; `ecommerce` is card-not-present only.
- `Idempotency-Key` is a required UUID. Only its SHA-256 hash is stored.
- Requests are limited to 32 KiB and must use `Content-Type: application/json`.
- PAN, card-number, CVV/CVC, PIN, and track-data field names are prohibited recursively.
- OpenAPI is available at `http://127.0.0.1:18000/openapi.json` and Swagger UI at `/docs`.

## Automated verification

`make verify` runs formatting/linting, 20 unit tests, frontend regressions, a migration up/down/up
cycle, six real-PostgreSQL integration tests, concurrent idempotency tests, rollback and immutable
record checks, service smoke tests, Redis failure/recovery, and cleanup.

## Thunder Client acceptance

Start the stack with `make up`, then create five POST requests to
`http://127.0.0.1:18000/api/v1/authorization-events`. Use `Content-Type: application/json` and the
headers shown for each case. All examples are synthetic.

### T1 Accepted

Headers:

```text
Idempotency-Key: 4f93f5fb-44f8-4d0a-9f69-c72466ad6402
X-Correlation-ID: 985d24e4-42be-4e3b-bb9a-ad43664ca053
```

Body:

```json
{
  "schema_version": "1.0",
  "event_id": "e82d7cc1-0d61-4f57-a6db-0e50d3708410",
  "authorization_id": "1b1e8879-4ec8-47d4-b447-24c7dc17c2a7",
  "occurred_at": "2026-08-10T12:30:00.000Z",
  "data_origin": "synthetic_enriched",
  "channel": "card_not_present",
  "amount_minor": 129900,
  "currency": "INR",
  "card_token": "card_tok_demo_001",
  "account_token": "acct_tok_demo_001",
  "merchant_id": "merchant_demo_001",
  "merchant_country": "IN",
  "entry_mode": "ecommerce",
  "device_token": "device_tok_demo_001"
}
```

Expected: HTTP `202`, outcome `accepted`, and IDs plus `received_at` present.

### T2 Replay

Repeat T1 without changing its headers or body.

Expected: HTTP `200`, outcome `duplicate`, `Idempotent-Replayed: true`, and the same ingestion and
event IDs as T1.

### T3 Conflict

Repeat T1 with the same headers but change only `amount_minor` to `129901`.

Expected: HTTP `409`, code `idempotency_conflict`, and no second event.

### T4 Validation

Use a new UUID for `Idempotency-Key`, keep the T1 body, and change `amount_minor` to `-1`.

Expected: HTTP `422`, code `validation_failed`, safe reason codes, and no request echo.

### T5 Quarantine

Use new UUIDs for `Idempotency-Key`, `X-Correlation-ID`, `event_id`, and `authorization_id`. Keep the
T1 body otherwise, but set `occurred_at` to `2099-01-01T00:00:00.000Z`.

Expected: HTTP `202`, outcome `quarantined`, reason `occurred_at_too_far_in_future`, and no accepted
event row.
