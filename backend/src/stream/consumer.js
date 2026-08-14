import { config } from '../config.js'
import { pool } from '../db.js'
import { logger } from '../logger.js'
import { consumeOnce, ensureConsumerGroup } from './consumerWorker.js'
import { createRedisClient } from './redis.js'

const redis = createRedisClient()
let stopping = false
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    stopping = true
  })
}

await redis.connect()
await ensureConsumerGroup(redis, config.stream)
logger.info(
  { stream: config.stream.name, group: config.stream.group },
  'Proof consumer started',
)
while (!stopping) {
  try {
    await consumeOnce({
      pool,
      redis,
      streamConfig: config.stream,
      log: logger,
    })
  } catch (error) {
    logger.error({ errorType: error.name }, 'Proof consumer cycle unavailable')
  }
}
await redis.quit().catch(() => {})
await pool.end()
