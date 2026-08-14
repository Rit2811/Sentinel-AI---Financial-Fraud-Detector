import { createApp } from './app.js'
import { config } from './config.js'
import { pool } from './db.js'
import { logger } from './logger.js'

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
