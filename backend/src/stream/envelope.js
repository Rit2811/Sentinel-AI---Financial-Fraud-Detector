const envelopeKeys = [
  'authorization_id',
  'correlation_id',
  'data_origin',
  'event_id',
  'occurred_at',
  'schema_version',
]

export function validateEnvelope(envelope) {
  if (
    !envelope ||
    typeof envelope !== 'object' ||
    Array.isArray(envelope) ||
    Object.keys(envelope).sort().join(',') !== envelopeKeys.join(',')
  ) {
    throw new Error('invalid_stream_envelope')
  }
  for (const key of envelopeKeys) {
    if (typeof envelope[key] !== 'string' || envelope[key].length === 0) {
      throw new Error('invalid_stream_envelope')
    }
  }
  return envelope
}
