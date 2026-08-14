import { createClient } from 'redis'

import { config } from '../config.js'
import { logger } from '../logger.js'

export function createRedisClient() {
  const client = createClient({ url: config.redisUrl })
  client.on('error', (error) => {
    logger.error({ errorType: error.name }, 'Redis client error')
  })
  return client
}
