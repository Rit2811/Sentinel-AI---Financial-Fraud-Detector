import { getDashboardSnapshot } from '../repositories/dashboardRepository.js'

export const dashboardRanges = Object.freeze({
  '1h': Object.freeze({ duration: '1 hour', bucket: '5 minutes' }),
  '24h': Object.freeze({ duration: '24 hours', bucket: '1 hour' }),
  '7d': Object.freeze({ duration: '7 days', bucket: '1 day' }),
})

export class UnsupportedDashboardRangeError extends Error {}
export class DashboardUnavailableError extends Error {}

function asNumber(value) {
  return Number(value ?? 0)
}

function asIsoString(value) {
  return value ? new Date(value).toISOString() : null
}

function processingRate(processedEvents, totalEvents) {
  if (totalEvents === 0) return null
  return Math.min(100, (processedEvents / totalEvents) * 100)
}

export function createDashboardService(pool, log) {
  return {
    async getSnapshot(requestedRange = '24h') {
      const rangeKey = requestedRange.toLowerCase()
      const range = dashboardRanges[rangeKey]
      if (!range) throw new UnsupportedDashboardRangeError()

      let row
      try {
        row = await getDashboardSnapshot(pool, range)
      } catch (error) {
        log.warn(
          { errorType: error.name },
          'Dashboard snapshot query unavailable',
        )
        throw new DashboardUnavailableError()
      }

      const totalEvents = asNumber(row.total_events)
      const processedEvents = asNumber(row.processed_events)

      return {
        schema_version: '1.0',
        generated_at: asIsoString(row.to_time),
        range: rangeKey,
        window: {
          from: asIsoString(row.from_time),
          to: asIsoString(row.to_time),
          bucket_seconds: asNumber(row.bucket_seconds),
        },
        summary: {
          total_events: totalEvents,
          processed_events: processedEvents,
          rejected_attempts: asNumber(row.rejected_attempts),
          quarantined_events: asNumber(row.quarantined_events),
          pending_events: asNumber(row.pending_events),
          dead_letter_events: asNumber(row.dead_letter_events),
          processing_rate: processingRate(processedEvents, totalEvents),
          last_event_at: asIsoString(row.last_event_at),
        },
        channels: {
          card_present: asNumber(row.card_present),
          card_not_present: asNumber(row.card_not_present),
        },
        activity: row.activity.map((bucket) => ({
          started_at: asIsoString(bucket.started_at),
          ingested: asNumber(bucket.ingested),
          processed: asNumber(bucket.processed),
          rejected: asNumber(bucket.rejected),
        })),
      }
    },
  }
}
