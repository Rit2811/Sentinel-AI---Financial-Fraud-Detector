import { randomUUID } from 'node:crypto'

import { jest } from '@jest/globals'
import request from 'supertest'

import { createApp } from '../src/app.js'
import { DependencyUnavailableError } from '../src/services/authorizationIngestionService.js'
import { cardNotPresent, correlationId, idempotencyKey } from './fixtures.js'

const log = { info: jest.fn(), warn: jest.fn(), error: jest.fn() }
const recordRejectedAttempt = jest.fn(async () => randomUUID())
const unusedPool = { query: jest.fn() }

function appWith(ingest) {
  return createApp({
    pool: unusedPool,
    log,
    recordRejectedAttempt,
    ingestionService: { ingest },
  })
}

function postEvent(app, body = cardNotPresent()) {
  return request(app)
    .post('/api/v1/authorization-events')
    .set('Content-Type', 'application/json')
    .set('Idempotency-Key', idempotencyKey)
    .set('X-Correlation-ID', correlationId)
    .send(body)
}

describe('HTTP ingestion boundary', () => {
  beforeEach(() => jest.clearAllMocks())

  test('preserves Task 2 liveness', async () => {
    const response = await request(appWith(jest.fn())).get('/health')
    expect(response.status).toBe(200)
    expect(response.body).toEqual({ status: 'ok', service: 'sentinel-ai-api' })
  })

  test('returns accepted result only from the service', async () => {
    const body = {
      ingestion_id: randomUUID(),
      event_id: cardNotPresent().event_id,
      correlation_id: correlationId,
      schema_version: '1.0',
      outcome: 'accepted',
      reason_codes: [],
      received_at: new Date().toISOString(),
    }
    const response = await postEvent(
      appWith(jest.fn(async () => ({ status: 202, body }))),
    )
    expect(response.status).toBe(202)
    expect(response.body).toEqual(body)
  })

  test.each([
    [undefined, 422, 'validation_failed'],
    [{ amount_minor: -1 }, 422, 'validation_failed'],
  ])(
    'rejects invalid headers or body safely',
    async (override, status, code) => {
      const app = appWith(jest.fn())
      let call = request(app)
        .post('/api/v1/authorization-events')
        .set('Content-Type', 'application/json')
        .set('X-Correlation-ID', correlationId)
      if (override)
        call = call
          .set('Idempotency-Key', idempotencyKey)
          .send(cardNotPresent(override))
      else call = call.send(cardNotPresent())
      const response = await call
      expect(response.status).toBe(status)
      expect(response.body.code).toBe(code)
      expect(JSON.stringify(response.body)).not.toContain('card_tok_demo_001')
    },
  )

  test('rejects prohibited fields without echoing names or values', async () => {
    const sensitiveMarker = 'never-echo-this-value'
    const response = await postEvent(appWith(jest.fn()), {
      ...cardNotPresent(),
      nested: { card_number: sensitiveMarker },
    })
    expect(response.status).toBe(422)
    expect(response.body.code).toBe('prohibited_field')
    expect(JSON.stringify(response.body)).not.toContain(sensitiveMarker)
  })

  test('enforces content type, malformed JSON, and the body limit', async () => {
    const app = appWith(jest.fn())
    const wrongType = await request(app)
      .post('/api/v1/authorization-events')
      .set('Content-Type', 'text/plain')
      .send('{}')
    expect(wrongType.status).toBe(415)
    expect(wrongType.body.code).toBe('unsupported_media_type')

    const malformed = await request(app)
      .post('/api/v1/authorization-events')
      .set('Content-Type', 'application/json')
      .send('{')
    expect(malformed.status).toBe(400)
    expect(malformed.body.code).toBe('malformed_json')

    const oversized = await request(app)
      .post('/api/v1/authorization-events')
      .set('Content-Type', 'application/json')
      .send(JSON.stringify({ padding: 'x'.repeat(40_000) }))
    expect(oversized.status).toBe(413)
    expect(oversized.body.code).toBe('payload_too_large')
  })

  test('sets replay header and does not alter persisted identifiers', async () => {
    const body = {
      ingestion_id: randomUUID(),
      event_id: cardNotPresent().event_id,
      correlation_id: correlationId,
      schema_version: '1.0',
      outcome: 'duplicate',
      reason_codes: [],
      received_at: new Date().toISOString(),
    }
    const response = await postEvent(
      appWith(jest.fn(async () => ({ status: 200, replayed: true, body }))),
    )
    expect(response.status).toBe(200)
    expect(response.headers['idempotent-replayed']).toBe('true')
    expect(response.body).toEqual(body)
  })

  test('maps database failure to dependency unavailable', async () => {
    const response = await postEvent(
      appWith(
        jest.fn(async () => {
          throw new DependencyUnavailableError()
        }),
      ),
    )
    expect(response.status).toBe(503)
    expect(response.body.code).toBe('dependency_unavailable')
  })

  test('publishes OpenAPI statuses and approved examples', async () => {
    const response = await request(appWith(jest.fn())).get('/openapi.json')
    const operation = response.body.paths['/api/v1/authorization-events'].post
    expect(Object.keys(operation.responses).sort()).toEqual([
      '200',
      '202',
      '400',
      '409',
      '413',
      '415',
      '422',
      '503',
    ])
    expect(response.body.components.examples.CardNotPresent.value).toEqual(
      cardNotPresent(),
    )
  })
})
