import { randomUUID } from 'node:crypto'
import { fork } from 'node:child_process'
import { once } from 'node:events'

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

async function queuedEvents(count) {
  const events = Array.from({ length: count }, (_, i) =>
    sparkovReplay({
      event_id: randomUUID(),
      authorization_id: randomUUID(),
      occurred_at: `2019-01-01T00:00:${String(i).padStart(2, '0')}Z`,
    }),
  )
  for (const event of events) await ingest(event)
  return events
}

async function publishedIds() {
  return (await redis.xRange(streamConfig.name, '-', '+')).map(
    ({ message }) => JSON.parse(message.envelope).event_id,
  )
}

test('concurrent publishers cannot overtake the locked predecessor; batch is bounded to four', async () => {
  const events = await queuedEvents(5)
  let unblock
  let signal
  const blocked = new Promise((resolve) => {
    unblock = resolve
  })
  const entered = new Promise((resolve) => {
    signal = resolve
  })
  let first = true
  const slow = {
    xAdd: async (...args) => {
      if (first) {
        first = false
        signal()
        await blocked
      }
      return redis.xAdd(...args)
    },
  }
  const publication = publishOutboxBatch({ ...context, redis: slow })
  await entered
  try {
    expect(await publishOutboxBatch(context)).toBe(0)
  } finally {
    unblock()
  }
  expect(await publication).toBe(4)
  expect(await publishOutboxBatch(context)).toBe(1)
  expect(await publishedIds()).toEqual(events.map((e) => e.event_id))
})

test('failure after a successful prefix rolls back the whole batch and preserves retry order', async () => {
  const events = await queuedEvents(3)
  let sends = 0
  await publishOutboxBatch({
    ...context,
    redis: {
      xAdd: async (...args) => {
        if (++sends === 2) throw new Error('redis_unavailable')
        return redis.xAdd(...args)
      },
    },
  })
  expect(
    (
      await pool.query('SELECT status FROM authorization_event_outbox')
    ).rows.every((r) => r.status === 'pending'),
  ).toBe(true)
  // The deferred predecessor prevents a later event from overtaking it.
  expect(await publishOutboxBatch(context)).toBe(1)
  expect(await publishOutboxBatch(context)).toBe(0)
  await pool.query(
    `UPDATE authorization_event_outbox SET available_at=clock_timestamp()`,
  )
  expect(await publishOutboxBatch(context)).toBe(2)
  expect(await publishedIds()).toEqual([
    events[0].event_id,
    ...events.map((e) => e.event_id),
  ])
  expect(await consumeOnce(context)).toBe(4)
  expect(
    (
      await pool.query(
        'SELECT count(*)::int AS n FROM stream_processing_receipts',
      )
    ).rows[0].n,
  ).toBe(3)
})

test('accepted but uncertain Redis publication is retried with the identical canonical ID', async () => {
  const [event] = await queuedEvents(1)
  await publishOutboxBatch({
    ...context,
    redis: {
      xAdd: async (...args) => {
        await redis.xAdd(...args)
        throw new Error('reply_lost_after_acceptance')
      },
    },
  })
  expect(
    (await pool.query('SELECT status FROM authorization_event_outbox')).rows[0]
      .status,
  ).toBe('pending')
  await pool.query(
    `UPDATE authorization_event_outbox SET available_at=clock_timestamp()`,
  )
  await publishOutboxBatch(context)
  expect(await publishedIds()).toEqual([event.event_id, event.event_id])
  await consumeOnce(context)
  expect(
    (
      await pool.query(
        'SELECT count(*)::int AS n FROM stream_processing_receipts',
      )
    ).rows[0].n,
  ).toBe(1)
})

test('uncertain database COMMIT never regresses published rows', async () => {
  const [event] = await queuedEvents(1)
  const wrapper = {
    connect: async () => {
      const client = await pool.connect()
      return {
        release: (...args) => client.release(...args),
        query: async (...args) => {
          const result = await client.query(...args)
          if (args[0] === 'COMMIT') throw new Error('commit_ack_lost')
          return result
        },
      }
    },
  }
  await expect(
    publishOutboxBatch({ ...context, pool: wrapper }),
  ).rejects.toThrow('commit_ack_lost')
  expect(
    (await pool.query('SELECT status FROM authorization_event_outbox')).rows[0]
      .status,
  ).toBe('published')
  expect(await publishOutboxBatch(context)).toBe(0)
  expect(await publishedIds()).toEqual([event.event_id])
})

test('a stalled Redis command releases locks and leaves a durable retry state', async () => {
  await queuedEvents(1)
  const start = performance.now()
  await publishOutboxBatch({
    ...context,
    redis: { xAdd: () => new Promise(() => {}) },
  })
  expect(performance.now() - start).toBeLessThan(1500)
  expect(
    (
      await pool.query(
        'SELECT status,attempt_count FROM authorization_event_outbox',
      )
    ).rows[0],
  ).toEqual({ status: 'pending', attempt_count: 1 })
  const peer = await pool.connect()
  try {
    await peer.query('BEGIN')
    expect(
      (await peer.query('SELECT pg_try_advisory_xact_lock(1706,1) AS acquired'))
        .rows[0].acquired,
    ).toBe(true)
    await peer.query('ROLLBACK')
  } finally {
    peer.release()
  }
})

test('native Redis timeout closes the connection, rolls back, then reconnects and recovers', async () => {
  const [event] = await queuedEvents(1)
  const bounded = createClient({
    url: requireTestRedisUrl(process.env.TEST_REDIS_URL),
    disableOfflineQueue: true,
    socket: { connectTimeout: 1000, reconnectStrategy: false },
  })
  bounded.on('error', () => {})
  await bounded.connect()
  try {
    await redis.sendCommand(['CLIENT', 'PAUSE', '250', 'ALL'])
    await publishOutboxBatch({ ...context, redis: bounded })
    expect(bounded.isOpen).toBe(false)
    expect(
      (await pool.query('SELECT status FROM authorization_event_outbox'))
        .rows[0].status,
    ).toBe('pending')
    await bounded.connect()
    await pool.query(
      `UPDATE authorization_event_outbox SET available_at=clock_timestamp()`,
    )
    expect(await publishOutboxBatch({ ...context, redis: bounded })).toBe(1)
    expect(await publishedIds()).toEqual([event.event_id])
  } finally {
    if (bounded.isOpen) bounded.destroy()
  }
})

test('single publication can use the existing batch budget without premature cancellation', async () => {
  const [event] = await queuedEvents(1)
  const delayed = {
    get isOpen() {
      return redis.isOpen
    },
    destroy() {
      redis.destroy()
    },
    async xAdd(...args) {
      await new Promise((resolve) => setTimeout(resolve, 130))
      return redis.xAdd(...args)
    },
  }
  expect(await publishOutboxBatch({ ...context, redis: delayed })).toBe(1)
  expect(await publishedIds()).toEqual([event.event_id])
  expect(
    (
      await pool.query(
        'SELECT status,attempt_count FROM authorization_event_outbox',
      )
    ).rows[0],
  ).toEqual({ status: 'published', attempt_count: 1 })
})

test('real publisher death after Redis accepts and before COMMIT recovers the complete batch', async () => {
  const events = await queuedEvents(3)
  const child = fork(
    new URL('../publisherCrashChild.js', import.meta.url),
    [],
    {
      env: {
        ...process.env,
        CRASH_STREAM_CONFIG: JSON.stringify(streamConfig),
      },
      stdio: ['ignore', 'ignore', 'pipe', 'ipc'],
    },
  )
  let stderr = ''
  child.stderr.on('data', (chunk) => {
    stderr += chunk
  })
  const exited = once(child, 'exit')
  try {
    const boundary = await Promise.race([
      once(child, 'message').then(([message]) => message),
      exited.then(() => {
        throw new Error(`Child exited early: ${stderr}`)
      }),
    ])
    expect(boundary).toBe('before_commit')
    expect(await publishedIds()).toEqual(events.map((e) => e.event_id))
    expect(
      (
        await pool.query('SELECT status FROM authorization_event_outbox')
      ).rows.every((r) => r.status === 'pending'),
    ).toBe(true)
  } finally {
    child.kill('SIGKILL')
    await exited
  }
  expect(await publishOutboxBatch(context)).toBe(3)
  expect(await publishedIds()).toEqual(
    [...events, ...events].map((e) => e.event_id),
  )
  await consumeOnce(context)
  expect(
    (
      await pool.query(
        'SELECT count(*)::int AS n FROM stream_processing_receipts',
      )
    ).rows[0].n,
  ).toBe(3)
})
