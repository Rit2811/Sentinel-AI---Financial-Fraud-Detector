import { createClient } from 'redis'

import { config } from '../config.js'
import { logger } from '../logger.js'

export function createRedisClient({ bounded = false } = {}) {
  const client = createClient({
    url: config.redisUrl,
    ...(bounded
      ? {
          disableOfflineQueue: true,
          socket: { connectTimeout: 1000, reconnectStrategy: false },
        }
      : {}),
  })
  client.on('error', (error) => {
    logger.error({ errorType: error.name }, 'Redis client error')
  })
  return client
}
