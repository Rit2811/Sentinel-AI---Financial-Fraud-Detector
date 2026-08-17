export function scaleSeries(values, width, height, padding, maximum) {
  const usableWidth = width - padding.left - padding.right
  const usableHeight = height - padding.top - padding.bottom
  const denominator = Math.max(values.length - 1, 1)

  const safeMaximum = Math.max(maximum, 1)

  return values.map((value, index) => ({
    x: padding.left + (index / denominator) * usableWidth,
    y: padding.top + usableHeight - (value / safeMaximum) * usableHeight,
  }))
}

export function chartScale(values, tickCount) {
  const highest = Math.max(...values, 0)
  if (highest === 0) {
    return { maximum: tickCount, ticks: [0, tickCount] }
  }
  const roughStep = highest / tickCount
  const magnitude = 10 ** Math.floor(Math.log10(roughStep))
  const normalized = roughStep / magnitude
  const niceFactor =
    normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  const step = niceFactor * magnitude
  const maximum = Math.ceil(highest / step) * step
  const ticks = Array.from(
    { length: Math.round(maximum / step) + 1 },
    (_, index) => index * step,
  )
  return { maximum, ticks }
}

export function linePath(points) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
}

export function areaPath(points, baseline) {
  if (points.length === 0) return ''
  return `${linePath(points)} L ${points.at(-1).x} ${baseline} L ${points[0].x} ${baseline} Z`
}

export function selectLabelIndexes(length, maximumLabels) {
  if (length <= maximumLabels)
    return new Set(Array.from({ length }, (_, index) => index))
  const indexes = new Set()
  for (let position = 0; position < maximumLabels; position += 1) {
    indexes.add(Math.round((position / (maximumLabels - 1)) * (length - 1)))
  }
  return indexes
}

export function formatInteger(value) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(
    value,
  )
}

export function formatChartTick(value) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 1,
  }).format(value)
}

export function formatPercent(value) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  }).format(value)
}
