const TEST_DATABASE_NAME = 'sentinel_task4_test'
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]'])
const SAFETY_ERROR =
  'Integration tests require loopback TEST_DATABASE_URL for sentinel_task4_test without query parameters'

export function requireTestDatabaseUrl(value) {
  let url
  try {
    url = new URL(value)
  } catch {
    throw new Error(SAFETY_ERROR)
  }
  if (
    !['postgres:', 'postgresql:'].includes(url.protocol) ||
    !LOOPBACK_HOSTS.has(url.hostname) ||
    url.pathname !== `/${TEST_DATABASE_NAME}` ||
    url.search ||
    url.hash
  ) {
    throw new Error(SAFETY_ERROR)
  }
  return value
}

export function requireTestRedisUrl(
  value,
  port = process.env.TEST_REDIS_PORT ?? '26379',
) {
  const message =
    'Stream tests require loopback TEST_REDIS_URL on TEST_REDIS_PORT (default 26379), database 0, without query parameters'
  let url
  try {
    url = new URL(value)
  } catch {
    throw new Error(message)
  }
  if (
    url.protocol !== 'redis:' ||
    !LOOPBACK_HOSTS.has(url.hostname) ||
    url.port !== String(port) ||
    url.pathname !== '/0' ||
    url.search ||
    url.hash
  ) {
    throw new Error(message)
  }
  return value
}

export async function assertTestDatabase(pool) {
  const result = await pool.query('SELECT current_database() AS database_name')
  if (result.rows[0]?.database_name !== TEST_DATABASE_NAME) {
    throw new Error(
      'Refusing to truncate a database other than sentinel_task4_test',
    )
  }
}
