import { validationResult } from 'express-validator'

import {
  containsProhibitedField,
  quarantineReasons,
  validateAuthorizationEvent,
} from '../contracts/authorizationEvent.js'
import { rejectionBody } from '../http/responses.js'
import { DependencyUnavailableError } from '../services/authorizationIngestionService.js'

async function reject(req, res, recordRejectedAttempt, status, code) {
  const ingestionId = await recordRejectedAttempt({
    correlationId: req.correlationId,
    code,
    idempotencyKey: req.get('Idempotency-Key'),
  })
  return res
    .status(status)
    .json(rejectionBody(req.correlationId, code, ingestionId))
}

export function createAuthorizationEventController(
  ingestionService,
  recordRejectedAttempt,
) {
  return async function authorizationEventController(req, res) {
    if (!validationResult(req).isEmpty()) {
      return reject(req, res, recordRejectedAttempt, 422, 'validation_failed')
    }
    if (containsProhibitedField(req.body)) {
      return reject(req, res, recordRejectedAttempt, 422, 'prohibited_field')
    }

    const reasonCodes = validateAuthorizationEvent(req.body)
    if (reasonCodes.length > 0) {
      const ingestionId = await recordRejectedAttempt({
        correlationId: req.correlationId,
        code: 'validation_failed',
        idempotencyKey: req.get('Idempotency-Key'),
      })
      return res.status(422).json({
        ...rejectionBody(req.correlationId, 'validation_failed', ingestionId),
        reason_codes: reasonCodes,
      })
    }

    try {
      const result = await ingestionService.ingest({
        event: req.body,
        idempotencyKey: req.get('Idempotency-Key'),
        correlationId: req.correlationId,
        quarantineReasonCodes: quarantineReasons(req.body),
      })
      if (result.replayed) res.set('Idempotent-Replayed', 'true')
      return res.status(result.status).json(result.body)
    } catch (error) {
      if (error instanceof DependencyUnavailableError) {
        return res
          .status(503)
          .json(rejectionBody(req.correlationId, 'dependency_unavailable'))
      }
      throw error
    }
  }
}
