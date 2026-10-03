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

test('accepts v2 without adding source or payment fields', () => {
  const envelope = {
    ...safeEnvelope,
    schema_version: '2.0',
    data_origin: 'sparkov_replay',
    occurred_at: '2019-01-01T00:00:00Z',
  }
  expect(validateEnvelope(envelope)).toEqual(envelope)
})

test('v2 envelopes reject fractional or invalid calendar timestamps', () => {
  for (const occurred_at of [
    '2019-01-01T00:00:00.000Z',
    '2019-02-30T00:00:00Z',
  ]) {
    expect(() =>
      validateEnvelope({
        ...safeEnvelope,
        schema_version: '2.0',
        data_origin: 'sparkov_replay',
        occurred_at,
      }),
    ).toThrow('invalid_stream_envelope')
  }
})

test.each([
  ['1.0', 'sparkov_replay'],
  ['2.0', 'synthetic_enriched'],
  ['3.0', 'sparkov_replay'],
])(
  'rejects mismatched version %s and origin %s',
  (schema_version, data_origin) => {
    expect(() =>
      validateEnvelope({ ...safeEnvelope, schema_version, data_origin }),
    ).toThrow('invalid_stream_envelope')
  },
)

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
