import { randomUUID } from 'node:crypto'

import pg from 'pg'
import request from 'supertest'

import { createApp } from '../../src/app.js'
import { recordProcessingReceipt } from '../../src/repositories/streamRepository.js'
import { sha256 } from '../../src/services/hashing.js'
import { cardNotPresent } from '../fixtures.js'

const { Pool } = pg
const connectionString =
  process.env.TEST_DATABASE_URL ??
  process.env.DATABASE_URL ??
  'postgresql://sentinel:sentinel_local_only@127.0.0.1:15432/sentinel'
const pool = new Pool({ connectionString, max: 20 })
const log = { info() {}, warn() {}, error() {} }

const app = createApp({ pool, log })

function uniqueEvent(overrides = {}) {
  return cardNotPresent({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
    ...overrides,
  })
}

function post(event, key = randomUUID(), correlation = randomUUID()) {
  return request(app)
    .post('/api/v1/authorization-events')
    .set('Content-Type', 'application/json')
    .set('Idempotency-Key', key)
    .set('X-Correlation-ID', correlation)
    .send(event)
}

beforeEach(async () => {
  await pool.query(
    'TRUNCATE stream_processing_receipts, authorization_event_outbox, quarantined_events, ingestion_attempts, idempotency_records, authorization_events',
  )
})

afterAll(async () => {
  await pool.end()
})

describe('PostgreSQL authorization ingestion', () => {
  test('atomically accepts, replays and conflicts without a second event', async () => {
    const event = uniqueEvent()
    const key = randomUUID()
    const accepted = await post(event, key)
    expect(accepted.status).toBe(202)
    expect(accepted.body.outcome).toBe('accepted')

    const replay = await post(event, key)
    expect(replay.status).toBe(200)
    expect(replay.body.outcome).toBe('duplicate')
    expect(replay.headers['idempotent-replayed']).toBe('true')
    expect(replay.body.ingestion_id).toBe(accepted.body.ingestion_id)

    const conflict = await post(
      { ...event, amount_minor: event.amount_minor + 1 },
      key,
    )
    expect(conflict.status).toBe(409)
    expect(conflict.body.code).toBe('idempotency_conflict')

    const counts = await pool.query(
      `SELECT
         (SELECT count(*)::int FROM authorization_events) AS events,
         (SELECT count(*)::int FROM idempotency_records) AS idempotency_records,
         (SELECT count(*)::int FROM authorization_event_outbox) AS outbox`,
    )
    expect(counts.rows[0]).toEqual({
      events: 1,
      idempotency_records: 1,
      outbox: 1,
    })
  })

  test('stores a future semantic event only in quarantine', async () => {
    const event = uniqueEvent({ occurred_at: '2099-01-01T00:00:00.000Z' })
    const response = await post(event)
    expect(response.status).toBe(202)
    expect(response.body.outcome).toBe('quarantined')
    expect(response.body.reason_codes).toEqual([
      'occurred_at_too_far_in_future',
    ])

    const counts = await pool.query(
      `SELECT
         (SELECT count(*)::int FROM authorization_events) AS events,
         (SELECT count(*)::int FROM quarantined_events) AS quarantines,
         (SELECT count(*)::int FROM authorization_event_outbox) AS outbox`,
    )
    expect(counts.rows[0]).toEqual({ events: 0, quarantines: 1, outbox: 0 })
  })

  test('concurrent identical requests create exactly one event', async () => {
    const event = uniqueEvent()
    const key = randomUUID()
    const responses = await Promise.all(
      Array.from({ length: 6 }, () => post(event, key)),
    )
    expect(responses.map(({ status }) => status).sort()).toEqual([
      200, 200, 200, 200, 200, 202,
    ])

    const count = await pool.query(
      'SELECT count(*)::int AS count FROM authorization_events',
    )
    expect(count.rows[0].count).toBe(1)
  })

  test('concurrent different payloads resolve to one accept and one conflict', async () => {
    const event = uniqueEvent()
    const key = randomUUID()
    const responses = await Promise.all([
      post(event, key),
      post({ ...event, amount_minor: event.amount_minor + 1 }, key),
    ])
    expect(responses.map(({ status }) => status).sort()).toEqual([202, 409])

    const count = await pool.query(
      'SELECT count(*)::int AS count FROM authorization_events',
    )
    expect(count.rows[0].count).toBe(1)
  })

  test('rolls back idempotency claim and event on a database constraint failure', async () => {
    const first = uniqueEvent()
    expect((await post(first)).status).toBe(202)

    const rollbackKey = randomUUID()
    const conflictingIdentity = uniqueEvent({
      authorization_id: first.authorization_id,
    })
    const response = await post(conflictingIdentity, rollbackKey)
    expect(response.status).toBe(503)
    expect(response.body.code).toBe('dependency_unavailable')

    const evidence = await pool.query(
      `SELECT
         (SELECT count(*)::int FROM authorization_events WHERE event_id = $1) AS events,
         (SELECT count(*)::int FROM idempotency_records WHERE key_hash = $2) AS claims,
         (SELECT count(*)::int FROM authorization_event_outbox WHERE event_id = $1) AS outbox`,
      [conflictingIdentity.event_id, sha256(rollbackKey)],
    )
    expect(evidence.rows[0]).toEqual({ events: 0, claims: 0, outbox: 0 })
  })

  test('database trigger prevents mutation of accepted events', async () => {
    const event = uniqueEvent()
    expect((await post(event)).status).toBe(202)
    await expect(
      pool.query(
        'UPDATE authorization_events SET amount_minor = amount_minor + 1 WHERE event_id = $1',
        [event.event_id],
      ),
    ).rejects.toThrow('Task 3 event records are immutable')
  })

  test('deduplicates a repeated downstream effect by purpose and event', async () => {
    const event = uniqueEvent()
    expect((await post(event)).status).toBe(202)
    const receipt = {
      consumerPurpose: 'integration-proof',
      eventId: event.event_id,
      streamMessageId: '1-0',
      envelopeHash: '0'.repeat(64),
    }
    expect(await recordProcessingReceipt(pool, receipt)).toBe(true)
    expect(
      await recordProcessingReceipt(pool, {
        ...receipt,
        streamMessageId: '2-0',
      }),
    ).toBe(false)
    const count = await pool.query(
      'SELECT count(*)::int AS count FROM stream_processing_receipts WHERE event_id = $1',
      [event.event_id],
    )
    expect(count.rows[0].count).toBe(1)
  })
})
