import { statusRingConfig } from '../config/charts'
import { formatInteger, formatPercent } from '../utils/chart'
import { Card } from './Card'

export function DetectionStatus({
  ariaLabel,
  details,
  emptyLabel,
  label,
  score,
  title,
}) {
  const config = statusRingConfig
  const circumference = 2 * Math.PI * config.radius
  const dashOffset = circumference * (1 - (score ?? 0) / 100)

  return (
    <Card className="detection-status" title={title}>
      <div className="detection-status__ring">
        <svg
          aria-label={ariaLabel}
          role="img"
          viewBox={`0 0 ${config.viewBoxSize} ${config.viewBoxSize}`}
        >
          <circle
            className="detection-status__track"
            cx={config.center}
            cy={config.center}
            r={config.radius}
            strokeWidth={config.strokeWidth}
          />
          <circle
            className="detection-status__progress"
            cx={config.center}
            cy={config.center}
            r={config.radius}
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeWidth={config.strokeWidth}
          />
        </svg>
        <div className="detection-status__value">
          <strong>{score === null ? '—' : `${formatPercent(score)}%`}</strong>
          <span>{score === null ? emptyLabel : label}</span>
        </div>
      </div>
      <dl className="detection-status__details">
        {details.map((detail) => (
          <div key={detail.label}>
            <dt>{detail.label}</dt>
            <dd>{formatInteger(detail.value)}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}
