import { randomUUID } from 'node:crypto'

import {
  claimIdempotency,
  completeIdempotency,
  getIdempotencyRecord,
  insertAcceptedEvent,
  insertAttempt,
  insertOutboxEvent,
  insertQuarantinedEvent,
} from '../repositories/authorizationEventRepository.js'
import { canonicalize, sha256 } from './hashing.js'

export class DependencyUnavailableError extends Error {}

function responseBody({
  ingestionId,
  event,
  correlationId,
  outcome,
  reasonCodes,
  receivedAt,
}) {
  return {
    ingestion_id: ingestionId,
    event_id: event.event_id,
    correlation_id: correlationId,
    schema_version: event.schema_version,
    outcome,
    reason_codes: reasonCodes,
    received_at: receivedAt,
  }
}

export function createAuthorizationIngestionService(pool, log) {
  return {
    async ingest({
      event,
      idempotencyKey,
      correlationId,
      quarantineReasonCodes,
    }) {
      const keyHash = sha256(idempotencyKey)
      const payloadHash = sha256(canonicalize(event))
      const receivedAt = new Date().toISOString()
      const client = await pool.connect().catch((error) => {
        log.error(
          { errorType: error.name },
          'PostgreSQL connection unavailable',
        )
        throw new DependencyUnavailableError()
      })

      try {
        await client.query('BEGIN')
        const claimed = await claimIdempotency(client, keyHash, payloadHash)
        if (!claimed) {
          const record = await getIdempotencyRecord(client, keyHash)
          if (!record || record.status !== 'completed')
            throw new Error('incomplete_idempotency_record')
          if (record.payload_hash !== payloadHash) {
            const ingestionId = randomUUID()
            await insertAttempt(client, {
              ingestionId,
              eventId: event.event_id,
              correlationId,
              keyHash,
              payloadHash,
              outcome: 'idempotency_conflict',
              reasonCodes: ['idempotency_conflict'],
              receivedAt,
            })
            await client.query('COMMIT')
            return {
              status: 409,
              body: {
                ingestion_id: ingestionId,
                correlation_id: correlationId,
                outcome: 'rejected',
                code: 'idempotency_conflict',
                reason_codes: ['idempotency_conflict'],
              },
            }
          }

          await client.query('COMMIT')
          return {
            status: 200,
            replayed: true,
            body: { ...record.response_body, outcome: 'duplicate' },
          }
        }

        const ingestionId = randomUUID()
        const quarantined = quarantineReasonCodes.length > 0
        const outcome = quarantined ? 'quarantined' : 'accepted'
        if (quarantined) {
          await insertQuarantinedEvent(
            client,
            randomUUID(),
            event,
            quarantineReasonCodes,
          )
        } else {
          await insertAcceptedEvent(client, event)
          await insertOutboxEvent(client, event, correlationId)
        }
        await insertAttempt(client, {
          ingestionId,
          eventId: event.event_id,
          correlationId,
          keyHash,
          payloadHash,
          outcome,
          reasonCodes: quarantineReasonCodes,
          receivedAt,
        })
        const body = responseBody({
          ingestionId,
          event,
          correlationId,
          outcome,
          reasonCodes: quarantineReasonCodes,
          receivedAt,
        })
        await completeIdempotency(client, keyHash, 202, body)
        await client.query('COMMIT')
        return { status: 202, body }
      } catch (error) {
        try {
          await client.query('ROLLBACK')
        } catch {
          // The original database failure is the useful diagnostic.
        }
        log.error(
          { errorType: error.name, databaseCode: error.code },
          'Authorization ingestion transaction failed',
        )
        throw new DependencyUnavailableError()
      } finally {
        client.release()
      }
    },
  }
}
