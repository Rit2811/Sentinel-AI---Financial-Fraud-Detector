import { readFileSync } from 'node:fs'

export function databaseConfig(
  env = process.env,
  readCertificate = readFileSync,
) {
  if (
    env.POSTGRES_URL &&
    env.DATABASE_URL &&
    env.POSTGRES_URL !== env.DATABASE_URL
  ) {
    throw new Error('Conflicting server database targets')
  }
  const raw =
    env.POSTGRES_URL ??
    env.DATABASE_URL ??
    'postgresql://sentinel:sentinel_local_only@127.0.0.1:15432/sentinel'
  let url
  try {
    url = new URL(raw)
  } catch {
    throw new Error('Invalid server database connection format')
  }
  if (!['postgres:', 'postgresql:'].includes(url.protocol)) {
    throw new Error('Server database must use PostgreSQL')
  }
  const max = Number(env.POSTGRES_POOL_MAX ?? 10)
  if (!Number.isInteger(max) || max < 1 || max > 10) {
    throw new Error('POSTGRES_POOL_MAX must be an integer from 1 to 10')
  }
  const min = Number(env.POSTGRES_POOL_MIN ?? 0)
  if (!Number.isInteger(min) || min < 0 || min > max) {
    throw new Error('POSTGRES_POOL_MIN must be an integer between zero and max')
  }
  const local = [
    'localhost',
    '127.0.0.1',
    '[::1]',
    'postgres',
    'sentinel-task4-test-postgres-1',
  ].includes(url.hostname)
  let ssl
  if (!local) {
    if (
      url.hostname.endsWith('.pooler.supabase.com') &&
      (url.port || '5432') !== '5432'
    ) {
      throw new Error('Supabase requires the approved Session pooler')
    }
    const allowed = new Set(['sslmode', 'sslrootcert', 'application_name'])
    if ([...url.searchParams.keys()].some((key) => !allowed.has(key))) {
      throw new Error('Unsupported remote database URL option')
    }
    const mode = url.searchParams.get('sslmode') ?? env.PGSSLMODE
    if (mode && mode !== 'verify-full') {
      throw new Error('Remote database requires verified TLS')
    }
    if (url.searchParams.has('sslcert') || url.searchParams.has('sslkey')) {
      throw new Error('Client TLS credentials are not configured by URL')
    }
    const root =
      env.POSTGRES_SSL_ROOT_CERT ??
      env.PGSSLROOTCERT ??
      url.searchParams.get('sslrootcert')
    if (!root) throw new Error('Remote database root certificate is required')
    let ca
    try {
      ca = readCertificate(root, 'utf8')
    } catch {
      throw new Error('Cannot read database root certificate')
    }
    if (!ca.includes('-----BEGIN CERTIFICATE-----')) {
      throw new Error('Database root certificate must be PEM encoded')
    }
    // pg URL SSL parameters override explicit SSL options; retain one verified policy.
    url.searchParams.delete('sslmode')
    url.searchParams.delete('sslrootcert')
    ssl = { ca, rejectUnauthorized: true }
  }
  return {
    connectionString: url.toString(),
    max,
    ...(env.POSTGRES_POOL_MIN === undefined ? {} : { min }),
    ...(ssl ? { ssl } : {}),
  }
}
