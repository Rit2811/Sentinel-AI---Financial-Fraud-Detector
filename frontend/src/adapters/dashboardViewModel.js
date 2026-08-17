import { runtimeConfig } from '../config/runtime'
import { dashboardContent } from '../content/dashboard'

function formatBucketLabel(timestamp, range) {
  const date = new Date(timestamp)
  if (range === '7d') {
    return new Intl.DateTimeFormat(runtimeConfig.locale, {
      weekday: 'short',
    }).format(date)
  }
  return new Intl.DateTimeFormat(runtimeConfig.locale, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatUpdatedAt(timestamp) {
  return new Intl.DateTimeFormat(runtimeConfig.locale, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(timestamp))
}

export function createDashboardViewModel(snapshot) {
  const activity = snapshot.activity.map((bucket) => ({
    ...bucket,
    label: formatBucketLabel(bucket.started_at, snapshot.range),
  }))

  return {
    activity,
    hasActivity: activity.some(
      ({ ingested, processed, rejected }) =>
        ingested > 0 || processed > 0 || rejected > 0,
    ),
    processingRate: snapshot.summary.processing_rate,
    statusDetails: [
      {
        label: dashboardContent.statusDetails.pending,
        value: snapshot.summary.pending_events,
      },
      {
        label: dashboardContent.statusDetails.quarantined,
        value: snapshot.summary.quarantined_events,
      },
      {
        label: dashboardContent.statusDetails.deadLetter,
        value: snapshot.summary.dead_letter_events,
      },
    ],
    metrics: dashboardContent.metrics.map((definition) => ({
      ...definition,
      value: snapshot.summary[definition.valueKey],
      valueFormat: 'integer',
      sparkline: activity.map((bucket) => bucket[definition.seriesKey]),
    })),
    updatedAt: formatUpdatedAt(snapshot.generated_at),
  }
}
