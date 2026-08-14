import { randomUUID } from 'node:crypto'

import { insertRejectedAttempt } from '../repositories/authorizationEventRepository.js'
import { sha256 } from './hashing.js'

export function createRejectedAttemptService(pool, log) {
  return async function recordRejectedAttempt({
    correlationId,
    code,
    idempotencyKey,
  }) {
    const ingestionId = randomUUID()
    try {
      await insertRejectedAttempt(pool, {
        ingestionId,
        correlationId,
        keyHash: idempotencyKey ? sha256(idempotencyKey) : null,
        outcome: code,
        reasonCodes: [code],
        receivedAt: new Date().toISOString(),
      })
    } catch (error) {
      log.warn(
        { errorType: error.name, databaseCode: error.code, correlationId },
        'Safe rejection audit could not be persisted',
      )
    }
    return ingestionId
  }
}
