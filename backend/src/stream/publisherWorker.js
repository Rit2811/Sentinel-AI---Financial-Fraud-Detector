import { performance } from 'node:perf_hooks'

import {
  lockPublicationBatch,
  completePublication,
  recordPublicationFailure,
} from '../repositories/streamRepository.js'
import { validateEnvelope } from './envelope.js'
import { publisherProfiler } from './publisherProfile.js'

async function boundedPublication(redis, streamConfig, envelope, timeoutMs) {
  const controller = new AbortController()
  let timer
  try {
    const command = redis.withCommandOptions
      ? redis.withCommandOptions({
          abortSignal: controller.signal,
          timeout: timeoutMs,
        })
      : redis
    return await Promise.race([
      command.xAdd(
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
      ),
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          controller.abort()
          // Cancellation cannot undo an accepted XADD. Closing the connection
          // prevents a queued command from being sent after the batch rolls back.
          if (redis.isOpen) redis.destroy()
          reject(new Error('stream_publish_timeout'))
        }, timeoutMs)
      }),
    ])
  } catch (error) {
    controller.abort()
    if (redis.isOpen) redis.destroy()
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export async function publishOutboxBatch({ pool, redis, streamConfig, log }) {
  const profile = publisherProfiler(log)
  const client = await pool.connect()
  let rows = []
  let activeRow = null
  let phase = 'lock'
  let destroyClient = false
  let released = false
  try {
    await client.query('BEGIN')
    await client.query(
      `SET LOCAL synchronous_commit=on; SET LOCAL lock_timeout='100ms'; SET LOCAL statement_timeout='500ms'; SET LOCAL idle_in_transaction_session_timeout='1500ms'`,
    )
    rows = await profile.measure('publisher_lock_total', null, () =>
      lockPublicationBatch(client, streamConfig),
    )
    const until = performance.now() + 200
    for (const row of rows) {
      activeRow = row
      phase = 'publish'
      const timeoutMs = Math.floor(until - performance.now())
      if (timeoutMs < 1) throw new Error('stream_publish_timeout')
      const envelope = validateEnvelope(row.envelope)
      const messageId = await profile.measure(
        'redis_publication',
        row.event_id,
        () => boundedPublication(redis, streamConfig, envelope, timeoutMs),
      )
      phase = 'outcome'
      await profile.measure('publisher_outcome_statement', row.event_id, () =>
        completePublication(client, row, messageId),
      )
    }
    phase = 'commit'
    await profile.measure(
      'publisher_batch_commit_ack',
      null,
      () => client.query('COMMIT'),
      rows.map((row) => row.event_id),
    )
    if (rows.length)
      log.info(
        { count: rows.length },
        'Authorization publication batch committed',
      )
    return rows.length
  } catch (error) {
    const rolledBack = await client.query('ROLLBACK').then(
      () => true,
      () => false,
    )
    destroyClient = !rolledBack || phase === 'commit'
    if (phase === 'commit' || !activeRow) throw error
    // Failure recovery borrows a connection after rollback; release this one
    // first so a bounded one-connection pool cannot wait on itself.
    client.release(destroyClient)
    released = true
    const errorCode =
      error?.message === 'invalid_stream_envelope'
        ? 'invalid_stream_envelope'
        : 'stream_publish_failed'
    await recordPublicationFailure(
      pool,
      activeRow,
      streamConfig.maxAttempts,
      errorCode,
    )
    log.error(
      {
        eventId: activeRow.event_id,
        errorCode,
        phase,
        failureType: error?.name,
        publicationTimeout: error?.message === 'stream_publish_timeout',
      },
      'Publication batch rolled back; canonical events remain recoverable',
    )
    return rows.length
  } finally {
    if (!released) client.release(destroyClient)
    if (rows.length) profile.flush()
  }
}
