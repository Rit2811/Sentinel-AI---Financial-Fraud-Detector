import { jest } from '@jest/globals'
import express from 'express'
import request from 'supertest'
import { createReviewResolutionsRouter } from '../src/routes/reviewResolutions.js'

const token = 'fixture-review-token-not-a-real-secret'
const id = '1414dca2-9d7d-47aa-8ab4-96086142ab95'
const body = {
  resolution_id: id,
  resolution: 'allow',
  notes: 'Reviewed synthetic transaction',
}
const path = `/${id}/review-resolution`
function app(
  service,
  access = { token, runId: id, reviewerId: 'team_member_1' },
) {
  return express().use(createReviewResolutionsRouter(service, access))
}
test('review authentication is separate and fails closed before storage', async () => {
  const service = { resolve: jest.fn() }
  expect((await request(app(service, {})).post(path).send(body)).status).toBe(
    503,
  )
  expect((await request(app(service)).post(path).send(body)).status).toBe(401)
  expect(service.resolve).not.toHaveBeenCalled()
})
test('reviewer identity comes from authenticated server configuration', async () => {
  const service = {
    resolve: jest.fn(async () => ({
      status: 201,
      body: { resolution: 'allow' },
    })),
  }
  const response = await request(app(service))
    .post(path)
    .auth(token, { type: 'bearer' })
    .send(body)
  expect(response.status).toBe(201)
  expect(response.headers['cache-control']).toBe('no-store')
  expect(service.resolve).toHaveBeenCalledWith(id, 'team_member_1', body)
})
test.each([
  { ...body, reviewer_id: 'forged' },
  { ...body, is_fraud: false },
  { ...body, cc_num: 'forbidden' },
  { ...body, resolution: 'Pass' },
  { ...body, notes: '' },
  { ...body, notes: '4111111111111111' },
])(
  'rejects extra fields, invalid choices and card-like note content',
  async (input) => {
    const service = { resolve: jest.fn() }
    expect(
      (
        await request(app(service))
          .post(path)
          .auth(token, { type: 'bearer' })
          .send(input)
      ).status,
    ).toBe(422)
    expect(service.resolve).not.toHaveBeenCalled()
  },
)
test('storage errors are redacted and malformed JSON is distinct', async () => {
  const service = {
    resolve: async () => {
      throw Error('private storage details')
    },
  }
  const response = await request(app(service))
    .post(path)
    .auth(token, { type: 'bearer' })
    .send(body)
  expect(response.status).toBe(503)
  expect(JSON.stringify(response.body)).not.toContain('private')
  expect(
    (
      await request(app(service))
        .post(path)
        .auth(token, { type: 'bearer' })
        .set('Content-Type', 'application/json')
        .send('{')
    ).status,
  ).toBe(400)
})
