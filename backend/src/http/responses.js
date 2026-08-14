import { randomUUID } from 'node:crypto'

export function rejectionBody(correlationId, code, ingestionId = randomUUID()) {
  return {
    ingestion_id: ingestionId,
    correlation_id: correlationId,
    outcome: 'rejected',
    code,
    reason_codes: [code],
  }
}
