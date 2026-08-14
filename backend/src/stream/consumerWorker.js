import { createHash, randomUUID } from 'node:crypto'

import { recordProcessingReceipt } from '../repositories/streamRepository.js'
import { validateEnvelope } from './envelope.js'

function hashEnvelope(envelope) {
  return createHash('sha256').update(JSON.stringify(envelope)).digest('hex')
}

async function handleMessage({ pool, redis, streamConfig, log, message }) {
  try {
    const envelope = validateEnvelope(JSON.parse(message.message.envelope))
    const inserted = await recordProcessingReceipt(pool, {
      consumerPurpose: streamConfig.consumerPurpose,
      eventId: envelope.event_id,
      streamMessageId: message.id,
      envelopeHash: hashEnvelope(envelope),
    })
    await redis.xAck(streamConfig.name, streamConfig.group, message.id)
    await redis.hDel(`${streamConfig.name}:retry-counts`, message.id)
    log.info(
      { eventId: envelope.event_id, streamMessageId: message.id, inserted },
      inserted ? 'Proof effect recorded' : 'Duplicate delivery deduplicated',
    )
    return inserted ? 'processed' : 'duplicate'
  } catch (error) {
    const retryKey = `${streamConfig.name}:retry-counts`
    const attempts = await redis.hIncrBy(retryKey, message.id, 1)
    if (attempts >= streamConfig.maxAttempts) {
      await redis.xAdd(
        streamConfig.deadLetterName,
        '*',
        {
          source_stream: streamConfig.name,
          source_message_id: message.id,
          error_code: 'consumer_processing_failed',
        },
        {
          TRIM: {
            strategy: 'MAXLEN',
            strategyModifier: '~',
            threshold: streamConfig.retention,
          },
        },
      )
      await redis.xAck(streamConfig.name, streamConfig.group, message.id)
      await redis.hDel(retryKey, message.id)
      log.error(
        { streamMessageId: message.id, attempts },
        'Stream message moved to dead letter',
      )
      return 'dead_letter'
    }
    log.warn(
      { streamMessageId: message.id, attempts, errorType: error.name },
      'Stream message left pending for retry',
    )
    return 'pending'
  }
}

export async function ensureConsumerGroup(redis, streamConfig) {
  try {
    await redis.xGroupCreate(streamConfig.name, streamConfig.group, '0', {
      MKSTREAM: true,
    })
  } catch (error) {
    if (!String(error.message).includes('BUSYGROUP')) throw error
  }
}

export async function consumeOnce({
  pool,
  redis,
  streamConfig,
  log,
  consumerId = `consumer-${randomUUID()}`,
}) {
  const reclaimed = await redis.xAutoClaim(
    streamConfig.name,
    streamConfig.group,
    consumerId,
    streamConfig.claimIdleMs,
    '0-0',
    { COUNT: streamConfig.batchSize },
  )
  const fresh = await redis.xReadGroup(
    streamConfig.group,
    consumerId,
    { key: streamConfig.name, id: '>' },
    { COUNT: streamConfig.batchSize, BLOCK: streamConfig.blockMs },
  )
  const messages = [
    ...(reclaimed?.messages ?? []),
    ...(fresh?.flatMap((stream) => stream.messages) ?? []),
  ]
  for (const message of messages) {
    await handleMessage({ pool, redis, streamConfig, log, message })
  }
  return messages.length
}
