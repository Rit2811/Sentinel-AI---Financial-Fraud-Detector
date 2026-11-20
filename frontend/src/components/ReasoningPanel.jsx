function generateNarrative(assessment, factors, features, transaction) {
  const { action, riskScore, probability } = assessment
  const amount = transaction?.amount || features?.amount || 0
  const hour = features?.hour ?? transaction?.simulatedHour ?? 0

  const riskFactors = factors.filter(
    (f) => f.severity === 'danger' || f.severity === 'warning',
  )
  const safeFactors = factors.filter((f) => f.severity === 'success')

  let intro
  if (action === 'Pass') {
    intro = `The Sentinel AI Random Forest ensemble classifier analyzed ${factors.length} behavioral features and determined this $${amount.toFixed(2)} transaction carries a LOW fraud probability of ${(probability * 100).toFixed(1)}% (risk score: ${riskScore}%). The transaction has been APPROVED for processing.`
  } else if (action === 'Review') {
    intro = `The Sentinel AI classifier flagged this $${amount.toFixed(2)} transaction with a MODERATE fraud probability of ${(probability * 100).toFixed(1)}% (risk score: ${riskScore}%). The transaction has been ESCALATED to a human fraud analyst for manual review under the dual-custody policy.`
  } else {
    intro = `The Sentinel AI classifier identified DANGEROUS fraud signals in this $${amount.toFixed(2)} transaction with a HIGH fraud probability of ${(probability * 100).toFixed(1)}% (risk score: ${riskScore}%). The transaction has been BLOCKED and declined automatically.`
  }

  let riskPart = ''
  if (riskFactors.length > 0) {
    const topRisk = riskFactors
      .slice(0, 3)
      .map((f) => f.name.split(':')[0].trim().toLowerCase())
    riskPart = ` Key risk drivers include ${topRisk.join(', ')}.`
  }

  let safePart = ''
  if (safeFactors.length > 0) {
    const topSafe = safeFactors
      .slice(0, 2)
      .map((f) => f.name.split(':')[0].trim().toLowerCase())
    safePart = ` Counterbalancing signals: ${topSafe.join(', ')}.`
  }

  const timePart =
    hour >= 1 && hour <= 5
      ? ` Transaction timing (${String(hour).padStart(2, '0')}:00 UTC) falls within the high-risk off-hours window.`
      : ''

  return intro + riskPart + safePart + timePart
}

export function ReasoningPanel({
  factors = [],
  assessment = {},
  features = {},
  transaction = {},
}) {
  const narrative = generateNarrative(assessment, factors, features, transaction)

  const parsedFactors = factors.map((f) => ({
    ...f,
    numericImpact: parseFloat(f.impact.replace(/[^-\d.]/g, '')),
  }))

  const maxAbs = Math.max(
    1,
    ...parsedFactors.map((f) => Math.abs(f.numericImpact)),
  )

  return (
    <div className="reasoning-panel" role="region" aria-label="AI Risk Analysis">
      <div className="reasoning-panel__header">
        <h4>🧠 AI Risk Analysis &amp; Reasoning</h4>
        <span className="reasoning-badge">{factors.length} signals analyzed</span>
      </div>

      {/* Narrative Summary */}
      <div className="reasoning-narrative">
        <p>{narrative}</p>
      </div>

      {/* Feature Importance Chart */}
      <div className="feature-chart">
        <span className="feature-chart__title">
          Feature Importance (Logit Contribution)
        </span>
        {parsedFactors.map((f, i) => (
          <div key={i} className="feature-bar-row">
            <div className="feature-bar-info">
              <strong>{f.name}</strong>
              <span>{f.description}</span>
            </div>
            <div className="feature-bar-track">
              <div
                className={`feature-bar feature-bar--${f.numericImpact > 0 ? 'risk' : 'safe'}`}
                style={{
                  width: `${(Math.abs(f.numericImpact) / maxAbs) * 100}%`,
                }}
              >
                <span className="feature-bar__value">{f.impact}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Raw Features Toggle */}
      <details className="reasoning-features">
        <summary>📋 View Raw Model Input Features</summary>
        <div className="features-grid">
          {Object.entries(features).map(([k, v]) => (
            <div key={k} className="feature-entry">
              <span className="feature-key">{k}</span>
              <span className="feature-val">{String(v)}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}
