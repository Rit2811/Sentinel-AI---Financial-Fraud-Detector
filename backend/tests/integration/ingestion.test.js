import { randomUUID } from 'node:crypto'

import pg from 'pg'
import request from 'supertest'

import { createApp } from '../../src/app.js'
import { recordProcessingReceipt } from '../../src/repositories/streamRepository.js'
import { sha256 } from '../../src/services/hashing.js'
import { createAuthorizationIngestionService } from '../../src/services/authorizationIngestionService.js'
import { cardNotPresent, sparkovReplay } from '../fixtures.js'
import {
  assertTestDatabase,
  requireTestDatabaseUrl,
} from '../databaseSafety.js'

const { Pool } = pg
const connectionString = requireTestDatabaseUrl(process.env.TEST_DATABASE_URL)
const pool = new Pool({
  connectionString,
  max: 20,
  connectionTimeoutMillis: 5000,
  statement_timeout: 10000,
})
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
  await assertTestDatabase(pool)
  await pool.query(
    'TRUNCATE scoring_predictions, scoring_attempt_audit, scoring_history, scoring_delivery_failures, scoring_worker_health, scoring_runs, review_resolutions, simulated_executions, scoring_results, scoring_feature_snapshots, scoring_jobs, stream_processing_receipts, authorization_event_outbox, quarantined_events, ingestion_attempts, idempotency_records, authorization_events',
  )
})

afterAll(async () => {
  await pool.end()
})

describe('PostgreSQL authorization ingestion', () => {
  test('v2 commits the linked audit, outbox and receipt in four database calls', async () => {
    const calls = []
    const observedPool = {
      async connect() {
        const client = await pool.connect()
        return {
          query(sql, values) {
            calls.push(sql)
            return client.query(sql, values)
          },
          release: () => client.release(),
        }
      },
    }
    const event = sparkovReplay()
    const key = randomUUID()
    const correlationId = randomUUID()
    const result = await createAuthorizationIngestionService(
      observedPool,
      log,
    ).ingest({
      event,
      idempotencyKey: key,
      correlationId,
      quarantineReasonCodes: [],
    })
    expect(result.status).toBe(202)
    expect(calls).toHaveLength(4)
    expect(calls[0]).toBe('BEGIN')
    expect(calls[3]).toBe('COMMIT')
    const saved = (
      await pool.query(
        `SELECT a.ingestion_id,a.correlation_id,a.outcome,a.received_at,
              o.envelope,i.response_body,i.response_status,i.status
       FROM ingestion_attempts a
       JOIN authorization_event_outbox o ON o.event_id=a.event_id
       JOIN idempotency_records i ON i.key_hash=a.key_hash
       WHERE a.event_id=$1`,
        [event.event_id],
      )
    ).rows[0]
    expect(saved.ingestion_id).toBe(result.body.ingestion_id)
    expect(saved.correlation_id).toBe(correlationId)
    expect(saved.outcome).toBe('accepted')
    expect(saved.received_at.toISOString()).toBe(result.body.received_at)
    expect(saved.envelope.event_id).toBe(event.event_id)
    expect(saved.envelope.correlation_id).toBe(correlationId)
    expect(saved.response_body).toEqual(result.body)
    expect(saved.response_status).toBe(202)
    expect(saved.status).toBe('completed')
  })

  test.each([
    ['outbox constraint', 20, '[]'],
    ['audit constraint', 22, null],
    ['receipt constraint', 26, null],
    ['missing claimed receipt', 23, 'a'.repeat(64)],
  ])(
    'v2 rolls back every write after %s failure',
    async (_, index, replacement) => {
      const faultyPool = {
        async connect() {
          const client = await pool.connect()
          return {
            query(sql, values) {
              if (sql.startsWith('WITH accepted AS')) {
                values = [...values]
                values[index] = replacement
              }
              return client.query(sql, values)
            },
            release: () => client.release(),
          }
        },
      }
      const event = sparkovReplay()
      const key = randomUUID()
      await expect(
        createAuthorizationIngestionService(faultyPool, log).ingest({
          event,
          idempotencyKey: key,
          correlationId: randomUUID(),
          quarantineReasonCodes: [],
        }),
      ).rejects.toThrow()
      const counts = (
        await pool.query(
          `SELECT
         (SELECT count(*)::int FROM authorization_events) AS events,
         (SELECT count(*)::int FROM authorization_event_outbox) AS outbox,
         (SELECT count(*)::int FROM ingestion_attempts) AS audit,
         (SELECT count(*)::int FROM idempotency_records) AS receipts`,
        )
      ).rows[0]
      expect(counts).toEqual({ events: 0, outbox: 0, audit: 0, receipts: 0 })
      expect((await post(event, key)).status).toBe(202)
    },
  )

  test('persists v2 without inferred facts and preserves mixed-version totals', async () => {
    const event = sparkovReplay()
    const key = randomUUID()
    const accepted = await post(event, key)
    expect(accepted.status).toBe(202)
    expect(accepted.body.schema_version).toBe('2.0')
    const replay = await post(event, key)
    expect(replay.status).toBe(200)
    expect(replay.body.ingestion_id).toBe(accepted.body.ingestion_id)
    expect(
      (await post({ ...event, amount_minor: event.amount_minor + 1 }, key))
        .status,
    ).toBe(409)
    expect((await post(uniqueEvent())).status).toBe(202)
    const saved = (
      await pool.query(
        'SELECT * FROM authorization_events WHERE event_id = $1',
        [event.event_id],
      )
    ).rows[0]
    expect(saved.sanitized_payload).toEqual(event)
    for (const field of [
      'channel',
      'account_token',
      'merchant_country',
      'entry_mode',
      'terminal_token',
      'device_token',
    ]) {
      expect(saved[field]).toBeNull()
    }
    expect(saved.merchant_category).toBe(event.merchant_category)
    expect(saved.time_basis).toBe(event.time_basis)
    expect(saved.currency_basis).toBe(event.currency_basis)
    expect(
      (
        await pool.query(
          'SELECT count(*)::int AS count FROM authorization_event_outbox WHERE event_id = $1',
          [event.event_id],
        )
      ).rows[0].count,
    ).toBe(1)
    const dashboard = await request(app).get('/api/v1/dashboard')
    expect(dashboard.body.summary.total_events).toBe(2)
    expect(dashboard.body.channels).toEqual({
      card_present: 0,
      card_not_present: 1,
    })
    await expect(
      pool.query('DELETE FROM authorization_events WHERE event_id = $1', [
        event.event_id,
      ]),
    ).rejects.toThrow('immutable')
  })

  test('v2 quarantine creates no outbox and cannot be mutated', async () => {
    const event = sparkovReplay({ occurred_at: '2099-01-01T00:00:00Z' })
    const response = await post(event)
    expect(response.status).toBe(202)
    expect(response.body.outcome).toBe('quarantined')
    expect(
      (
        await pool.query(
          'SELECT count(*)::int AS count FROM authorization_event_outbox',
        )
      ).rows[0].count,
    ).toBe(0)
    expect(
      (await pool.query('SELECT sanitized_payload FROM quarantined_events'))
        .rows[0].sanitized_payload,
    ).toEqual(event)
    await expect(
      pool.query('DELETE FROM quarantined_events WHERE event_id = $1', [
        event.event_id,
      ]),
    ).rejects.toThrow('immutable')
  })

  test('concurrent v2 replay commits only one event and outbox row', async () => {
    const event = sparkovReplay()
    const key = randomUUID()
    const responses = await Promise.all(
      Array.from({ length: 4 }, () => post(event, key)),
    )
    expect(responses.map(({ status }) => status).sort()).toEqual([
      200, 200, 200, 202,
    ])
    expect(
      (
        await pool.query(
          'SELECT count(*)::int AS count FROM authorization_event_outbox',
        )
      ).rows[0].count,
    ).toBe(1)
  })

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

  test('returns only aggregate live dashboard data', async () => {
    const event = uniqueEvent()
    expect((await post(event)).status).toBe(202)
    await recordProcessingReceipt(pool, {
      consumerPurpose: 'dashboard-proof',
      eventId: event.event_id,
      streamMessageId: 'dashboard-1-0',
      envelopeHash: '1'.repeat(64),
    })

    const response = await request(app).get('/api/v1/dashboard?range=1h')

    expect(response.status).toBe(200)
    expect(response.headers['cache-control']).toBe('no-store')
    expect(response.body.range).toBe('1h')
    expect(response.body.summary.total_events).toBe(1)
    expect(response.body.summary.processed_events).toBe(1)
    expect(
      response.body.activity.reduce(
        (total, bucket) => total + bucket.ingested,
        0,
      ),
    ).toBe(1)
    expect(JSON.stringify(response.body)).not.toContain(event.card_token)
    expect(JSON.stringify(response.body)).not.toContain(event.account_token)
  })
})
