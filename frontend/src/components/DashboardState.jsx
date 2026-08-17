export function DashboardState({ message, onRetry, retryLabel, title, type }) {
  const isError = type === 'error'
  return (
    <section
      aria-live="polite"
      className={`dashboard-state dashboard-state--${type}`}
      role={isError ? 'alert' : 'status'}
    >
      <span aria-hidden="true" className="dashboard-state__indicator" />
      <h2>{title}</h2>
      <p>{message}</p>
      {isError && (
        <button onClick={onRetry} type="button">
          {retryLabel}
        </button>
      )}
    </section>
  )
}
