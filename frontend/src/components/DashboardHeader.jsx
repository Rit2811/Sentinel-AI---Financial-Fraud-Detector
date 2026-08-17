import { StatusBadge } from './StatusBadge'

export function DashboardHeader({
  description,
  heading,
  isRefreshing,
  onRefresh,
  refreshLabel,
  status,
  updatedAt,
  updatedLabel,
}) {
  return (
    <header className="dashboard-header">
      <div>
        <h1>{heading}</h1>
        <div className="dashboard-header__meta">
          <p>{description}</p>
          <StatusBadge label={status.label} tone={status.tone} />
        </div>
      </div>
      <div className="dashboard-header__actions">
        {updatedAt && (
          <span>
            {updatedLabel}: <time>{updatedAt}</time>
          </span>
        )}
        <button
          className="refresh-button"
          disabled={isRefreshing}
          onClick={onRefresh}
          type="button"
        >
          <span aria-hidden="true">↻</span>
          {refreshLabel}
        </button>
      </div>
    </header>
  )
}
