export function SegmentedControl({ activeValue, label, onChange, options }) {
  return (
    <div aria-label={label} className="segmented-control" role="group">
      {options.map((option) => (
        <button
          aria-pressed={activeValue === option.value}
          className="segmented-control__option"
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
