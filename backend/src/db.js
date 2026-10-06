import pg from 'pg'

import { config } from './config.js'
import { databaseConfig } from './databaseConfig.js'

const { Pool } = pg

export const pool = new Pool({
  ...databaseConfig(),
  options: '-c extra_float_digits=3',
  onConnect: async (client) => {
    await client.query('SET extra_float_digits=3')
  },
  connectionTimeoutMillis: config.readinessTimeoutMs,
})

export async function warmPool(databasePool) {
  const clients = await Promise.allSettled(
    Array.from({ length: databasePool.options.min ?? 0 }, () =>
      databasePool.connect(),
    ),
  )
  for (const client of clients)
    if (client.status === 'fulfilled') client.value.release()
  const failure = clients.find((client) => client.status === 'rejected')
  if (failure) throw failure.reason
}
