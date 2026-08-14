import { randomUUID } from 'node:crypto'

import {
  claimOutboxBatch,
  markOutboxFailure,
  markOutboxPublished,
} from '../repositories/streamRepository.js'
import { validateEnvelope } from './envelope.js'

export async function publishOutboxBatch({
  pool,
  redis,
  streamConfig,
  log,
  workerId = `publisher-${randomUUID()}`,
}) {
  const rows = await claimOutboxBatch(pool, {
    workerId,
    batchSize: streamConfig.batchSize,
    claimIdleMs: streamConfig.claimIdleMs,
  })
  for (const row of rows) {
    try {
      const envelope = validateEnvelope(row.envelope)
      const messageId = await redis.xAdd(
        streamConfig.name,
        '*',
        { envelope: JSON.stringify(envelope) },
        {
          TRIM: {
            strategy: 'MAXLEN',
            strategyModifier: '~',
            threshold: streamConfig.retention,
          },
        },
      )
      await markOutboxPublished(pool, row.outbox_id, messageId)
      log.info(
        { eventId: row.event_id, streamMessageId: messageId },
        'Authorization envelope published',
      )
    } catch (error) {
      const errorCode =
        error?.message === 'invalid_stream_envelope'
          ? 'invalid_stream_envelope'
          : 'stream_publish_failed'
      const deadLettered = await markOutboxFailure(pool, {
        outboxId: row.outbox_id,
        attemptCount: row.attempt_count,
        maxAttempts: streamConfig.maxAttempts,
        errorCode,
      })
      log.error(
        { eventId: row.event_id, errorCode, deadLettered },
        'Authorization envelope publish failed',
      )
    }
  }
  return rows.length
}
