import { ActivityChart } from './ActivityChart'
import { Card } from './Card'
import { SegmentedControl } from './SegmentedControl'

export function ActivityPanel({
  activeRange,
  chartLabel,
  data,
  emptyMessage,
  hasActivity,
  labels,
  onRangeChange,
  rangeLabel,
  ranges,
  title,
  tooltipIndex,
  tooltipLabels,
}) {
  return (
    <Card
      actions={
        <SegmentedControl
          activeValue={activeRange}
          label={rangeLabel}
          onChange={onRangeChange}
          options={ranges}
        />
      }
      className="activity-panel"
      title={title}
    >
      <ActivityChart
        ariaLabel={chartLabel}
        data={data}
        key={activeRange}
        legendLabels={labels}
        tooltipIndex={tooltipIndex}
        tooltipLabels={tooltipLabels}
      />
      {!hasActivity && <p className="activity-panel__empty">{emptyMessage}</p>}
    </Card>
  )
}
