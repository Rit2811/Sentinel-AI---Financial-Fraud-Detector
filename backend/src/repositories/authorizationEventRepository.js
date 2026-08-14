import crypto from 'node:crypto'

export async function claimIdempotency(client, keyHash, payloadHash) {
  const result = await client.query(
    `INSERT INTO idempotency_records (key_hash, payload_hash, status)
     VALUES ($1, $2, 'processing')
     ON CONFLICT (key_hash) DO NOTHING
     RETURNING key_hash`,
    [keyHash, payloadHash],
  )
  return result.rowCount === 1
}

export async function getIdempotencyRecord(client, keyHash) {
  const result = await client.query(
    `SELECT payload_hash, status, response_status, response_body
     FROM idempotency_records WHERE key_hash = $1`,
    [keyHash],
  )
  return result.rows[0]
}

export async function completeIdempotency(client, keyHash, status, body) {
  await client.query(
    `UPDATE idempotency_records
     SET status = 'completed', response_status = $2, response_body = $3::jsonb,
         completed_at = clock_timestamp()
     WHERE key_hash = $1`,
    [keyHash, status, JSON.stringify(body)],
  )
}

export async function insertAcceptedEvent(client, event) {
  await client.query(
    `INSERT INTO authorization_events (
       event_id, authorization_id, occurred_at, schema_version, data_origin, channel,
       amount_minor, currency, card_token, account_token, merchant_id, merchant_country,
       entry_mode, terminal_token, device_token, sanitized_payload
     ) VALUES (
       $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb
     )`,
    [
      event.event_id,
      event.authorization_id,
      event.occurred_at,
      event.schema_version,
      event.data_origin,
      event.channel,
      event.amount_minor,
      event.currency,
      event.card_token,
      event.account_token,
      event.merchant_id,
      event.merchant_country,
      event.entry_mode,
      event.terminal_token ?? null,
      event.device_token ?? null,
      JSON.stringify(event),
    ],
  )
}

export async function insertOutboxEvent(client, event, correlationId) {
  const envelope = {
    event_id: event.event_id,
    authorization_id: event.authorization_id,
    correlation_id: correlationId,
    schema_version: event.schema_version,
    data_origin: event.data_origin,
    occurred_at: event.occurred_at,
  }
  await client.query(
    `INSERT INTO authorization_event_outbox (outbox_id, event_id, envelope)
     VALUES ($1, $2, $3::jsonb)`,
    [crypto.randomUUID(), event.event_id, JSON.stringify(envelope)],
  )
}

export async function insertQuarantinedEvent(
  client,
  quarantineId,
  event,
  reasonCodes,
) {
  await client.query(
    `INSERT INTO quarantined_events
       (quarantine_id, event_id, sanitized_payload, reason_codes)
     VALUES ($1, $2, $3::jsonb, $4::text[])`,
    [quarantineId, event.event_id, JSON.stringify(event), reasonCodes],
  )
}

export async function insertAttempt(client, attempt) {
  await client.query(
    `INSERT INTO ingestion_attempts (
       ingestion_id, event_id, correlation_id, key_hash, payload_hash,
       outcome, reason_codes, received_at
     ) VALUES ($1, $2, $3, $4, $5, $6, $7::text[], $8)`,
    [
      attempt.ingestionId,
      attempt.eventId,
      attempt.correlationId,
      attempt.keyHash,
      attempt.payloadHash,
      attempt.outcome,
      attempt.reasonCodes,
      attempt.receivedAt,
    ],
  )
}

export async function insertRejectedAttempt(pool, attempt) {
  await pool.query(
    `INSERT INTO ingestion_attempts (
       ingestion_id, event_id, correlation_id, key_hash, payload_hash,
       outcome, reason_codes, received_at
     ) VALUES ($1, NULL, $2, $3, NULL, $4, $5::text[], $6)`,
    [
      attempt.ingestionId,
      attempt.correlationId,
      attempt.keyHash,
      attempt.outcome,
      attempt.reasonCodes,
      attempt.receivedAt,
    ],
  )
}
