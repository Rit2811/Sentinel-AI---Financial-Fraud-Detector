import { databaseConfig } from '../src/databaseConfig.js'

const url =
  'postgresql://postgres.example:encoded%40placeholder@aws-0-example.pooler.supabase.com:5432/postgres'
const ca = '-----BEGIN CERTIFICATE-----\nplaceholder\n-----END CERTIFICATE-----'

test('keeps the existing local target and bounded pool', () => {
  expect(databaseConfig({})).toEqual({
    connectionString:
      'postgresql://sentinel:sentinel_local_only@127.0.0.1:15432/sentinel',
    max: 10,
  })
})
test('preserves the explicitly isolated Docker fixture target', () => {
  expect(
    databaseConfig({
      POSTGRES_URL:
        'postgresql://sentinel:placeholder@sentinel-task4-test-postgres-1:5432/sentinel_task4_test',
    }).ssl,
  ).toBeUndefined()
})
test('DATABASE_URL supports verified remote TLS without URL override', () => {
  const read = (path) => {
    expect(path).toBe('/trusted/root.crt')
    return ca
  }
  const settings = databaseConfig(
    {
      DATABASE_URL: url + '?sslmode=verify-full',
      PGSSLROOTCERT: '/trusted/root.crt',
      POSTGRES_POOL_MAX: '3',
    },
    read,
  )
  expect(settings).toEqual({
    connectionString: url,
    max: 3,
    ssl: { ca, rejectUnauthorized: true },
  })
})
test.each([
  { POSTGRES_URL: url, DATABASE_URL: 'postgresql://different/target' },
  { DATABASE_URL: 'not a URL' },
  { DATABASE_URL: 'https://example.com' },
  { DATABASE_URL: url },
  { DATABASE_URL: url.replace(':5432/', ':6543/'), PGSSLROOTCERT: '/root.crt' },
  { DATABASE_URL: url + '?sslmode=require', PGSSLROOTCERT: '/root.crt' },
  { DATABASE_URL: url + '?sslkey=private.key', PGSSLROOTCERT: '/root.crt' },
  { DATABASE_URL: url + '?ssl=0', PGSSLROOTCERT: '/root.crt' },
  { DATABASE_URL: url + '?host=localhost', PGSSLROOTCERT: '/root.crt' },
  { POSTGRES_POOL_MAX: '0' },
  { POSTGRES_POOL_MAX: '11' },
  { POSTGRES_POOL_MAX: '1.5' },
  { POSTGRES_POOL_MIN: '-1' },
  { POSTGRES_POOL_MAX: '3', POSTGRES_POOL_MIN: '4' },
  { POSTGRES_POOL_MIN: '1.5' },
])(
  'rejects conflicting, insecure or invalid settings without secret details',
  (env) => {
    try {
      databaseConfig(env, () => ca)
      throw new Error('unexpected acceptance')
    } catch (error) {
      expect(error.message).not.toContain('encoded%40placeholder')
      expect(error.message).not.toBe('unexpected acceptance')
    }
  },
)
test('certificate read failures are sanitized', () => {
  expect(() =>
    databaseConfig({ DATABASE_URL: url, PGSSLROOTCERT: '/root.crt' }, () => {
      throw Error(url)
    }),
  ).toThrow('Cannot read database root certificate')
})
