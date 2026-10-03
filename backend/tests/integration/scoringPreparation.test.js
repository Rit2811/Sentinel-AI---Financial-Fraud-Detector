import { randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import pg from 'pg'
import { insertAcceptedEvent } from '../../src/repositories/authorizationEventRepository.js'
import { createScoringResultService } from '../../src/services/scoringResultService.js'
import { createReviewResolutionService } from '../../src/services/reviewResolutionService.js'
import {
  assertTestDatabase,
  requireTestDatabaseUrl,
} from '../databaseSafety.js'
import { sparkovReplay } from '../fixtures.js'

const url = requireTestDatabaseUrl(process.env.TEST_DATABASE_URL)
const client = new pg.Client({
  connectionString: url,
  statement_timeout: 10000,
})
const schema = `scoring_${randomUUID().replaceAll('-', '')}`
const runId = randomUUID()
let migration
let executionMigration
beforeAll(async () => {
  await client.connect()
  await assertTestDatabase(client)
  await client.query(`CREATE SCHEMA ${schema}`)
  await client.query(`SET search_path TO ${schema}`)
  for (const name of [
    '0001_authorization-event-ingestion.sql',
    '0002_reliable-event-streaming.sql',
    '0003_dashboard-query-indexes.sql',
    '0004_sparkov-replay-schema-v2.sql',
  ]) {
    const sql = await readFile(
      new URL(`../../migrations/${name}`, import.meta.url),
      'utf8',
    )
    await client.query(sql.split('-- Down Migration')[0])
  }
  migration = (
    await readFile(
      new URL(
        '../../migrations/0005_scoring-evidence-preparation.sql',
        import.meta.url,
      ),
      'utf8',
    )
  ).split('-- Down Migration')
  await client.query('BEGIN')
  await client.query(migration[0])
  executionMigration = (
    await readFile(
      new URL('../../migrations/0006_simulated-execution.sql', import.meta.url),
      'utf8',
    )
  ).split('-- Down Migration')
  await client.query(executionMigration[0])
  await client.query('COMMIT')
})
afterAll(async () => {
  try {
    await client.query('ROLLBACK')
    await assertTestDatabase(client)
    await client.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`)
  } finally {
    await client.end()
  }
})
async function job() {
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  await client.query(
    `INSERT INTO scoring_jobs (run_id, event_id, correlation_id, bundle_sha256, model_version, policy_version, feature_version, deadline_at)
    VALUES ($1, $2, $3, $4, 'FIXTURE_MODEL', 'FIXTURE_POLICY', 'sparkov-pit-v1', clock_timestamp() + interval '1 hour')`,
    [runId, event.event_id, randomUUID(), 'a'.repeat(64)],
  )
  return event
}
async function snapshot(event) {
  await client.query(
    `INSERT INTO scoring_feature_snapshots (run_id, event_id, feature_sha256, history_sequence,
    amount, hour, day_of_week, prior_count_1h, prior_count_24h, prior_sum_24h, prior_mean_24h, merchant_category)
    VALUES ($1, $2, $3, 0, 12.34, 0, 1, 0, 0, 0, 0, 'grocery_pos')`,
    [runId, event.event_id, 'b'.repeat(64)],
  )
}
async function result(
  event,
  probability = 0.1,
  action = 'Review',
  reason = 'review_region',
) {
  await client.query(
    `INSERT INTO scoring_results (run_id, event_id, probability, action, review_threshold,
    block_threshold, reason_code, inference_started_at, inference_finished_at, inference_ms)
    VALUES ($1, $2, $3, $4, 0.1, 0.9, $5, clock_timestamp() - interval '1 second', clock_timestamp(), 1)`,
    [runId, event.event_id, probability, action, reason],
  )
}

test('empty up/down/up preserves accepted v2 events', async () => {
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  for (const sql of [
    executionMigration[1],
    migration[1],
    migration[0],
    executionMigration[0],
  ]) {
    await client.query('BEGIN')
    await client.query(sql)
    await client.query('COMMIT')
  }
  expect(
    (
      await client.query(
        'SELECT sanitized_payload FROM authorization_events WHERE event_id = $1',
        [event.event_id],
      )
    ).rows[0].sanitized_payload,
  ).toEqual(event)
})

test('result and scored state must commit atomically; evidence is immutable', async () => {
  const event = await job()
  await snapshot(event)
  const complete = () =>
    client.query(
      `UPDATE scoring_jobs SET status = 'scored', retryable = false WHERE run_id = $1 AND event_id = $2`,
      [runId, event.event_id],
    )
  for (const write of [() => result(event), complete]) {
    await client.query('BEGIN')
    await write()
    await expect(client.query('COMMIT')).rejects.toThrow('commit atomically')
    await client.query('ROLLBACK')
  }
  await client.query('BEGIN')
  await result(event)
  await complete()
  await client.query('COMMIT')
  const service = createScoringResultService(client, runId)
  const first = await service.lookup(event.event_id)
  expect(first.action).toBe('Review')
  expect(first.probability).toBe(0.1)
  expect(first.execution_state).toBe('pending_review')
  expect(await service.lookup(event.event_id)).toEqual(first)
  await expect(result(event)).rejects.toMatchObject({ code: '23505' })
  await expect(
    client.query('UPDATE scoring_results SET probability = 0'),
  ).rejects.toThrow('immutable')
  await expect(
    client.query('DELETE FROM scoring_feature_snapshots'),
  ).rejects.toThrow('immutable')
})

test('retries cannot change assigned versions', async () => {
  const event = await job()
  await expect(
    client.query(
      `UPDATE scoring_jobs SET policy_version = 'NEW_POLICY' WHERE run_id = $1 AND event_id = $2`,
      [runId, event.event_id],
    ),
  ).rejects.toThrow('immutable')
  await client.query(
    'UPDATE scoring_jobs SET attempts = attempts + 1 WHERE run_id = $1 AND event_id = $2',
    [runId, event.event_id],
  )
  expect(
    (
      await client.query(
        'SELECT attempts FROM scoring_jobs WHERE run_id = $1 AND event_id = $2',
        [runId, event.event_id],
      )
    ).rows[0].attempts,
  ).toBe(1)
})

test('unknown and unassigned accepted events are truthful', async () => {
  const service = createScoringResultService(client, runId)
  expect(await service.lookup(randomUUID())).toBeNull()
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  const stored = await service.lookup(event.event_id)
  expect(stored.status).toBe('unavailable')
  expect(stored.reason_code).toBe('scoring_not_activated')
  expect(stored.probability).toBeNull()
})

test('probability, exact boundaries and forbidden raw columns are constrained', async () => {
  const event = await job()
  await snapshot(event)
  await expect(result(event, 0.1, 'Pass', 'below_review')).rejects.toThrow()
  await expect(result(event, NaN)).rejects.toThrow()
  await expect(result(event, 1.1)).rejects.toThrow()
  for (const column of ['cc_num', 'is_fraud']) {
    await expect(
      client.query(
        `INSERT INTO scoring_feature_snapshots (${column}) VALUES (1)`,
      ),
    ).rejects.toMatchObject({ code: '42703' })
  }
})

test('concurrent duplicate assignment creates one original job', async () => {
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  const peers = [
    new pg.Client({ connectionString: url, statement_timeout: 10000 }),
    new pg.Client({ connectionString: url, statement_timeout: 10000 }),
  ]
  try {
    for (const peer of peers) {
      await peer.connect()
      await peer.query(`SET search_path TO ${schema}`)
    }
    const writes = await Promise.all(
      peers.map((peer) =>
        peer.query(
          `INSERT INTO scoring_jobs
      (run_id, event_id, correlation_id, bundle_sha256, model_version, policy_version, feature_version, deadline_at)
      VALUES ($1, $2, $3, $4, 'FIXTURE_MODEL', 'FIXTURE_POLICY', 'sparkov-pit-v1', clock_timestamp() + interval '1 hour')
      ON CONFLICT (run_id, event_id) DO NOTHING`,
          [runId, event.event_id, randomUUID(), 'a'.repeat(64)],
        ),
      ),
    )
    expect(writes.map((write) => write.rowCount).sort()).toEqual([0, 1])
  } finally {
    await Promise.all(peers.map((peer) => peer.end()))
  }
})

test('expired fixture decision cannot commit as success', async () => {
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  await client.query(
    `INSERT INTO scoring_jobs (run_id, event_id, correlation_id, bundle_sha256, model_version, policy_version, feature_version, created_at, deadline_at)
    VALUES ($1, $2, $3, $4, 'FIXTURE_MODEL', 'FIXTURE_POLICY', 'sparkov-pit-v1', clock_timestamp() - interval '1 hour', clock_timestamp() - interval '1 second')`,
    [runId, event.event_id, randomUUID(), 'a'.repeat(64)],
  )
  await snapshot(event)
  await client.query('BEGIN')
  await result(event)
  await client.query(
    `UPDATE scoring_jobs SET status = 'scored', retryable = false WHERE run_id = $1 AND event_id = $2`,
    [runId, event.event_id],
  )
  await expect(client.query('COMMIT')).rejects.toThrow('Expired scoring')
  await client.query('ROLLBACK')
})

test('populated scoring evidence blocks downgrade', async () => {
  await expect(client.query(migration[1])).rejects.toThrow('Cannot downgrade')
})

test.each([
  [0.01, 'Pass', 'below_review', 'allowed'],
  [0.95, 'Block', 'block_region', 'rejected'],
])(
  'automatic %s execution commits once and preserves original action',
  async (p, action, reason, state) => {
    const event = await job()
    await snapshot(event)
    await client.query('BEGIN')
    await result(event, p, action, reason)
    await client.query(
      `UPDATE scoring_jobs SET status = 'scored', retryable = false WHERE run_id = $1 AND event_id = $2`,
      [runId, event.event_id],
    )
    await client.query('COMMIT')
    const stored = await createScoringResultService(client, runId).lookup(
      event.event_id,
    )
    expect(stored.execution_state).toBe(state)
    expect(stored.action).toBe(action)
    await expect(
      client.query(
        'UPDATE simulated_executions SET state = $1 WHERE event_id = $2',
        ['pending_review', event.event_id],
      ),
    ).rejects.toThrow('immutable')
    expect(
      (
        await client.query(
          'SELECT count(*)::int AS n FROM simulated_executions WHERE event_id = $1',
          [event.event_id],
        )
      ).rows[0].n,
    ).toBe(1)
  },
)

test('concurrent resolution executes once, retry returns original, decision stays Review', async () => {
  const event = await job()
  await snapshot(event)
  await client.query('BEGIN')
  await result(event)
  await client.query(
    `UPDATE scoring_jobs SET status = 'scored', retryable = false WHERE run_id = $1 AND event_id = $2`,
    [runId, event.event_id],
  )
  await client.query('COMMIT')
  const pool = new pg.Pool({
    connectionString: url,
    options: `-c search_path=${schema}`,
    max: 2,
  })
  try {
    const service = createReviewResolutionService(pool, runId)
    const input = {
      resolution_id: randomUUID(),
      resolution: 'allow',
      notes: 'Synthetic review fixture',
    }
    const resolutions = await Promise.all([
      service.resolve(event.event_id, 'fixture_reviewer', input),
      service.resolve(event.event_id, 'fixture_reviewer', input),
    ])
    expect(resolutions.map((r) => r.status).sort()).toEqual([200, 201])
    expect(
      (
        await service.resolve(event.event_id, 'fixture_reviewer', {
          ...input,
          resolution: 'reject',
        })
      ).status,
    ).toBe(409)
    const stored = await createScoringResultService(pool, runId).lookup(
      event.event_id,
    )
    expect(stored.action).toBe('Review')
    expect(stored.execution_state).toBe('allowed')
    expect(stored.review_resolution.reviewer_id).toBe('fixture_reviewer')
    expect(stored).not.toHaveProperty('is_fraud')
    await expect(
      client.query('DELETE FROM review_resolutions'),
    ).rejects.toThrow('immutable')
  } finally {
    await pool.end()
  }
})

test('expired processing cannot revive or produce a simulated action', async () => {
  const event = await job()
  await client.query(
    `UPDATE scoring_jobs SET status = 'expired', error_code = 'deadline_expired', retryable = false WHERE run_id = $1 AND event_id = $2`,
    [runId, event.event_id],
  )
  await expect(
    client.query(
      `UPDATE scoring_jobs SET status = 'scoring' WHERE run_id = $1 AND event_id = $2`,
      [runId, event.event_id],
    ),
  ).rejects.toThrow('immutable')
  const stored = await createScoringResultService(client, runId).lookup(
    event.event_id,
  )
  expect(stored.status).toBe('expired')
  expect(stored.probability).toBeNull()
  expect(stored.execution_state).toBe('not_executed')
})

test('deadline crossed after result INSERT but before COMMIT prevents all execution', async () => {
  const event = sparkovReplay({
    event_id: randomUUID(),
    authorization_id: randomUUID(),
  })
  await insertAcceptedEvent(client, event)
  await client.query(
    `INSERT INTO scoring_jobs (run_id, event_id, correlation_id, bundle_sha256, model_version, policy_version, feature_version, deadline_at)
    VALUES ($1, $2, $3, $4, 'FIXTURE_MODEL', 'FIXTURE_POLICY', 'sparkov-pit-v1', clock_timestamp() + interval '2 seconds')`,
    [runId, event.event_id, randomUUID(), 'a'.repeat(64)],
  )
  await snapshot(event)
  await client.query('BEGIN')
  await result(event)
  await client.query(
    `UPDATE scoring_jobs SET status = 'scored', retryable = false WHERE run_id = $1 AND event_id = $2`,
    [runId, event.event_id],
  )
  await client.query('SELECT pg_sleep(2.1)')
  await expect(client.query('COMMIT')).rejects.toThrow(
    'expired simulated execution',
  )
  await client.query('ROLLBACK')
  const stored = await createScoringResultService(client, runId).lookup(
    event.event_id,
  )
  expect(stored.probability).toBeNull()
  expect(stored.execution_state).toBe('not_executed')
})
