import { setTimeout as delay } from 'node:timers/promises'

import { config } from '../config.js'
import { pool } from '../db.js'
import { logger } from '../logger.js'
import { createRedisClient } from './redis.js'
import { publishOutboxBatch } from './publisherWorker.js'

const redis = createRedisClient()
let stopping = false
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    stopping = true
  })
}

await redis.connect()
logger.info({ stream: config.stream.name }, 'Outbox publisher started')
while (!stopping) {
  try {
    const count = await publishOutboxBatch({
      pool,
      redis,
      streamConfig: config.stream,
      log: logger,
    })
    if (count === 0) await delay(config.stream.pollMs)
  } catch (error) {
    logger.error(
      { errorType: error.name },
      'Outbox publisher cycle unavailable',
    )
    await delay(config.stream.pollMs)
  }
}
await redis.quit().catch(() => {})
await pool.end()
