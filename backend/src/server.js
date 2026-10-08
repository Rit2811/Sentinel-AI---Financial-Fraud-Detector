import { createApp } from './app.js'
import { config } from './config.js'
import { pool, warmPool } from './db.js'
import { logger } from './logger.js'

try {
  await warmPool(pool)
} catch (error) {
  logger.error(
    { errorType: error.name },
    'Application database initialization failed',
  )
  await pool.end()
  process.exit(1)
}

const server = createApp().listen(config.port, '0.0.0.0', () => {
  logger.info({ port: config.port }, 'Sentinel AI API listening')
})

async function shutdown(signal) {
  logger.info({ signal }, 'Shutting down')
  server.close(async () => {
    await pool.end()
    process.exit(0)
  })
}

process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
