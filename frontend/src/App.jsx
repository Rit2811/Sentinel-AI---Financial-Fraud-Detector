import { useMemo, useState } from 'react'

import { createDashboardViewModel } from './adapters/dashboardViewModel'
import { ActivityPanel } from './components/ActivityPanel'
import { CreditCardSimulator } from './components/CreditCardSimulator'
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

function App({ defaultTab = 'simulator' }) {
  const [activeTab, setActiveTab] = useState(defaultTab)
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

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div className="view-switcher" role="tablist" aria-label="System Navigation">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'simulator'}
            className={`view-switcher-button ${activeTab === 'simulator' ? 'view-switcher-button--active' : ''}`}
            onClick={() => setActiveTab('simulator')}
          >
            <span>💳</span> Credit Card Simulator
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'dashboard'}
            className={`view-switcher-button ${activeTab === 'dashboard' ? 'view-switcher-button--active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <span>📊</span> Ingestion &amp; Stream Dashboard
          </button>
        </div>

        {activeTab === 'simulator' && (
          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', background: 'var(--color-surface)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-pill)', border: '1px solid var(--color-border)' }}>
            🟢 Model Status: Random Forest Sigmoid-Calibrated Simulation
          </span>
        )}
      </div>

      {activeTab === 'simulator' ? (
        <CreditCardSimulator onTransactionProcessed={refresh} />
      ) : (
        <>
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
        </>
      )}
    </main>
  )
}

export default App
