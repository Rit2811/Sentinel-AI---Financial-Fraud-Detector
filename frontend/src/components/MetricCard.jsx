import { iconRegistry } from '../icons/registry'
import { formatInteger } from '../utils/chart'
import { Card } from './Card'
import { Sparkline } from './Sparkline'

const valueFormatters = Object.freeze({
  integer: formatInteger,
})

export function MetricCard({ metric }) {
  const Icon = iconRegistry[metric.icon]
  const formatValue = valueFormatters[metric.valueFormat]

  return (
    <Card className={`metric-card metric-card--${metric.tone}`}>
      <div className="metric-card__content">
        <div className="metric-card__heading">
          <span className="metric-card__icon">
            <Icon label={`${metric.label} icon`} />
          </span>
          <h2>{metric.label}</h2>
        </div>
        <strong className="metric-card__value">
          {formatValue(metric.value)}
        </strong>
        <p className="metric-card__detail">{metric.detailLabel}</p>
      </div>
      <Sparkline
        label={`${metric.label} trend`}
        tone={metric.tone}
        values={metric.sparkline}
      />
    </Card>
  )
}
