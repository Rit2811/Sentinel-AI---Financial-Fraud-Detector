# Docker purpose names

## Reconciled Configuration

The laptop commit and PC work were reconciled locally on 2026-10-06. Current
canonical names are defined in [component-naming.md](component-naming.md):
API `local`, dashboard `dashboard`, scoring worker `replay`, and the existing
`pipeline-profile`, `deadline-trial` and `combined-commit` experiment tags.
The Mumbai override retains its explicitly selected images and activation hold.
The aliases recorded below describe the earlier laptop engine, not the current
deployment selection. Git does not transfer Docker images or alias definitions.

The isolated project remains `sentinel-test`, with Compose-generated container
names. Explicit legacy DNS aliases retain compatibility with immutable images
and fixture guards; `sentinel-test-redis-1` remains the restart-test target.
The laptop's fixed container names were not retained: they would break that
restart reference and remove the original benchmark DNS names without aliases.
Historical laptop observations below remain preserved, not new qualification.

On 2026-10-05, the owner requested descriptive Sentinel container and image
names. This change concerns naming only; Task 6 remains incomplete and no
application or scoring service was started, rebuilt or activated.

## Images present on the inspected engine

| Existing compatibility tag | Purpose tag | Image ID prefix |
| --- | --- | --- |
| `sentinel-ai-api:task2` | `sentinel-ai-api:operational-api-legacy` | `ab2f3dd9e68f` |
| `sentinel-ai-api:task3` | `sentinel-ai-api:authorization-ingestion-legacy` | `caede9ba8ad5` |
| `sentinel-ai-api:task4` | `sentinel-ai-api:streaming-ingestion` | `af03bd92fee3` |
| `sentinel-ai-web:task2` | `sentinel-ai-web:operations-dashboard` | `622c1034248b` |

All four purpose tags were created and their complete image IDs matched the
original tags. Docker image names are tags; the old tags remain as aliases for
historical commands and rollback references. No image layers were copied or
removed. The inspected backend image is not a promotion of any later qualified
or candidate image recorded in the performance reports.

## Containers

The existing stopped test containers were renamed in place:

| Previous name | Purpose name |
| --- | --- |
| `sentinel-task4-test-postgres-1` | `sentinel-ai-integration-postgres` |
| `sentinel-task4-test-redis-1` | `sentinel-ai-integration-redis` |

The test Compose file now declares these names explicitly. Its project identity
and database name remain unchanged so existing verification/cleanup commands
retain the same ownership. Application services already use purpose-based
Compose service names and retain their existing project identity.

Docker accepted both renames. Its event history then recorded destruction of
both containers five seconds later, outside the commands issued for this task.
The actor responsible is not established by these events. Final container
inventory was empty, so post-rename preservation of container state could not
be verified. No replacement containers were created. The two test containers
had no mounted volumes before renaming; both application named data volumes
still exist. Volume existence is not a new database-content verification.

## Compose references for images absent on this engine

| Previous default | Purpose default |
| --- | --- |
| `sentinel-ai-scoring-worker:task6` | `sentinel-ai-scoring-worker:random-forest-scoring` |
| `sentinel-ai-api:task6-pipeline-profile` | `sentinel-ai-api:pipeline-profiling-candidate` |
| `sentinel-ai-api:task6-deadline-trial` | `sentinel-ai-api:two-second-deadline-diagnostic` |
| `sentinel-ai-scoring-worker:task6-deadline-trial` | `sentinel-ai-scoring-worker:two-second-deadline-diagnostic` |
| `sentinel-ai-scoring-worker:task6-combined-commit` | `sentinel-ai-scoring-worker:combined-commit-candidate` |

These references were updated without creating images or changing diagnostic
parameters. Before any separately authorized use of these overlays, the exact
intended image must be available under its new tag, or selected through the
existing candidate-image override where supported. Do not substitute an
unverified build for a historical image. Historical reports retain their tags
and immutable image IDs.

## Verification and scope

- Six Compose configurations validated with `config --no-interpolate --quiet`:
  base, test, base/profile, base/pipeline-candidate, base/deadline-trial, and
  base/deadline-trial/combined-trial.
- Four old/new image pairs passed complete image-ID equality checks.
- Docker events confirmed two renames, followed by two external removals.
- Both `sentinel-ai-postgres-data` and `sentinel-ai-redis-data` still exist.
- Git diff review and `git diff --check` passed; `.env.task6.local` is ignored.
- No application tests, load runs, reserved evaluation, container restarts,
  volume changes, commits or pushes were performed. Naming does not qualify
  Task 6 or begin Task 7. The next work remains the separately scoped Task 6
  capacity issue; it was not started here.
