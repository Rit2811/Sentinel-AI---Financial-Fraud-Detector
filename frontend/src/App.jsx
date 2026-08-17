import { useMemo, useState } from 'react'

import { createDashboardViewModel } from './adapters/dashboardViewModel'
import { ActivityPanel } from './components/ActivityPanel'
import { DashboardHeader } from './components/DashboardHeader'
import { DashboardState } from './components/DashboardState'
import { DetectionStatus } from './components/DetectionStatus'
import { MetricCard } from './components/MetricCard'
import { runtimeConfig } from './config/runtime'
import { dashboardContent, dashboardRanges } from './content/dashboard'
import { useDashboard } from './hooks/useDashboard'

function dashboardStatus({ data, error, isRefreshing }) {
  if (error && !data) return dashboardContent.statuses.unavailable
  if (isRefreshing) return dashboardContent.statuses.refreshing
  if (data) return dashboardContent.statuses.live
  return dashboardContent.statuses.connecting
}

function App() {
  const [activeRange, setActiveRange] = useState(
    runtimeConfig.initialDashboardRange,
  )
  const { data, error, isLoading, isRefreshing, refresh } =
    useDashboard(activeRange)
  const viewModel = useMemo(
    () => (data ? createDashboardViewModel(data) : null),
    [data],
  )
  const status = dashboardStatus({ data, error, isRefreshing })

  return (
    <main className="dashboard">
      <DashboardHeader
        description={dashboardContent.description}
        heading={dashboardContent.heading}
        isRefreshing={isRefreshing}
        onRefresh={refresh}
        refreshLabel={dashboardContent.refreshLabel}
        status={status}
        updatedAt={viewModel?.updatedAt}
        updatedLabel={dashboardContent.updatedLabel}
      />

      {isLoading && !viewModel && (
        <DashboardState
          message={dashboardContent.state.loadingMessage}
          title={dashboardContent.state.loadingTitle}
          type="loading"
        />
      )}

      {error && !viewModel && !isLoading && (
        <DashboardState
          message={dashboardContent.state.errorMessage}
          onRetry={refresh}
          retryLabel={dashboardContent.state.retryLabel}
          title={dashboardContent.state.errorTitle}
          type="error"
        />
      )}

      {viewModel && (
        <>
          <div className="dashboard__primary-grid">
            <ActivityPanel
              activeRange={activeRange}
              chartLabel={dashboardContent.activityChartLabel}
              data={viewModel.activity}
              emptyMessage={dashboardContent.state.emptyMessage}
              hasActivity={viewModel.hasActivity}
              labels={dashboardContent.chartLabels}
              onRangeChange={setActiveRange}
              rangeLabel={dashboardContent.rangeControlLabel}
              ranges={dashboardRanges}
              title={dashboardContent.activityTitle}
              tooltipIndex={viewModel.activity.length - 1}
              tooltipLabels={dashboardContent.chartLabels}
            />
            <DetectionStatus
              ariaLabel={dashboardContent.processingTitle}
              details={viewModel.statusDetails}
              emptyLabel={dashboardContent.noProcessingLabel}
              label={dashboardContent.processingLabel}
              score={viewModel.processingRate}
              title={dashboardContent.processingTitle}
            />
          </div>

          <div className="dashboard__metric-grid">
            {viewModel.metrics.map((metric) => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>
        </>
      )}
    </main>
  )
}

export default App
