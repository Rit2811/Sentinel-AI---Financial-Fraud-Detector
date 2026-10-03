import { timingSafeEqual } from 'node:crypto'
import express, { Router } from 'express'

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function createReviewResolutionsRouter(
  service,
  { token, runId, reviewerId },
) {
  const router = Router()
  router.post(
    '/:eventId/review-resolution',
    (req, res, next) => {
      res.set('Cache-Control', 'no-store')
      if (
        !token ||
        token.length < 32 ||
        !UUID.test(runId ?? '') ||
        !/^[A-Za-z0-9_-]{1,128}$/.test(reviewerId ?? '')
      )
        return res.status(503).json({ code: 'review_api_not_configured' })
      const supplied = req.get('Authorization') ?? ''
      const expected = `Bearer ${token}`
      if (
        Buffer.byteLength(supplied) !== Buffer.byteLength(expected) ||
        !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
      )
        return res.status(401).json({ code: 'unauthorized' })
      if (!UUID.test(req.params.eventId))
        return res.status(400).json({ code: 'invalid_event_id' })
      if (!req.is('application/json'))
        return res.status(415).json({ code: 'unsupported_media_type' })
      return next()
    },
    express.json({ limit: '8kb', strict: true }),
    async (req, res) => {
      const body = req.body
      if (
        !body ||
        Array.isArray(body) ||
        Object.keys(body).sort().join(',') !==
          'notes,resolution,resolution_id' ||
        !UUID.test(body.resolution_id ?? '') ||
        !['allow', 'reject'].includes(body.resolution) ||
        typeof body.notes !== 'string' ||
        !body.notes.trim() ||
        body.notes.length > 2000 ||
        /(?:\d[ -]?){13,19}/.test(body.notes)
      )
        return res.status(422).json({ code: 'invalid_review_resolution' })
      try {
        const result = await service.resolve(
          req.params.eventId,
          reviewerId,
          body,
        )
        return res.status(result.status).json(result.body)
      } catch {
        return res.status(503).json({ code: 'review_store_unavailable' })
      }
    },
  )
  router.use((error, _req, res, _next) => {
    res
      .status(error.type === 'entity.too.large' ? 413 : 400)
      .json({ code: 'invalid_review_json' })
  })
  return router
}
