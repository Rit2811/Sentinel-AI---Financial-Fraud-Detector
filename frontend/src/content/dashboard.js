export const dashboardContent = Object.freeze({
  heading: 'Transaction Overview',
  description: 'Live authorization ingestion and stream processing',
  statuses: Object.freeze({
    connecting: Object.freeze({ label: 'Connecting', tone: 'neutral' }),
    live: Object.freeze({ label: 'Live backend', tone: 'success' }),
    refreshing: Object.freeze({ label: 'Refreshing', tone: 'warning' }),
    unavailable: Object.freeze({
      label: 'Backend unavailable',
      tone: 'danger',
    }),
  }),
  updatedLabel: 'Last updated',
  refreshLabel: 'Refresh dashboard',
  activityTitle: 'Authorization Activity',
  activityChartLabel: 'Live ingestion, processing, and rejection activity',
  rangeControlLabel: 'Activity time range',
  processingTitle: 'Stream Processing Status',
  processingLabel: 'Events processed',
  noProcessingLabel: 'Awaiting events',
  chartLabels: Object.freeze({
    ingested: 'Ingested',
    processed: 'Processed',
    rejected: 'Rejected',
  }),
  state: Object.freeze({
    loadingTitle: 'Loading operational data',
    loadingMessage: 'Reading the latest aggregate snapshot from PostgreSQL.',
    errorTitle: 'Dashboard data is unavailable',
    errorMessage:
      'The page could not reach the dashboard API. Existing ingestion services may still be running.',
    retryLabel: 'Try again',
    emptyMessage: 'No activity was recorded during this time range.',
  }),
  statusDetails: Object.freeze({
    pending: 'Pending',
    quarantined: 'Quarantined',
    deadLetter: 'Dead letter',
  }),
  metrics: Object.freeze([
    Object.freeze({
      id: 'total-events',
      label: 'Total Events',
      valueKey: 'total_events',
      detailLabel: 'accepted authorizations',
      tone: 'accent',
      icon: 'transactions',
      seriesKey: 'ingested',
    }),
    Object.freeze({
      id: 'processed-events',
      label: 'Processed',
      valueKey: 'processed_events',
      detailLabel: 'unique stream events',
      tone: 'success',
      icon: 'check',
      seriesKey: 'processed',
    }),
    Object.freeze({
      id: 'rejected-attempts',
      label: 'Rejected Attempts',
      valueKey: 'rejected_attempts',
      detailLabel: 'failed ingestion attempts',
      tone: 'danger',
      icon: 'shield',
      seriesKey: 'rejected',
    }),
  ]),
})

export const dashboardRanges = Object.freeze([
  Object.freeze({ value: '1h', label: '1H' }),
  Object.freeze({ value: '24h', label: '24H' }),
  Object.freeze({ value: '7d', label: '7D' }),
])
