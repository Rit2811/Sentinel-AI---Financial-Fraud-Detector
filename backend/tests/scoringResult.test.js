import { jest } from '@jest/globals'
import request from 'supertest'

import { createApp } from '../src/app.js'
import { createScoringResultService } from '../src/services/scoringResultService.js'
import { sparkovReplay } from './fixtures.js'

const event = sparkovReplay()
const runId = '1414dca2-9d7d-47aa-8ab4-96086142ab95'
const token = 'fixture-only-access-token-not-a-real-secret'
const base = { event_id: event.event_id, schema_version: '2.0' }
const path = `/api/v1/transactions/${event.event_id}/result`

function appWith(service, access = { token, runId }) {
  return createApp({
    pool: { query: jest.fn() },
    log: { info() {}, error() {} },
    ingestionService: {},
    recordRejectedAttempt() {},
    scoringResultService: service,
    resultAccess: access,
  })
}

test('scoring readiness remains false during preparation', async () => {
  const response = await request(appWith({})).get('/ready/scoring')
  expect(response.status).toBe(503)
  expect(response.body.status).toBe('not_ready')
})

test('an eligible unassigned event is pending without a fabricated score', async () => {
  const pool = {
    query: jest
      .fn()
      .mockResolvedValueOnce({ rows: [base] })
      .mockResolvedValueOnce({ rows: [{ eligible: true }] }),
  }
  const result = await createScoringResultService(pool, runId).lookup(
    event.event_id,
  )
  expect(result.status).toBe('pending')
  expect(result.reason_code).toBe('awaiting_worker')
  expect(result.probability).toBeNull()
  expect(result.action).toBeNull()
})

test('run lookup failure is not disguised as scoring not activated', async () => {
  const pool = {
    query: jest
      .fn()
      .mockResolvedValueOnce({ rows: [base] })
      .mockRejectedValueOnce(new Error('database unavailable')),
  }
  await expect(
    createScoringResultService(pool, runId).lookup(event.event_id),
  ).rejects.toThrow('database unavailable')
})

test('result lookup is fail-closed and does not query without authentication', async () => {
  const service = { lookup: jest.fn() }
  expect((await request(appWith(service, {})).get(path)).status).toBe(503)
  for (const authorization of [
    '',
    'Bearer wrong',
    `Bearer ${token.slice(1)}x`,
  ]) {
    expect(
      (
        await request(appWith(service))
          .get(path)
          .set('Authorization', authorization)
      ).status,
    ).toBe(401)
  }
  expect(service.lookup).not.toHaveBeenCalled()
})

test('unknown, invalid and store unavailable are distinct', async () => {
  const app = appWith({ lookup: async () => null })
  expect(
    (await request(app).get(path).auth(token, { type: 'bearer' })).status,
  ).toBe(404)
  expect(
    (
      await request(app)
        .get('/api/v1/transactions/not-uuid/result')
        .auth(token, { type: 'bearer' })
    ).status,
  ).toBe(400)
  const failed = await request(
    appWith({
      lookup: async () => {
        throw new Error('private database details')
      },
    }),
  )
    .get(path)
    .auth(token, { type: 'bearer' })
  expect(failed.status).toBe(503)
  expect(JSON.stringify(failed.body)).not.toContain('private')
})

test.each([
  'pending',
  'scoring',
  'unavailable',
  'failed',
  'expired',
  undefined,
])('state %s has no score or action', async (status) => {
  const pool = {
    query: jest.fn(async () => ({
      rows: [{ ...base, status, probability: 0.9, action: 'Block' }],
    })),
  }
  const result = await createScoringResultService(pool, runId).lookup(
    event.event_id,
  )
  expect(result.probability).toBeNull()
  expect(result.action).toBeNull()
  expect(result.risk_score).toBeNull()
  expect(result.available).toBe(false)
  expect(pool.query.mock.calls[0][1]).toEqual([event.event_id, runId])
})

test.each([
  [0.1, 'Review'],
  [0.9, 'Block'],
  [0.099999999999, 'Pass'],
])(
  'stored full precision %s is returned without rounding',
  async (probability, action) => {
    const service = createScoringResultService(
      {
        query: async () => ({
          rows: [
            {
              ...base,
              status: 'scored',
              probability,
              action,
              review_threshold: 0.1,
              block_threshold: 0.9,
              decision_at: '2026-10-02T00:00:00Z',
            },
          ],
        }),
      },
      runId,
    )
    const app = appWith(service)
    const first = await request(app).get(path).auth(token, { type: 'bearer' })
    const second = await request(app).get(path).auth(token, { type: 'bearer' })
    expect(first.status).toBe(200)
    expect(first.body).toEqual(second.body)
    expect(first.body.probability).toBe(probability)
    expect(first.body.action).toBe(action)
    expect(first.headers['cache-control']).toBe('no-store')
    expect(first.body.execution_state).toBe('not_executed')
  },
)

test.each([NaN, Infinity, -0.1, 1.1, null])(
  'invalid stored probability %s is rejected',
  async (probability) => {
    const service = createScoringResultService(
      {
        query: async () => ({
          rows: [{ ...base, status: 'scored', probability }],
        }),
      },
      runId,
    )
    await expect(service.lookup(event.event_id)).rejects.toThrow(
      'invalid_stored_scoring_evidence',
    )
  },
)
