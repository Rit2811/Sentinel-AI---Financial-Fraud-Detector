import { timingSafeEqual } from 'node:crypto'
import { Router } from 'express'

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function createScoringResultsRouter(service, { token, runId }) {
  const router = Router()
  router.use((req, res, next) => {
    if (req.method !== 'GET' || !req.path.endsWith('/result')) return next()
    res.set('Cache-Control', 'no-store')
    if (!token || token.length < 32 || !UUID.test(runId ?? '')) {
      return res
        .status(503)
        .json({ status: 'unavailable', code: 'result_api_not_configured' })
    }
    const supplied = req.get('Authorization') ?? ''
    const expected = `Bearer ${token}`
    if (
      Buffer.byteLength(supplied) !== Buffer.byteLength(expected) ||
      !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
    ) {
      return res.status(401).json({ code: 'unauthorized' })
    }
    return next()
  })
  router.get('/:eventId/result', async (req, res) => {
    if (!UUID.test(req.params.eventId))
      return res.status(400).json({ code: 'invalid_event_id' })
    try {
      const result = await service.lookup(req.params.eventId)
      if (!result) return res.status(404).json({ code: 'event_not_found' })
      return res.json(result)
    } catch {
      return res
        .status(503)
        .json({ status: 'unavailable', code: 'scoring_store_unavailable' })
    }
  })
  return router
}
