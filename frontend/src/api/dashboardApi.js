import { runtimeConfig } from '../config/runtime'

export class DashboardApiError extends Error {
  constructor(message, status = null) {
    super(message)
    this.name = 'DashboardApiError'
    this.status = status
  }
}

function isFiniteNonNegative(value) {
  return Number.isFinite(value) && value >= 0
}

function validateSnapshot(snapshot) {
  const validSummary =
    snapshot?.summary &&
    ['total_events', 'processed_events', 'rejected_attempts'].every((key) =>
      isFiniteNonNegative(snapshot.summary[key]),
    )
  const validActivity =
    Array.isArray(snapshot?.activity) &&
    snapshot.activity.length > 0 &&
    snapshot.activity.every(
      (bucket) =>
        typeof bucket.started_at === 'string' &&
        ['ingested', 'processed', 'rejected'].every((key) =>
          isFiniteNonNegative(bucket[key]),
        ),
    )

  if (
    snapshot?.schema_version !== '1.0' ||
    typeof snapshot.generated_at !== 'string' ||
    !validSummary ||
    !validActivity
  ) {
    throw new DashboardApiError('Dashboard API returned an invalid response')
  }
  return snapshot
}

export async function fetchDashboard(range, { signal } = {}) {
  const query = new URLSearchParams({ range })
  const response = await fetch(
    `${runtimeConfig.dashboardApiPath}?${query.toString()}`,
    {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal,
    },
  )

  if (!response.ok) {
    throw new DashboardApiError(
      `Dashboard request failed with status ${response.status}`,
      response.status,
    )
  }

  return validateSnapshot(await response.json())
}
