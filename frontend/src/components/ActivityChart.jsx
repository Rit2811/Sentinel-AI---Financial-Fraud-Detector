import { useMemo, useState } from 'react'

import { activityChartConfig } from '../config/charts'
import {
  areaPath,
  chartScale,
  formatChartTick,
  formatInteger,
  linePath,
  scaleSeries,
  selectLabelIndexes,
} from '../utils/chart'

const seriesDefinitions = Object.freeze([
  Object.freeze({ key: 'ingested', tone: 'primary' }),
  Object.freeze({ key: 'processed', tone: 'secondary' }),
  Object.freeze({ key: 'rejected', tone: 'danger' }),
])

function selectedDescription(point, labels) {
  return seriesDefinitions
    .map(({ key }) => `${labels[key]} ${formatInteger(point[key])}`)
    .join(', ')
}

export function ActivityChart({
  ariaLabel,
  data,
  legendLabels,
  tooltipIndex,
  tooltipLabels,
}) {
  const config = activityChartConfig
  const [selectedIndex, setSelectedIndex] = useState(tooltipIndex)
  const baseline = config.height - config.padding.bottom
  const allValues = data.flatMap((point) =>
    seriesDefinitions.map(({ key }) => point[key]),
  )
  const scale = useMemo(
    () => chartScale(allValues, config.yTickCount),
    [allValues, config.yTickCount],
  )
  const pointsBySeries = useMemo(
    () =>
      Object.fromEntries(
        seriesDefinitions.map(({ key }) => [
          key,
          scaleSeries(
            data.map((point) => point[key]),
            config.width,
            config.height,
            config.padding,
            scale.maximum,
          ),
        ]),
      ),
    [config, data, scale.maximum],
  )
  const xLabelIndexes = selectLabelIndexes(
    data.length,
    config.maximumXAxisLabels,
  )
  const safeSelectedIndex = Math.max(
    0,
    Math.min(selectedIndex, data.length - 1),
  )
  const selectedPoint = data[safeSelectedIndex]
  const selectedPosition = pointsBySeries.ingested[safeSelectedIndex]
  const tooltipLeft = `${Math.min(90, Math.max(10, (selectedPosition.x / config.width) * 100))}%`
  const tooltipTop = `${(selectedPosition.y / config.height) * 100}%`
  const showTooltipBelow = selectedPosition.y < config.height * 0.33

  function selectFromPointer(event) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const pointerX =
      ((event.clientX - bounds.left) / bounds.width) * config.width
    const usableWidth =
      config.width - config.padding.left - config.padding.right
    const progress = Math.min(
      1,
      Math.max(0, (pointerX - config.padding.left) / usableWidth),
    )
    setSelectedIndex(Math.round(progress * (data.length - 1)))
  }

  function navigateSelection(event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    if (event.key === 'Home') setSelectedIndex(0)
    else if (event.key === 'End') setSelectedIndex(data.length - 1)
    else {
      const direction = event.key === 'ArrowLeft' ? -1 : 1
      setSelectedIndex((current) =>
        Math.min(data.length - 1, Math.max(0, current + direction)),
      )
    }
  }

  return (
    <div className="activity-chart">
      <svg
        aria-label={`${ariaLabel}. Use left and right arrow keys to inspect time buckets.`}
        className="activity-chart__plot"
        onKeyDown={navigateSelection}
        onPointerDown={selectFromPointer}
        onPointerMove={selectFromPointer}
        role="group"
        tabIndex="0"
        viewBox={`0 0 ${config.width} ${config.height}`}
      >
        <defs>
          <linearGradient id="primary-area" x1="0" x2="0" y1="0" y2="1">
            <stop className="activity-chart__area-start" offset="0%" />
            <stop className="activity-chart__area-end" offset="100%" />
          </linearGradient>
        </defs>

        {scale.ticks.map((tick) => {
          const y =
            config.padding.top +
            (1 - tick / scale.maximum) *
              (config.height - config.padding.top - config.padding.bottom)
          return (
            <g key={tick}>
              <line
                className="activity-chart__grid"
                x1={config.padding.left}
                x2={config.width - config.padding.right}
                y1={y}
                y2={y}
              />
              <text
                className="activity-chart__axis-label"
                textAnchor="end"
                x={config.padding.left - 12}
                y={y + 5}
              >
                {formatChartTick(tick)}
              </text>
            </g>
          )
        })}

        {data.map((point, index) =>
          xLabelIndexes.has(index) ? (
            <text
              className="activity-chart__axis-label"
              key={point.started_at}
              textAnchor={
                index === 0
                  ? 'start'
                  : index === data.length - 1
                    ? 'end'
                    : 'middle'
              }
              x={pointsBySeries.ingested[index].x}
              y={config.height - 17}
            >
              {point.label}
            </text>
          ) : null,
        )}

        <path
          className="activity-chart__primary-area"
          d={areaPath(pointsBySeries.ingested, baseline)}
        />
        {seriesDefinitions.map(({ key, tone }) => (
          <path
            className={`activity-chart__line activity-chart__line--${tone}`}
            d={linePath(pointsBySeries[key])}
            key={key}
          />
        ))}

        <line
          className="activity-chart__selection-line"
          x1={selectedPosition.x}
          x2={selectedPosition.x}
          y1={config.padding.top}
          y2={baseline}
        />

        {seriesDefinitions.flatMap(({ key, tone }) =>
          pointsBySeries[key].map((point, index) => (
            <circle
              aria-hidden="true"
              className={`activity-chart__point activity-chart__point--${tone}`}
              cx={point.x}
              cy={point.y}
              key={`${key}-${data[index].started_at}`}
              r={index === safeSelectedIndex ? 5 : 3}
            />
          )),
        )}
      </svg>

      <p aria-live="polite" className="visually-hidden">
        {selectedPoint.label}:{' '}
        {selectedDescription(selectedPoint, tooltipLabels)}
      </p>
      <div
        aria-hidden="true"
        className={`activity-chart__tooltip${showTooltipBelow ? ' activity-chart__tooltip--below' : ''}`}
        style={{ left: tooltipLeft, top: tooltipTop }}
      >
        <strong>{selectedPoint.label}</strong>
        {seriesDefinitions.map(({ key, tone }) => (
          <span key={key}>
            {tooltipLabels[key]}
            <b className={`activity-chart__tooltip-${tone}`}>
              {formatInteger(selectedPoint[key])}
            </b>
          </span>
        ))}
      </div>

      <div className="activity-chart__legend">
        {seriesDefinitions.map(({ key, tone }) => (
          <span key={key}>
            <i
              className={`activity-chart__legend-line activity-chart__legend-line--${tone}`}
            />
            {legendLabels[key]}
          </span>
        ))}
      </div>
    </div>
  )
}
