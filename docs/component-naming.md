# Component Naming

## Convention

Name components by purpose, deployment or meaningful version/experiment. Do not
use milestone numbers as filenames, image tags, container names or new report
directories. Milestone numbers can remain in planning and acceptance discussions.

## Runtime Names

| Component | Canonical name |
| --- | --- |
| Local API/publisher image | sentinel-ai-api:local |
| Supabase API/publisher image | sentinel-ai-api:supabase |
| Local replay worker image | sentinel-ai-scoring-worker:replay |
| Supabase scoring worker image | sentinel-ai-scoring-worker:supabase |
| Dashboard image | sentinel-ai-web:dashboard |
| Private application configuration | .env.application.local |
| Supabase target configuration | .env.supabase.local |
| Mumbai target input | .env.supabase-mumbai.local |
| Application replay load client | sentinel-replay-client-<uuid> |
| Isolated load API/publisher/worker/client | sentinel-load-<role>-<uuid> |
| Isolated fixture stack/network | sentinel-test / sentinel-test_default |
| New application load reports | services/ml/reports/replay-load/ |
| New isolated scoring reports | services/ml/reports/scoring-load/ |
| New action/review checks | services/ml/reports/replay-actions/ |

Existing application services already use role-based Compose names:
sentinel-ai-api-1, sentinel-ai-publisher-1, sentinel-ai-scoring-worker-1,
sentinel-ai-consumer-1, sentinel-ai-postgres-1, sentinel-ai-redis-1 and
sentinel-ai-web-1. Those stable identities are not changed.

Experimental tags describe behavior: pipeline-profile, deadline-trial and
combined-commit. They are NOT approved production promotions. The deadline
trial remains diagnostic only; naming does not adopt its two-second limit.

## Document Mapping

| Former filename | Current filename |
| --- | --- |
| task-3-authorization-ingestion.md | authorization-ingestion.md |
| task-6-preparation.md | scoring-readiness.md |
| task-6-worker-status.md | scoring-worker-status.md |
| task-6-verification-record.md | scoring-verification.md |
| task-6-execution-and-recovery.md | scoring-execution-recovery.md |
| task-6-requests.http | transaction-replay.http |
| infrastructure/wslconfig.task6 | infrastructure/wslconfig.prototype |

Mutable links were updated; historical body/evidence is retained. The WSL file
is still a prototype, not a new system setting or permission to install it.

## Compatibility and Safety

- Image aliases point to exactly the existing immutable image IDs. No image was
  rebuilt, removed or qualified by this cleanup. Historical tags remain only
  for existing evidence/rollback references.
- Stopped API/publisher/worker/consumer containers were recreated WITHOUT
  starting them. Image IDs, hashed effective environments, command arguments
  and mount sets matched before/after. Docker mount ordering is nonsemantic;
  comparison sorts mounts by destination. Activation remains held.
- .env.application.local is an exact byte copy of the protected original
  .env.task6.local. Original credentials, run identity, metadata and its
  environment checksum remain intact. Helpers prefer the canonical name and
  fall back to the old file for existing setups. The old copy is a rollback
  artifact, not a second configuration to edit.
- Do not rename applied SQL migration files, frozen packages, policy/authorization
  JSON, historical reports/backups, Redis stream/group IDs or recorded run IDs:
  their names or bytes belong to durable evidence/protocols.
- The isolated stack uses new role-based container/network names while retaining
  sentinel_task4_test and legacy Docker DNS aliases ONLY for strict safety
  guards and already measured images. These aliases resolve exclusively inside
  the isolated network; they are not application targets. Existing retired test
  containers/evidence were not erased.
- No database data, model, policy, feature contract, deadline or durability
  setting was changed. No activation, reserved evaluation, commit or push.

## Verification

Purpose-named environment and Mumbai target files are Git-ignored. Both private
runtime environment copies matched the recorded SHA-256. Nine image aliases
matched old IDs. Core stopped containers retained exact image/environment/mount/
command configuration. Focused Python configuration/benchmark/gate tests passed
55 checks. All 49 backend integration checks passed against the new tmpfs
fixture stack. Existing images resolved its legacy safety DNS aliases and
queried the expected isolated database/Redis. The named Redis restart check is
explicitly enabled and passed separately. No application load qualification
was run.

Already measured images retain their own older installed load-client code.
Isolated Docker controllers now mount only connected_benchmark.py,
worker_benchmark.py and database.py read-only, recording their checksums just
like the existing application controller. This keeps new purpose-based endpoint
names consistent without rebuilding or mounting any scorer/worker implementation.
Retired fixture containers use sentinel-test-postgres-archive and
sentinel-test-redis-archive; their IDs/images/tmpfs configuration are unchanged.
The pinned replay image also imported these controller-only tools successfully;
no database connection or model execution was required for that import check.

Private evidence is under services/ml/reports/component-naming/. Current
deployment status remains in scoring-verification.md and supabase-clock-resume.md.
