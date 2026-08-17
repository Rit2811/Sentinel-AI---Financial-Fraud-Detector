import { jest } from '@jest/globals'

import {
  DashboardUnavailableError,
  UnsupportedDashboardRangeError,
  createDashboardService,
} from '../src/services/dashboardService.js'

const log = { warn: jest.fn() }

function databaseRow() {
  return {
    from_time: '2026-08-17T05:00:00.000Z',
    to_time: '2026-08-17T06:00:00.000Z',
    bucket_seconds: 300,
    total_events: 4,
    processed_events: 3,
    rejected_attempts: 2,
    quarantined_events: 1,
    pending_events: 1,
    dead_letter_events: 0,
    last_event_at: '2026-08-17T05:50:00.000Z',
    card_present: 1,
    card_not_present: 3,
    activity: [
      {
        started_at: '2026-08-17T05:00:00.000Z',
        ingested: 2,
        processed: 1,
        rejected: 1,
      },
    ],
  }
}

describe('dashboard service', () => {
  beforeEach(() => jest.clearAllMocks())

  test('normalizes a database aggregate without exposing event payloads', async () => {
    const pool = { query: jest.fn(async () => ({ rows: [databaseRow()] })) }
    const snapshot = await createDashboardService(pool, log).getSnapshot('1H')

    expect(pool.query.mock.calls[0][1]).toEqual(['1 hour', '5 minutes'])
    expect(snapshot.range).toBe('1h')
    expect(snapshot.summary.processing_rate).toBe(75)
    expect(snapshot.channels).toEqual({ card_present: 1, card_not_present: 3 })
    expect(snapshot.activity[0]).toEqual({
      started_at: '2026-08-17T05:00:00.000Z',
      ingested: 2,
      processed: 1,
      rejected: 1,
    })
    expect(JSON.stringify(snapshot)).not.toContain('sanitized_payload')
  })

  test('reports null processing rate before the first event', async () => {
    const row = databaseRow()
    row.total_events = 0
    row.processed_events = 0
    const pool = { query: jest.fn(async () => ({ rows: [row] })) }

    const snapshot = await createDashboardService(pool, log).getSnapshot()

    expect(snapshot.summary.processing_rate).toBeNull()
  })

  test('rejects unsupported ranges before querying PostgreSQL', async () => {
    const pool = { query: jest.fn() }
    await expect(
      createDashboardService(pool, log).getSnapshot('30d'),
    ).rejects.toBeInstanceOf(UnsupportedDashboardRangeError)
    expect(pool.query).not.toHaveBeenCalled()
  })

  test('maps database failures to a dashboard availability error', async () => {
    const pool = {
      query: jest.fn(async () => {
        throw new Error('do not leak this')
      }),
    }
    await expect(
      createDashboardService(pool, log).getSnapshot(),
    ).rejects.toBeInstanceOf(DashboardUnavailableError)
    expect(log.warn).toHaveBeenCalledWith(
      { errorType: 'Error' },
      'Dashboard snapshot query unavailable',
    )
  })
})
