import { randomUUID } from 'node:crypto'

import pg from 'pg'
import { createClient } from 'redis'

import { createAuthorizationIngestionService } from '../../src/services/authorizationIngestionService.js'
import { publishOutboxBatch } from '../../src/stream/publisherWorker.js'
import {
  consumeOnce,
  ensureConsumerGroup,
} from '../../src/stream/consumerWorker.js'
import {
  assertTestDatabase,
  requireTestDatabaseUrl,
  requireTestRedisUrl,
} from '../databaseSafety.js'
import { cardNotPresent, sparkovReplay } from '../fixtures.js'

const pool = new pg.Pool({
  connectionString: requireTestDatabaseUrl(process.env.TEST_DATABASE_URL),
  connectionTimeoutMillis: 5000,
  statement_timeout: 10000,
})
const redis = createClient({
  url: requireTestRedisUrl(process.env.TEST_REDIS_URL),
  socket: { connectTimeout: 5000, reconnectStrategy: false },
})
redis.on('error', () => {})
const log = { info() {}, warn() {}, error() {} }
const ingestion = createAuthorizationIngestionService(pool, log)
let streamConfig
let context

beforeAll(async () => {
  await assertTestDatabase(pool)
  await redis.connect()
})

beforeEach(async () => {
  await assertTestDatabase(pool)
  await pool.query(
    'TRUNCATE scoring_predictions, scoring_attempt_audit, scoring_history, scoring_delivery_failures, scoring_worker_health, scoring_runs, review_resolutions, simulated_executions, scoring_results, scoring_feature_snapshots, scoring_jobs, stream_processing_receipts, authorization_event_outbox, quarantined_events, ingestion_attempts, idempotency_records, authorization_events',
  )
  const name = `task4-test:${randomUUID()}`
  streamConfig = {
    name,
    deadLetterName: `${name}:dead-letter`,
    group: 'test-group',
    consumerPurpose: 'task4-test-proof',
    batchSize: 10,
    blockMs: 1,
    claimIdleMs: 0,
    maxAttempts: 2,
    retention: 100,
  }
  context = { pool, redis, streamConfig, log }
  await ensureConsumerGroup(redis, streamConfig)
})

afterEach(async () => {
  if (redis.isReady && streamConfig) {
    await redis.del([
      streamConfig.name,
      streamConfig.deadLetterName,
      `${streamConfig.name}:retry-counts`,
    ])
  }
})

afterAll(async () => {
  if (redis.isOpen) redis.destroy()
  await pool.end()
})

async function ingest(event) {
  const result = await ingestion.ingest({
    event,
    idempotencyKey: randomUUID(),
    correlationId: randomUUID(),
    quarantineReasonCodes: [],
  })
  expect(result.status).toBe(202)
}

async function receipt(eventId) {
  return (
    await pool.query(
      'SELECT * FROM stream_processing_receipts WHERE event_id = $1',
      [eventId],
    )
  ).rows[0]
}

test('v1 and v2 reach Redis and durable receipts; duplicate delivery keeps the first receipt', async () => {
  const v2 = sparkovReplay()
  await ingest(cardNotPresent())
  await ingest(v2)
  expect(await publishOutboxBatch(context)).toBe(2)
  const messages = await redis.xRange(streamConfig.name, '-', '+')
  expect(messages).toHaveLength(2)
  const replay = messages.find(
    ({ message }) => JSON.parse(message.envelope).schema_version === '2.0',
  )
  expect(Object.keys(JSON.parse(replay.message.envelope)).sort()).toEqual([
    'authorization_id',
    'correlation_id',
    'data_origin',
    'event_id',
    'occurred_at',
    'schema_version',
  ])
  expect(JSON.parse(replay.message.envelope).data_origin).toBe('sparkov_replay')
  expect(await consumeOnce(context)).toBe(2)
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(0)
  const original = await receipt(v2.event_id)
  expect(original.stream_message_id).toBe(replay.id)
  expect(await receipt(cardNotPresent().event_id)).toBeDefined()
  await redis.xAdd(streamConfig.name, '*', replay.message)
  expect(await consumeOnce(context)).toBe(1)
  expect(await receipt(v2.event_id)).toEqual(original)
  expect(
    (
      await pool.query('SELECT status FROM authorization_event_outbox')
    ).rows.every(({ status }) => status === 'published'),
  ).toBe(true)
})

test('an abandoned v2 pending message is reclaimed and acknowledged after receipt commit', async () => {
  const event = sparkovReplay()
  await ingest(event)
  await publishOutboxBatch(context)
  await redis.xReadGroup(
    streamConfig.group,
    'abandoned-consumer',
    { key: streamConfig.name, id: '>' },
    { COUNT: 1 },
  )
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(1)
  expect(await receipt(event.event_id)).toBeUndefined()
  expect(
    await consumeOnce({ ...context, consumerId: 'replacement-consumer' }),
  ).toBe(1)
  expect(await receipt(event.event_id)).toBeDefined()
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(0)
})

test('receipt commit followed by ACK failure is recovered without another effect', async () => {
  const event = sparkovReplay()
  await ingest(event)
  await publishOutboxBatch(context)
  const failingAck = {
    xAutoClaim: redis.xAutoClaim.bind(redis),
    xReadGroup: redis.xReadGroup.bind(redis),
    hIncrBy: redis.hIncrBy.bind(redis),
    xAck: async () => {
      throw new Error('simulated_ack_disconnect')
    },
  }
  await consumeOnce({ ...context, redis: failingAck })
  const original = await receipt(event.event_id)
  expect(original).toBeDefined()
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(1)
  await consumeOnce(context)
  expect(await receipt(event.event_id)).toEqual(original)
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(0)
})

test('missing FK leaves the message pending, then dead-letters with no receipt', async () => {
  const event = sparkovReplay()
  const envelope = {
    event_id: event.event_id,
    authorization_id: event.authorization_id,
    correlation_id: randomUUID(),
    schema_version: '2.0',
    data_origin: 'sparkov_replay',
    occurred_at: event.occurred_at,
  }
  await redis.xAdd(streamConfig.name, '*', {
    envelope: JSON.stringify(envelope),
  })
  await consumeOnce(context)
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(1)
  expect(await receipt(event.event_id)).toBeUndefined()
  await consumeOnce(context)
  expect(
    (await redis.xPending(streamConfig.name, streamConfig.group)).pending,
  ).toBe(0)
  expect(await redis.xLen(streamConfig.deadLetterName)).toBe(1)
  expect(await receipt(event.event_id)).toBeUndefined()
})

test('publisher retries a failed send and reclaims a lost publishing claim', async () => {
  const event = sparkovReplay()
  await ingest(event)
  await publishOutboxBatch({
    ...context,
    redis: {
      xAdd: async () => {
        throw new Error('simulated_send_disconnect')
      },
    },
  })
  const failed = (
    await pool.query(
      'SELECT status, attempt_count FROM authorization_event_outbox',
    )
  ).rows[0]
  expect(failed).toEqual({ status: 'pending', attempt_count: 1 })
  await pool.query(
    "UPDATE authorization_event_outbox SET status = 'publishing', claimed_at = clock_timestamp() - interval '1 minute', claimed_by = 'abandoned-publisher'",
  )
  await pool.query(
    "UPDATE authorization_event_outbox SET available_at = clock_timestamp() - interval '1 second'",
  )
  expect(await publishOutboxBatch(context)).toBe(1)
  expect(await consumeOnce(context)).toBe(1)
  expect(await receipt(event.event_id)).toBeDefined()
})
