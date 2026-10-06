import pg from 'pg'

import { databaseConfig } from './databaseConfig.js'

let client
try {
  const settings = databaseConfig()
  const target = new URL(settings.connectionString)
  client = new pg.Client({
    ...settings,
    application_name: 'sentinel-migration-probe',
    connectionTimeoutMillis: 10000,
    query_timeout: 10000,
  })
  await client.connect()
  const identity = await client.query(`
    SELECT current_database() AS database,
           current_setting('server_version') AS postgres_version,
           pg_database_size(current_database())::text AS database_bytes,
           current_setting('max_connections') AS server_max_connections,
           current_setting('fsync') AS fsync,
           current_setting('synchronous_commit') AS synchronous_commit,
           ssl, version AS tls_version
    FROM pg_stat_ssl WHERE pid=pg_backend_pid()
  `)
  const extensions = await client.query(
    'SELECT extname, extversion FROM pg_extension ORDER BY extname',
  )
  const schemas = await client.query(`
    SELECT nspname FROM pg_namespace
    WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
    ORDER BY nspname
  `)
  const publicTables = await client.query(`
    SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename
  `)
  console.log(
    JSON.stringify({
      host: target.hostname,
      port: target.port || '5432',
      identity: identity.rows[0],
      extensions: extensions.rows,
      schemas: schemas.rows,
      publicTables: publicTables.rows,
      clientTLS: {
        encrypted: client.connection.stream.encrypted === true,
        authorized: client.connection.stream.authorized === true,
        protocol: client.connection.stream.getProtocol?.() ?? null,
      },
      verifiedClientTLS:
        settings.ssl?.rejectUnauthorized === true &&
        client.connection.stream.authorized === true,
      capacityNote:
        'Project quota and pooler limits require dashboard confirmation; server max_connections is not the project allowance.',
    }),
  )
} catch (error) {
  console.error(
    JSON.stringify({
      status: 'connection_not_verified',
      errorType: error.name,
      errorCode: error.code ?? null,
    }),
  )
  process.exitCode = 1
} finally {
  if (client) await client.end().catch(() => {})
}
