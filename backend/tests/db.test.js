import { jest } from '@jest/globals'

jest.unstable_mockModule('pg', () => ({
  default: {
    Pool: class {
      constructor(options) {
        this.options = options
      }
    },
  },
}))
const { pool, warmPool } = await import('../src/db.js')

test('pool initializes float precision before leasing each new connection', async () => {
  const client = { query: jest.fn().mockResolvedValue({ rows: [] }) }
  await pool.options.onConnect(client)
  expect(client.query).toHaveBeenCalledWith('SET extra_float_digits=3')
})

test('failed session initialization rejects connection acquisition', async () => {
  const client = {
    query: jest.fn().mockRejectedValue(new Error('session_setup_failed')),
  }
  await expect(pool.options.onConnect(client)).rejects.toThrow(
    'session_setup_failed',
  )
})

test('startup acquires the bounded minimum and releases every initialized client', async () => {
  const clients = Array.from({ length: 3 }, () => ({ release: jest.fn() }))
  const databasePool = { options: { min: 3 }, connect: jest.fn() }
  clients.forEach((client) =>
    databasePool.connect.mockResolvedValueOnce(client),
  )
  await warmPool(databasePool)
  expect(databasePool.connect).toHaveBeenCalledTimes(3)
  clients.forEach((client) => expect(client.release).toHaveBeenCalledTimes(1))
})

test('failed startup releases successful peers and never signals readiness', async () => {
  const client = { release: jest.fn() }
  const databasePool = {
    options: { min: 2 },
    connect: jest
      .fn()
      .mockResolvedValueOnce(client)
      .mockRejectedValueOnce(new Error('initialization_failed')),
  }
  await expect(warmPool(databasePool)).rejects.toThrow('initialization_failed')
  expect(client.release).toHaveBeenCalledTimes(1)
})
