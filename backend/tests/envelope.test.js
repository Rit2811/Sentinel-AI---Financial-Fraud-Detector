import { validateEnvelope } from '../src/stream/envelope.js'

const safeEnvelope = {
  event_id: 'c9744fa0-40e6-4703-bfe4-81d6b5c58e80',
  authorization_id: 'a9e38d8c-51f0-43cd-8b63-f73bd3595248',
  correlation_id: 'd138e735-971b-4fcf-bd90-8e707c4f592f',
  schema_version: '1.0',
  data_origin: 'synthetic_enriched',
  occurred_at: '2026-08-11T00:00:00.000Z',
}

test('accepts only the six safe envelope fields', () => {
  expect(validateEnvelope(safeEnvelope)).toEqual(safeEnvelope)
})

test('rejects a stream envelope containing payment data', () => {
  expect(() =>
    validateEnvelope({ ...safeEnvelope, amount_minor: 100 }),
  ).toThrow('invalid_stream_envelope')
})

test('rejects a stream envelope missing required evidence', () => {
  const incomplete = { ...safeEnvelope }
  delete incomplete.correlation_id
  expect(() => validateEnvelope(incomplete)).toThrow('invalid_stream_envelope')
})
