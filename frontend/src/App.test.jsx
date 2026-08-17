import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import App from './App'

function snapshot(range = '24h') {
  return {
    schema_version: '1.0',
    generated_at: '2026-08-17T06:00:00.000Z',
    range,
    window: {
      from: '2026-08-16T06:00:00.000Z',
      to: '2026-08-17T06:00:00.000Z',
      bucket_seconds: 3600,
    },
    summary: {
      total_events: 2,
      processed_events: 1,
      rejected_attempts: 3,
      quarantined_events: 1,
      pending_events: 1,
      dead_letter_events: 0,
      processing_rate: 50,
      last_event_at: '2026-08-17T05:50:00.000Z',
    },
    channels: { card_present: 1, card_not_present: 1 },
    activity: [
      {
        started_at: '2026-08-17T04:00:00.000Z',
        ingested: 1,
        processed: 0,
        rejected: 2,
      },
      {
        started_at: '2026-08-17T05:00:00.000Z',
        ingested: 1,
        processed: 1,
        rejected: 1,
      },
    ],
  }
}

function response(body, { ok = true, status = 200 } = {}) {
  return { ok, status, json: vi.fn(async () => body) }
}

beforeEach(() => {
  vi.restoreAllMocks()
  globalThis.fetch = vi.fn(async (input) => {
    const range = new URL(input, 'http://localhost').searchParams.get('range')
    return response(snapshot(range))
  })
})

test('renders real operational values returned by the dashboard API', async () => {
  render(<App />)

  expect(screen.getByText('Loading operational data')).toBeInTheDocument()
  expect(await screen.findByText('Live backend')).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Total Events' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Processed' })).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Rejected Attempts' }),
  ).toBeInTheDocument()
  expect(screen.getByText('50.0%')).toBeInTheDocument()
  expect(globalThis.fetch).toHaveBeenCalledWith(
    '/api/v1/dashboard?range=24h',
    expect.objectContaining({ cache: 'no-store' }),
  )
})

test('requests a fresh backend snapshot when the activity range changes', async () => {
  render(<App />)
  await screen.findByText('Live backend')

  fireEvent.click(screen.getByRole('button', { name: '7D' }))

  await waitFor(() =>
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/dashboard?range=7d',
      expect.objectContaining({ cache: 'no-store' }),
    ),
  )
  expect(screen.getByRole('button', { name: '7D' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('supports keyboard inspection across chart buckets', async () => {
  render(<App />)
  const chart = await screen.findByRole('group', {
    name: /Use left and right arrow keys/,
  })

  fireEvent.keyDown(chart, { key: 'ArrowLeft' })

  expect(
    screen.getByText(/Ingested 1, Processed 0, Rejected 2/),
  ).toBeInTheDocument()
})

test('shows a retryable state when the dashboard API is unavailable', async () => {
  globalThis.fetch = vi.fn(async () => response({}, { ok: false, status: 503 }))
  render(<App />)

  expect(await screen.findByRole('alert', { name: '' })).toHaveTextContent(
    'Dashboard data is unavailable',
  )
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
})
