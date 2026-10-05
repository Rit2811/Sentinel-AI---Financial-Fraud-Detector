import pg from 'pg'
import { createClient } from 'redis'
import { publishOutboxBatch } from '../src/stream/publisherWorker.js'
import {
  assertTestDatabase,
  requireTestDatabaseUrl,
  requireTestRedisUrl,
} from './databaseSafety.js'

const pool = new pg.Pool({
  connectionString: requireTestDatabaseUrl(process.env.TEST_DATABASE_URL),
})
await assertTestDatabase(pool)
const redis = createClient({
  url: requireTestRedisUrl(process.env.TEST_REDIS_URL),
  disableOfflineQueue: true,
  socket: { reconnectStrategy: false },
})
redis.on('error', () => {})
await redis.connect()
if (process.env.CRASH_STDIN_START === '1') {
  process.stdout.write('publisher_ready\n')
  await new Promise((resolve) => process.stdin.once('data', resolve))
}
const wrapper = {
  connect: async () => {
    const client = await pool.connect()
    return {
      release: (...args) => client.release(...args),
      query: async (...args) => {
        if (args[0] === 'COMMIT') {
          if (process.send) process.send('before_commit')
          if (process.env.CRASH_STDOUT_BOUNDARY === '1')
            process.stdout.write('before_commit\n')
          await new Promise(() => {})
        }
        return client.query(...args)
      },
    }
  },
}
await publishOutboxBatch({
  pool: wrapper,
  redis,
  streamConfig: JSON.parse(process.env.CRASH_STREAM_CONFIG),
  log: { info() {}, error() {} },
})
