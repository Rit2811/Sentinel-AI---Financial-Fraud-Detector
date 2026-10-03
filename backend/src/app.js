import { randomUUID } from 'node:crypto'

import express from 'express'
import { createClient } from 'redis'
import swaggerUi from 'swagger-ui-express'

import { config } from './config.js'
import { createAuthorizationEventController } from './controllers/authorizationEventController.js'
import { createDashboardController } from './controllers/dashboardController.js'
import { pool as defaultPool } from './db.js'
import { rejectionBody } from './http/responses.js'
import { logger as defaultLogger } from './logger.js'
import { openApiDocument } from './openapi.js'
import { createAuthorizationEventsRouter } from './routes/authorizationEvents.js'
import { createDashboardRouter } from './routes/dashboard.js'
import { createScoringResultsRouter } from './routes/scoringResults.js'
import { createReviewResolutionsRouter } from './routes/reviewResolutions.js'
import { createReviewResolutionService } from './services/reviewResolutionService.js'
import { createScoringResultService } from './services/scoringResultService.js'
import { scoringReadiness } from './services/scoringReadinessService.js'
import { createAuthorizationIngestionService } from './services/authorizationIngestionService.js'
import { createDashboardService } from './services/dashboardService.js'
import { createRejectedAttemptService } from './services/rejectedAttemptService.js'

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

async function postgresReady(pool) {
  const result = await pool.query('SELECT 1 AS value')
  return result.rows[0].value === 1
}

async function redisReady(redisFactory) {
  const client = redisFactory()
  let timeout
  try {
    const pong = await Promise.race([
      client.connect().then(() => client.ping()),
      new Promise((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error('redis_readiness_timeout')),
          config.readinessTimeoutMs,
        )
      }),
    ])
    return pong === 'PONG'
  } finally {
    clearTimeout(timeout)
    if (client.isOpen) client.destroy()
  }
}

export function createApp({
  pool = defaultPool,
  log = defaultLogger,
  ingestionService: suppliedIngestionService,
  dashboardService: suppliedDashboardService,
  recordRejectedAttempt: suppliedRecordRejectedAttempt,
  scoringResultService: suppliedScoringResultService,
  reviewResolutionService: suppliedReviewResolutionService,
  reviewAccess = {
    token: process.env.REVIEW_API_TOKEN,
    runId: process.env.SCORING_RUN_ID,
    reviewerId: process.env.REVIEWER_ID,
  },
  resultAccess = {
    token: process.env.RESULT_API_TOKEN,
    runId: process.env.SCORING_RUN_ID,
  },
  redisFactory = () =>
    createClient({
      url: config.redisUrl,
      socket: {
        connectTimeout: config.readinessTimeoutMs,
        reconnectStrategy: false,
      },
    }),
} = {}) {
  const app = express()
  app.disable('x-powered-by')

  const ingestionService =
    suppliedIngestionService ?? createAuthorizationIngestionService(pool, log)
  const recordRejectedAttempt =
    suppliedRecordRejectedAttempt ?? createRejectedAttemptService(pool, log)
  const controller = createAuthorizationEventController(
    ingestionService,
    recordRejectedAttempt,
  )
  const dashboardService =
    suppliedDashboardService ?? createDashboardService(pool, log)
  const dashboardController = createDashboardController(dashboardService)

  app.use((req, res, next) => {
    const supplied = req.get('X-Correlation-ID')
    req.correlationId = UUID_PATTERN.test(supplied ?? '')
      ? supplied
      : randomUUID()
    res.set('X-Correlation-ID', req.correlationId)
    next()
  })

  app.use((req, res, next) => {
    res.on('finish', () => {
      log.info(
        {
          method: req.method,
          path: req.path,
          statusCode: res.statusCode,
          correlationId: req.correlationId,
        },
        'HTTP request completed',
      )
    })
    next()
  })

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok', service: 'sentinel-ai-api' })
  })

  app.get('/ready', async (_req, res) => {
    const [postgres, redis] = await Promise.all([
      postgresReady(pool).catch(() => false),
      redisReady(redisFactory).catch(() => false),
    ])
    const ready = postgres && redis
    res.status(ready ? 200 : 503).json({
      status: ready ? 'ready' : 'not_ready',
      dependencies: { postgres, redis },
    })
  })

  app.get('/openapi.json', (_req, res) => res.json(openApiDocument))
  app.use('/docs', swaggerUi.serve, swaggerUi.setup(openApiDocument))
  app.use('/api/v1/dashboard', createDashboardRouter(dashboardController))
  app.use(
    '/api/v1/transactions',
    createScoringResultsRouter(
      suppliedScoringResultService ??
        createScoringResultService(pool, resultAccess.runId),
      resultAccess,
    ),
  )
  app.get('/ready/scoring', async (_req, res) => {
    const ready = await scoringReadiness(pool, resultAccess.runId)
    res.status(ready ? 200 : 503).json({
      status: ready ? 'ready' : 'not_ready',
      code: ready
        ? 'approved_scoring_worker_ready'
        : 'approved_scoring_worker_not_connected',
    })
  })

  app.use(
    '/api/v1/transactions',
    createReviewResolutionsRouter(
      suppliedReviewResolutionService ??
        createReviewResolutionService(pool, reviewAccess.runId),
      reviewAccess,
    ),
  )

  app.use('/api/v1/authorization-events', async (req, res, next) => {
    if (!req.is('application/json')) {
      const code = 'unsupported_media_type'
      const ingestionId = await recordRejectedAttempt({
        correlationId: req.correlationId,
        code,
        idempotencyKey: req.get('Idempotency-Key'),
      })
      return res
        .status(415)
        .json(rejectionBody(req.correlationId, code, ingestionId))
    }
    return next()
  })

  app.use(express.json({ limit: config.bodyLimit, strict: true }))
  app.use(
    '/api/v1/authorization-events',
    createAuthorizationEventsRouter(controller),
  )

  app.use(async (error, req, res, _next) => {
    let status = 500
    let code = 'internal_error'
    if (error.type === 'entity.too.large') {
      status = 413
      code = 'payload_too_large'
    } else if (error instanceof SyntaxError && error.status === 400) {
      status = 400
      code = 'malformed_json'
    } else {
      log.error(
        { errorType: error.name, correlationId: req.correlationId },
        'Unhandled request error',
      )
    }

    const ingestionId =
      status === 500
        ? randomUUID()
        : await recordRejectedAttempt({
            correlationId: req.correlationId,
            code,
            idempotencyKey: req.get('Idempotency-Key'),
          })
    res.status(status).json(rejectionBody(req.correlationId, code, ingestionId))
  })

  return app
}
