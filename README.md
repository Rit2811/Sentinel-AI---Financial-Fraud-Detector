# Sentinel AI

Sentinel AI is a local prototype for synthetic/tokenized financial authorization
events. It combines validated ingestion, durable PostgreSQL evidence, Redis
Streams, frozen fraud scoring, simulated actions and an operational dashboard.

## Run on Your Computer

Read [teammate setup](docs/teammate-setup.md) for independent Docker development,
private runtime inputs, fresh local secrets and the exact startup commands.
GitHub supplies code; model binaries, credentials and local databases are separate.
No remote PostgreSQL/Supabase URI is needed for the independent local setup.

The complete local stack has six services: PostgreSQL 17, Redis, API, publisher,
Python scoring worker and dashboard. Each developer has their own persistent
database/Redis volumes. The optional proof consumer is disabled in this profile.

| Component | Default local address |
| --- | --- |
| Dashboard | http://localhost:15173 |
| API infrastructure readiness | http://localhost:18000/ready |
| API scoring readiness | http://localhost:18000/ready/scoring |
| OpenAPI UI | http://localhost:18000/docs |

## Application Behavior

- Authorization ingestion validates the payload, preserves canonical event IDs
  and deduplicates retries before durable stream publication.
- The selected scorer is the approved sigmoid-calibrated Random Forest. It uses
  the frozen point-in-time feature contract, not the separate ensemble track.
- Review threshold is 0.10; Block threshold is 0.25. Pass/Block produce automatic
  simulated actions; Review requires an authorized, idempotent human resolution.
- Results preserve the original model decision. Human resolutions are not fraud
  labels. Failed, unavailable or expired scoring never defaults to Pass.
- The scoring deadline is 1000 ms, with durable evidence and completion before
  stream acknowledgement. Late scores do not execute.
- The dashboard shows ingestion/stream activity. Result and review routes exist
  in the API; a complete analyst case-management interface is not implemented.

## Development

`backend/` contains the Express service, migrations and tests; `frontend/` the
React dashboard; `services/ml/` the Python feature/scoring code; `infrastructure/`
the Compose profiles; `scripts/` setup helpers. Runtime containers include their
dependencies. Host Node 22/npm and Python 3.12/uv are useful for code development.

New developer deployments start with scoring activation held. They need their
own runtime/workload verification before general activation; another machine's
performance evidence does not qualify them automatically.

## Data and Credentials

Use synthetic or tokenized events only. Do not commit raw datasets, labels,
cardholder data, filled env files, model binaries or private reports. The private
model bundle is transferred intact and verified by its external checksum. Do not
retrain or repeat the reserved evaluation as a setup step. No source channel,
device, entry mode or balance is invented when it is absent from the data.

Local bearer tokens protect result/review routes; full user/tenant authorization,
drift monitoring and automatic retraining are not implemented. This is a local
simulation prototype, not a deployed banking payment system.
