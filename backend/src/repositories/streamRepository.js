export async function claimOutboxBatch(pool, options) {
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    await client.query(
      `UPDATE authorization_event_outbox
       SET status = 'pending', claimed_at = NULL, claimed_by = NULL,
           updated_at = clock_timestamp()
       WHERE status = 'publishing'
         AND claimed_at < clock_timestamp() - ($1::int * interval '1 millisecond')`,
      [options.claimIdleMs],
    )
    const result = await client.query(
      `WITH candidates AS (
         SELECT outbox_id FROM authorization_event_outbox
         WHERE status = 'pending' AND available_at <= clock_timestamp()
         ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT $1
       )
       UPDATE authorization_event_outbox AS outbox
       SET status = 'publishing', claimed_at = clock_timestamp(),
           claimed_by = $2, attempt_count = attempt_count + 1,
           updated_at = clock_timestamp()
       FROM candidates WHERE outbox.outbox_id = candidates.outbox_id
       RETURNING outbox.outbox_id, outbox.event_id, outbox.envelope,
                 outbox.attempt_count`,
      [options.batchSize, options.workerId],
    )
    await client.query('COMMIT')
    return result.rows
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {})
    throw error
  } finally {
    client.release()
  }
}

export async function markOutboxPublished(pool, outboxId, messageId) {
  await pool.query(
    `UPDATE authorization_event_outbox
     SET status = 'published', published_at = clock_timestamp(),
         stream_message_id = $2, claimed_at = NULL, claimed_by = NULL,
         last_error_code = NULL, updated_at = clock_timestamp()
     WHERE outbox_id = $1`,
    [outboxId, messageId],
  )
}

export async function markOutboxFailure(pool, options) {
  const exhausted = options.attemptCount >= options.maxAttempts
  await pool.query(
    `UPDATE authorization_event_outbox
     SET status = $2, available_at = clock_timestamp() + interval '2 seconds',
         claimed_at = NULL, claimed_by = NULL, last_error_code = $3,
         updated_at = clock_timestamp() WHERE outbox_id = $1`,
    [
      options.outboxId,
      exhausted ? 'dead_letter' : 'pending',
      options.errorCode,
    ],
  )
  return exhausted
}

export async function recordProcessingReceipt(pool, receipt) {
  const result = await pool.query(
    `INSERT INTO stream_processing_receipts (
       consumer_purpose, event_id, stream_message_id, envelope_hash
     ) VALUES ($1, $2, $3, $4)
     ON CONFLICT (consumer_purpose, event_id) DO NOTHING RETURNING event_id`,
    [
      receipt.consumerPurpose,
      receipt.eventId,
      receipt.streamMessageId,
      receipt.envelopeHash,
    ],
  )
  return result.rowCount === 1
}

export async function getStreamingEvidence(pool, eventId) {
  const result = await pool.query(
    `SELECT event.event_id, event.authorization_id,
       outbox.status AS outbox_status, outbox.attempt_count,
       outbox.stream_message_id, outbox.published_at,
       receipt.consumer_purpose, receipt.processed_at
     FROM authorization_events AS event
     LEFT JOIN authorization_event_outbox AS outbox USING (event_id)
     LEFT JOIN stream_processing_receipts AS receipt USING (event_id)
     WHERE event.event_id = $1`,
    [eventId],
  )
  return result.rows[0] ?? null
}
