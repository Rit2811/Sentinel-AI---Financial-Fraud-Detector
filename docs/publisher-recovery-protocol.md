# Bounded Single-Commit Publisher

## Scope

Owner authorized local implementation/testing on 2026-10-04, not activation.
Model, thresholds, one-second scoring deadline, fsync and synchronous commit
remain unchanged. PostgreSQL and Redis are not an atomic distributed transaction.

## Protocol

1. Begin a PostgreSQL transaction with synchronous commit, a 100ms lock timeout,
   500ms statement timeout and 1500ms idle-in-transaction timeout.
2. Try a shared transaction-scoped advisory fence. A competing publisher returns
   immediately. This intentionally serializes this outbox: SKIP LOCKED alone
   would allow a later same-card event to overtake a locked predecessor.
3. Lock at most four existing pending/legacy-publishing rows, ordered by the
   worker's committed acceptance key `(event.created_at,event_id)`. No batch-fill
   delay. An unavailable retry or non-abandoned legacy claim stops the prefix;
   later rows do not overtake it. Terminal published/dead-letter rows are skipped.
4. Sequentially validate and XADD canonical envelopes. Each Redis call is bounded
   by the remaining 200ms publication/outcome budget across the batch. The
   premature 100ms per-call cap was removed after a measured uncertain
   publication caused a two-second ordered retry wait and ten expiries. The
   total publication budget and one-second scoring deadline remain unchanged.
   The publisher disables the offline queue and closes the Redis connection on
   uncertainty/timeout, reconnecting outside the database transaction next cycle.
5. Only after Redis acceptance, update that row's publication evidence using the
   SAME database client, then commit the complete batch once. Empty transactions
   do not change rows. Logs report successful publication only after commit ACK.
6. On send/validation/outcome failure, roll back the ENTIRE batch. Persist a
   compare-and-set failure/retry record in a separate synchronous transaction,
   retaining the previous two-second backoff and maximum-attempt dead-letter
   policy. It cannot regress a concurrently committed published row. A failure
   while persisting this record still leaves original work recoverable.

The 200ms admission budget is checked before each Redis call and includes elapsed
outcome-statement time between calls. A final SQL statement can overrun this
budget up to its separate SQL timeout; it is not a hard total transaction bound.
It does not cover commit latency or operating-system scheduling. SQL timeouts bound
individual statements and
lock waits; they do not guarantee a subsecond fsync acknowledgement. Observe
actual lock/commit timings rather than treating configured bounds as a benchmark.
Deploy with the old publisher stopped; mixed old/new publishers do not share the
new fence. Legacy abandoned claims remain reclaimable without bulk state resets.
Legacy claim helpers remain exported for compatibility but the new publisher
entrypoint does not call them.
Per-card scoring history stays database-canonical, not Redis-arrival ordered.
Uncommitted future ingestion cannot be ordered ahead of already visible commits;
the existing worker's acceptance-order checks remain authoritative.

## Failure Boundaries

| Boundary | Durable database state | Recovery |
| --- | --- | --- |
| Before Redis acceptance | Pending/legacy claim unchanged on rollback | Retry |
| Redis accepted, reply lost | Original state on rollback | Republish same event ID |
| Prefix accepted, later send fails | Whole batch rolls back | Prefix duplicates permitted; ordered retry |
| Process killed before COMMIT | PostgreSQL releases locks and rolls back | Restart republishes canonical IDs |
| COMMIT succeeds, ACK lost | Published if commit succeeded; pending otherwise | Inspect durable state next cycle; never blindly reset |
| Redis unavailable | Rollback, durable retry/failure evidence | Reconnect outside row locks; no score/default Pass fabricated |

At-least-once Redis delivery is intentional. Database uniqueness and existing
worker checkpoints deduplicate history, snapshots, original decisions and
separate executions by run/event identity. Stream acknowledgement still occurs
only after durable completion or durable terminal failure. Expired jobs never
execute, including late recovered publications. Dead letters remain explicit
terminal failure evidence, not successful delivery or fraud labels.

## Verification

See `task-6-verification-record.md` for exact test/image/report evidence. Short
unqualified-image diagnostics are marked `diagnostic_only`; the runtime gate
rejects them regardless of their rate/outcome. Activation still requires exact
qualified images, controlled normal traffic and a full ten-minute 5 TPS workload
with zero expiries, full parity and no late execution on actual persistent storage.
