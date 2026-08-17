import { sparklineConfig } from '../config/charts'
import { areaPath, linePath, scaleSeries } from '../utils/chart'

export function Sparkline({ label, tone, values }) {
  const padding = {
    top: sparklineConfig.padding,
    right: sparklineConfig.padding,
    bottom: sparklineConfig.padding,
    left: sparklineConfig.padding,
  }
  const points = scaleSeries(
    values,
    sparklineConfig.width,
    sparklineConfig.height,
    padding,
    Math.max(...values),
  )

  return (
    <svg
      aria-label={label}
      className={`sparkline sparkline--${tone}`}
      role="img"
      viewBox={`0 0 ${sparklineConfig.width} ${sparklineConfig.height}`}
    >
      <path
        className="sparkline__area"
        d={areaPath(points, sparklineConfig.height - sparklineConfig.padding)}
      />
      <path className="sparkline__line" d={linePath(points)} />
      {points.map((point, index) => (
        <circle
          className="sparkline__point"
          cx={point.x}
          cy={point.y}
          key={`${point.x}-${point.y}`}
          r={index === points.length - 1 ? 3.5 : 2}
        />
      ))}
    </svg>
  )
}
