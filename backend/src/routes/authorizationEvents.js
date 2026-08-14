import { Router } from 'express'
import { header } from 'express-validator'

export function createAuthorizationEventsRouter(controller) {
  const router = Router()
  router.post(
    '/',
    header('Idempotency-Key').exists({ values: 'falsy' }).bail().isUUID(),
    controller,
  )
  return router
}
