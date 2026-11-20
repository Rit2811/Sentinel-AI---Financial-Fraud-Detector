export function RiskGauge({ riskScore = 0, probability = 0, status = 'approved' }) {
  const cx = 120, cy = 110, r = 85, sw = 16
  const score = Math.max(0, Math.min(100, riskScore))

  const pctToAngle = (pct) => Math.PI * (1 - pct / 100)
  const toXY = (angle) => ({
    x: cx + r * Math.cos(angle),
    y: cy - r * Math.sin(angle),
  })

  function arc(sp, ep) {
    const s = toXY(pctToAngle(sp))
    const e = toXY(pctToAngle(ep))
    return `M ${s.x.toFixed(1)} ${s.y.toFixed(1)} A ${r} ${r} 0 0 0 ${e.x.toFixed(1)} ${e.y.toFixed(1)}`
  }

  const nl = r - 20
  const needleRotation = 180 + (score / 100) * 180

  const color =
    status === 'approved'
      ? '#10b981'
      : status === 'warning'
        ? '#f59e0b'
        : '#ef4444'

  const ticks = [10, 25].map((t) => {
    const a = pctToAngle(t)
    const half = sw / 2 + 4
    return {
      pct: t,
      x1: cx + (r - half) * Math.cos(a),
      y1: cy - (r - half) * Math.sin(a),
      x2: cx + (r + half) * Math.cos(a),
      y2: cy - (r + half) * Math.sin(a),
    }
  })

  return (
    <div
      className="radial-gauge"
      role="meter"
      aria-valuenow={riskScore}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Fraud risk score: ${riskScore} percent`}
    >
      <div className="radial-gauge__wrapper">
        <svg viewBox="0 0 240 135" className="radial-gauge__svg">
          {/* Background track */}
          <path
            d={arc(0, 100)}
            fill="none"
            className="radial-gauge__track"
            strokeWidth={sw}
            strokeLinecap="round"
          />

          {/* Zone overlays */}
          <path d={arc(0, 10)} fill="none" stroke="#10b981" strokeWidth={sw} strokeLinecap="butt" opacity="0.25" />
          <path d={arc(10, 25)} fill="none" stroke="#f59e0b" strokeWidth={sw} strokeLinecap="butt" opacity="0.25" />
          <path d={arc(25, 100)} fill="none" stroke="#ef4444" strokeWidth={sw} strokeLinecap="butt" opacity="0.25" />

          {/* Active fill up to current score */}
          {score > 0.5 && (
            <path
              d={arc(0, Math.min(score, 100))}
              fill="none"
              stroke={color}
              strokeWidth={sw}
              strokeLinecap="round"
              className="radial-gauge__fill"
            />
          )}

          {/* Threshold ticks */}
          {ticks.map((t) => (
            <line
              key={t.pct}
              x1={t.x1}
              y1={t.y1}
              x2={t.x2}
              y2={t.y2}
              className="radial-gauge__tick"
            />
          ))}

          {/* Needle (rotation-based for CSS animation) */}
          <g
            className="radial-gauge__needle-group"
            style={{
              transform: `rotate(${needleRotation}deg)`,
              transformOrigin: `${cx}px ${cy}px`,
            }}
          >
            <line x1={cx} y1={cy} x2={cx + nl} y2={cy} stroke={color} strokeWidth="3" strokeLinecap="round" />
          </g>
          <circle cx={cx} cy={cy} r="7" fill={color} />
          <circle cx={cx} cy={cy} r="3.5" className="radial-gauge__center-dot" />
        </svg>

        <div className="radial-gauge__score-display">
          <span className="radial-gauge__score" style={{ color }}>
            {riskScore}%
          </span>
          <span className="radial-gauge__prob">p = {probability}</span>
        </div>
      </div>

      <div className="radial-gauge__labels">
        <span>0% Safe</span>
        <span>10% Review</span>
        <span>25% Block</span>
        <span>100%</span>
      </div>
    </div>
  )
}
