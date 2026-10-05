import { randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'

import pg from 'pg'

import {
  insertAcceptedEvent,
  insertOutboxEvent,
} from '../../src/repositories/authorizationEventRepository.js'
import { recordProcessingReceipt } from '../../src/repositories/streamRepository.js'
import {
  assertTestDatabase,
  requireTestDatabaseUrl,
} from '../databaseSafety.js'
import { cardNotPresent, sparkovReplay } from '../fixtures.js'

const client = new pg.Client({
  connectionString: requireTestDatabaseUrl(process.env.TEST_DATABASE_URL),
  connectionTimeoutMillis: 5000,
  statement_timeout: 10000,
})
const schema = `migration_${randomUUID().replaceAll('-', '')}`
let migration

beforeAll(async () => {
  await client.connect()
  await assertTestDatabase(client)
  await client.query(`CREATE SCHEMA ${schema}`)
  await client.query(`SET search_path TO ${schema}`)
  for (const file of [
    '0001_authorization-event-ingestion.sql',
    '0002_reliable-event-streaming.sql',
    '0003_dashboard-query-indexes.sql',
  ]) {
    const sql = await readFile(
      new URL(`../../migrations/${file}`, import.meta.url),
      'utf8',
    )
    await client.query(sql.split('-- Down Migration')[0])
  }
  migration = (
    await readFile(
      new URL(
        '../../migrations/0004_sparkov-replay-schema-v2.sql',
        import.meta.url,
      ),
      'utf8',
    )
  ).split('-- Down Migration')
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

async function migrate(sql) {
  await client.query('BEGIN')
  try {
    await client.query(sql)
    await client.query('COMMIT')
  } catch (error) {
    await client.query('ROLLBACK')
    throw error
  }
}

async function snapshot() {
  const result = {}
  for (const table of [
    'authorization_events',
    'authorization_event_outbox',
    'stream_processing_receipts',
    'quarantined_events',
    'idempotency_records',
    'ingestion_attempts',
  ]) {
    result[table] = (
      await client.query(
        `SELECT to_jsonb(record) - ARRAY['merchant_category', 'time_basis', 'currency_basis'] AS value FROM ${table} AS record`,
      )
    ).rows
  }
  return result
}

test('up/down/up preserves v1 audit rows, FKs, receipts and immutable triggers', async () => {
  const v1 = cardNotPresent()
  await client.query(
    `INSERT INTO authorization_events (
    event_id, authorization_id, occurred_at, schema_version, data_origin, channel,
    amount_minor, currency, card_token, account_token, merchant_id, merchant_country,
    entry_mode, device_token, sanitized_payload
  ) VALUES ($1, $2, $3, '1.0', 'synthetic_enriched', $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
    [
      v1.event_id,
      v1.authorization_id,
      v1.occurred_at,
      v1.channel,
      v1.amount_minor,
      v1.currency,
      v1.card_token,
      v1.account_token,
      v1.merchant_id,
      v1.merchant_country,
      v1.entry_mode,
      v1.device_token,
      JSON.stringify(v1),
    ],
  )
  await insertOutboxEvent(client, v1, randomUUID())
  await recordProcessingReceipt(client, {
    consumerPurpose: 'migration-proof',
    eventId: v1.event_id,
    streamMessageId: '1-0',
    envelopeHash: 'a'.repeat(64),
  })
  await client.query(
    "INSERT INTO idempotency_records (key_hash, payload_hash, status, response_status, response_body) VALUES ($1, $2, 'completed', 202, $3)",
    [
      'b'.repeat(64),
      'c'.repeat(64),
      JSON.stringify({ schema_version: '1.0', event_id: v1.event_id }),
    ],
  )
  await client.query(
    'INSERT INTO quarantined_events (quarantine_id, event_id, sanitized_payload, reason_codes) VALUES ($1, $2, $3, $4)',
    [randomUUID(), randomUUID(), JSON.stringify(v1), ['held']],
  )
  const before = await snapshot()
  const fksBefore = (
    await client.query(
      "SELECT oid, conname, confrelid FROM pg_constraint WHERE contype = 'f' AND connamespace = $1::regnamespace ORDER BY conname",
      [schema],
    )
  ).rows
  await migrate(migration[0])
  expect(await snapshot()).toEqual(before)
  await migrate(migration[1])
  expect(await snapshot()).toEqual(before)
  await migrate(migration[0])
  expect(await snapshot()).toEqual(before)
  expect(
    (
      await client.query(
        "SELECT oid, conname, confrelid FROM pg_constraint WHERE contype = 'f' AND connamespace = $1::regnamespace ORDER BY conname",
        [schema],
      )
    ).rows,
  ).toEqual(fksBefore)
  await expect(
    client.query(
      'UPDATE authorization_events SET amount_minor = 0 WHERE event_id = $1',
      [v1.event_id],
    ),
  ).rejects.toThrow('immutable')
  await expect(client.query('DELETE FROM quarantined_events')).rejects.toThrow(
    'immutable',
  )
})

test('SQL constraints reject incomplete or manufactured fields and payloads', async () => {
  for (const override of [
    { time_basis: null },
    { currency_basis: null },
    { merchant_category: null },
    { currency: 'INR' },
    { channel: 'card_present' },
    { account_token: 'invented_account' },
    { entry_mode: 'ecommerce' },
    { device_token: 'invented_device' },
    { terminal_token: 'invented_terminal' },
    { merchant_country: 'US' },
    { data_origin: 'synthetic_enriched' },
    { amount_minor: 9007199254740992 },
    { cc_num: 'private' },
    { merchant_category: { is_fraud: 1 } },
    { occurred_at: '2019-01-01T00:00:00.000Z' },
  ]) {
    await expect(
      insertAcceptedEvent(client, sparkovReplay(override)),
    ).rejects.toThrow()
  }
  await expect(
    insertAcceptedEvent(
      client,
      cardNotPresent({
        event_id: randomUUID(),
        authorization_id: randomUUID(),
        account_token: null,
      }),
    ),
  ).rejects.toThrow()
  await expect(
    insertOutboxEvent(client, sparkovReplay(), randomUUID()),
  ).rejects.toMatchObject({ code: '23503' })
  await expect(
    recordProcessingReceipt(client, {
      consumerPurpose: 'missing-event',
      eventId: sparkovReplay().event_id,
      streamMessageId: '2-0',
      envelopeHash: 'b'.repeat(64),
    }),
  ).rejects.toMatchObject({ code: '23503' })
})

test('downgrade also refuses quarantine-only or idempotency-only v2 evidence', async () => {
  for (const kind of ['quarantine', 'idempotency']) {
    await client.query('BEGIN')
    try {
      if (kind === 'quarantine') {
        await client.query(
          'INSERT INTO quarantined_events (quarantine_id, event_id, sanitized_payload, reason_codes) VALUES ($1, $2, $3, $4)',
          [
            randomUUID(),
            randomUUID(),
            JSON.stringify(sparkovReplay()),
            ['held'],
          ],
        )
      } else {
        await client.query(
          "INSERT INTO idempotency_records (key_hash, payload_hash, status, response_status, response_body) VALUES ($1, $2, 'completed', 202, $3)",
          [
            'd'.repeat(64),
            'e'.repeat(64),
            JSON.stringify({ schema_version: '2.0' }),
          ],
        )
      }
      await expect(client.query(migration[1])).rejects.toThrow(
        'Cannot downgrade',
      )
    } finally {
      await client.query('ROLLBACK')
    }
  }
})

test('downgrade refuses v2 audit records without changing data or schema', async () => {
  const event = sparkovReplay()
  await insertAcceptedEvent(client, event)
  const before = await snapshot()
  await expect(migrate(migration[1])).rejects.toThrow('Cannot downgrade')
  expect(await snapshot()).toEqual(before)
  expect(
    (
      await client.query(
        'SELECT merchant_category FROM authorization_events WHERE event_id = $1',
        [event.event_id],
      )
    ).rows[0].merchant_category,
  ).toBe(event.merchant_category)
})

test('scoring candidate index preserves populated immutable events and is reversible', async () => {
  const sql = (
    await readFile(
      new URL(
        '../../migrations/0010_scoring-candidate-index.sql',
        import.meta.url,
      ),
      'utf8',
    )
  ).split('-- Down Migration')
  const before = await snapshot()
  await migrate(sql[0])
  expect(await snapshot()).toEqual(before)
  const index = (
    await client.query(
      'SELECT indexdef FROM pg_indexes WHERE schemaname=$1 AND indexname=$2',
      [schema, 'authorization_events_scoring_order_idx'],
    )
  ).rows[0]
  expect(index.indexdef).toContain('(created_at, event_id)')
  expect(index.indexdef).toContain('schema_version')
  expect(index.indexdef).toContain('2.0')
  await migrate(sql[1])
  expect(await snapshot()).toEqual(before)
})
