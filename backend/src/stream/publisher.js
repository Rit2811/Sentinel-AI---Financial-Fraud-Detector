import { setTimeout as delay } from 'node:timers/promises'

import { config } from '../config.js'
import { pool } from '../db.js'
import { logger } from '../logger.js'
import { createRedisClient } from './redis.js'
import { publishOutboxBatch } from './publisherWorker.js'

const redis = createRedisClient({ bounded: true })
let stopping = false
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    stopping = true
  })
}

const settings = await pool.query(`SELECT current_setting('fsync') AS fsync`)
if (settings.rows[0].fsync !== 'on')
  throw new Error('durable_publication_requires_fsync')
logger.info({ stream: config.stream.name }, 'Outbox publisher started')
while (!stopping) {
  try {
    if (!redis.isReady) {
      if (redis.isOpen) redis.destroy()
      await redis.connect()
    }
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
