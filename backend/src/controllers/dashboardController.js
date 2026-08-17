import {
  DashboardUnavailableError,
  UnsupportedDashboardRangeError,
  dashboardRanges,
} from '../services/dashboardService.js'

export function createDashboardController(dashboardService) {
  return async function dashboardController(req, res) {
    const requestedRange =
      typeof req.query.range === 'string' ? req.query.range : '24h'

    try {
      const snapshot = await dashboardService.getSnapshot(requestedRange)
      res.set('Cache-Control', 'no-store')
      return res.json(snapshot)
    } catch (error) {
      if (error instanceof UnsupportedDashboardRangeError) {
        return res.status(400).json({
          code: 'invalid_range',
          correlation_id: req.correlationId,
          supported_ranges: Object.keys(dashboardRanges),
        })
      }
      if (error instanceof DashboardUnavailableError) {
        return res.status(503).json({
          code: 'dashboard_unavailable',
          correlation_id: req.correlationId,
        })
      }
      throw error
    }
  }
}
