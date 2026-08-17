export function StatusBadge({ label, tone }) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span aria-hidden="true" className="status-badge__dot" />
      {label}
    </span>
  )
}
