import {
  assertTestDatabase,
  requireTestDatabaseUrl,
  requireTestRedisUrl,
} from './databaseSafety.js'

const testUrl =
  'postgresql://sentinel:sentinel_test_only@127.0.0.1:25432/sentinel_task4_test'

test('accepts an explicit isolated PostgreSQL test database', () => {
  expect(requireTestDatabaseUrl(testUrl)).toBe(testUrl)
  expect(
    requireTestDatabaseUrl(testUrl.replace('postgresql:', 'postgres:')),
  ).toBe(testUrl.replace('postgresql:', 'postgres:'))
})

test.each([
  undefined,
  '',
  'not-a-url',
  testUrl.replace('sentinel_task4_test', 'sentinel'),
  `${testUrl}_other`,
  testUrl.replace('postgresql:', 'https:'),
  `${testUrl}?dbname=sentinel`,
  `${testUrl}#sentinel`,
  testUrl.replace('127.0.0.1', 'db.example.com'),
  testUrl.replace('127.0.0.1', '10.0.0.1'),
])('rejects an unsafe test URL without echoing credentials: %p', (value) => {
  expect(() => requireTestDatabaseUrl(value)).toThrow(
    'Integration tests require loopback TEST_DATABASE_URL for sentinel_task4_test without query parameters',
  )
})

test.each(['127.0.0.1', 'localhost', '[::1]'])(
  'accepts only explicit loopback test endpoints: %s',
  (host) => {
    expect(
      requireTestDatabaseUrl(testUrl.replace('127.0.0.1', host)),
    ).toContain('sentinel_task4_test')
    const redisUrl = `redis://sentinel_test_only@${host}:26379/0`
    expect(requireTestRedisUrl(redisUrl, '26379')).toBe(redisUrl)
  },
)

test.each([
  undefined,
  '',
  'not-a-url',
  'redis://db.example.com:26379/0',
  'redis://127.0.0.1:16379/0',
  'redis://127.0.0.1:26379/1',
  'redis://127.0.0.1:26379/0?host=db.example.com',
  'redis://127.0.0.1:26379/0#fragment',
])('rejects unsafe Redis target %p', (value) => {
  expect(() => requireTestRedisUrl(value, '26379')).toThrow(
    'Stream tests require loopback TEST_REDIS_URL',
  )
})

test('accepts an explicitly selected isolated Redis port', () => {
  const url = 'redis://127.0.0.1:36379/0'
  expect(requireTestRedisUrl(url, '36379')).toBe(url)
})

test('checks the connected database before permitting destructive setup', async () => {
  await expect(
    assertTestDatabase({
      query: async () => ({ rows: [{ database_name: 'sentinel_task4_test' }] }),
    }),
  ).resolves.toBeUndefined()
  await expect(
    assertTestDatabase({
      query: async () => ({ rows: [{ database_name: 'sentinel' }] }),
    }),
  ).rejects.toThrow('Refusing to truncate')
})
