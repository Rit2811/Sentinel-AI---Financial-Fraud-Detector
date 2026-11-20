import express, { Router } from 'express'

export function createPaymentSimulationRouter(simulationService) {
  const router = Router()
  router.use(express.json({ limit: '64kb' }))

  router.get('/presets', (_req, res) => {
    res.json({
      success: true,
      presets: simulationService.getPresets(),
    })
  })

  router.get('/history', (req, res) => {
    const limit = Math.min(100, Math.max(1, Number(req.query.limit ?? 25)))
    res.json({
      success: true,
      history: simulationService.getHistory(limit),
    })
  })

  router.post('/reset', (_req, res) => {
    const result = simulationService.resetVelocity()
    res.json(result)
  })

  router.post('/review', async (req, res) => {
    const { simulationId, decision, notes } = req.body ?? {}
    if (!simulationId || !['allow', 'reject'].includes(decision)) {
      return res.status(400).json({
        success: false,
        code: 'invalid_review_payload',
        message: 'simulationId and decision ("allow" | "reject") are required.',
      })
    }

    const result = await simulationService.resolveReview(simulationId, decision, notes)
    if (!result.success) {
      return res.status(404).json(result)
    }
    return res.json(result)
  })

  router.post('/payment', async (req, res) => {
    try {
      const result = await simulationService.simulatePayment(req.body ?? {})
      const httpStatus = result.pciViolation ? 422 : 200
      return res.status(httpStatus).json(result)
    } catch (err) {
      return res.status(500).json({
        success: false,
        code: 'simulation_error',
        message: err.message,
      })
    }
  })

  return router
}
