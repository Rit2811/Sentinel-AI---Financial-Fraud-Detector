const STEPS = [
  { label: 'Card Read', icon: '💳' },
  { label: 'Tokenize', icon: '🔐' },
  { label: 'Extract', icon: '📊' },
  { label: 'ML Score', icon: '🧠' },
  { label: 'Decision', icon: '⚖️' },
  { label: 'Execute', icon: '⚡' },
]

export function TransactionTimeline({ latencyMs = 0, status = 'approved' }) {
  const statusColors = {
    approved: 'var(--color-success)',
    warning: 'var(--color-warning)',
    dangerous: 'var(--color-danger)',
  }

  const timings = [
    '< 1ms',
    '1ms',
    '1ms',
    `${Math.max(1, latencyMs - 4)}ms`,
    '< 1ms',
    '< 1ms',
  ]

  const finalIcon =
    status === 'approved' ? '✅' : status === 'warning' ? '⚠️' : '🛑'

  return (
    <div
      className="tx-timeline"
      role="list"
      aria-label="Transaction processing pipeline"
      style={{ '--tl-color': statusColors[status] || statusColors.approved }}
    >
      {STEPS.map((step, i) => (
        <div key={i} className="tx-timeline__step" role="listitem">
          <div className="tx-timeline__dot">
            <span>{i === STEPS.length - 1 ? finalIcon : step.icon}</span>
          </div>
          <span className="tx-timeline__label">{step.label}</span>
          <span className="tx-timeline__time">{timings[i]}</span>
        </div>
      ))}
    </div>
  )
}
