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
    if (options.profile)
      await options.profile.measure('publisher_claim_commit_ack', null, () =>
        client.query('COMMIT'),
      )
    else await client.query('COMMIT')
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

export async function lockPublicationBatch(client, options) {
  // One transaction-scoped fence prevents concurrent publishers skipping a
  // locked predecessor and reversing publication order. No wait to fill a batch.
  const fence = await client.query(
    'SELECT pg_try_advisory_xact_lock(1706, 1) AS acquired',
  )
  if (!fence.rows[0].acquired) return []
  const result = await client.query(
    `SELECT o.outbox_id, o.event_id, o.envelope, o.attempt_count,
            o.status, o.available_at <= clock_timestamp() AS available,
            o.claimed_at < clock_timestamp() - ($2::int * interval '1 millisecond') AS abandoned
     FROM authorization_event_outbox o JOIN authorization_events e USING(event_id)
     WHERE o.status IN ('pending','publishing')
     ORDER BY e.created_at, e.event_id
     LIMIT $1 FOR UPDATE OF o`,
    [Math.max(1, Math.min(options.batchSize, 4)), options.claimIdleMs],
  )
  const rows = []
  for (const row of result.rows) {
    if (!row.available || (row.status === 'publishing' && !row.abandoned)) break
    rows.push(row)
  }
  return rows
}

export async function completePublication(client, row, messageId) {
  await client.query(
    `UPDATE authorization_event_outbox
     SET status='published', attempt_count=attempt_count+1,
         published_at=clock_timestamp(), stream_message_id=$2,
         claimed_at=NULL, claimed_by=NULL, last_error_code=NULL,
         updated_at=clock_timestamp() WHERE outbox_id=$1`,
    [row.outbox_id, messageId],
  )
}

export async function recordPublicationFailure(
  pool,
  row,
  maxAttempts,
  errorCode,
) {
  // After rollback, compare-and-set cannot undo another publisher's successful
  // commit. A lost failure record still leaves the original event retryable.
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    await client.query(
      `SET LOCAL synchronous_commit=on; SET LOCAL lock_timeout='100ms'; SET LOCAL statement_timeout='500ms'`,
    )
    await client.query(
      `UPDATE authorization_event_outbox
       SET attempt_count=attempt_count+1,
           status=CASE WHEN attempt_count+1 >= $3 THEN 'dead_letter' ELSE 'pending' END,
           available_at=clock_timestamp()+interval '2 seconds',
           claimed_at=NULL, claimed_by=NULL, last_error_code=$4,
           updated_at=clock_timestamp()
       WHERE outbox_id=$1 AND attempt_count=$2 AND status IN ('pending','publishing')`,
      [row.outbox_id, row.attempt_count, maxAttempts, errorCode],
    )
    await client.query('COMMIT')
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {})
    throw error
  } finally {
    client.release()
  }
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
