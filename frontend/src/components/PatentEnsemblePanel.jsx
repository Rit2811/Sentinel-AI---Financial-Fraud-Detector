export function PatentEnsemblePanel({
  ensemble = {
    randomForest: 0.05,
    svm: 0.04,
    knn: 0.06,
    logisticRegression: 0.05,
    fusedScore: 0.05,
  },
  behavioral = {
    initialBalance: 5000,
    amount: 14.5,
    expectedBalance: 4985.5,
    inconsistencyScore: 0.0,
  },
  drift = {
    driftMetric: 0.024,
    driftStatus: 'Nominal (No Drift)',
    imbalanceRatio: '0.16% Fraud / 99.84% Legitimate',
    bufferSize: 1000,
  },
}) {
  const models = [
    {
      name: 'Random Forest (Tree-Based)',
      tag: 'Tree Ensemble',
      score: ensemble.randomForest,
      desc: 'Non-linear multi-split bagging across 21 Sparkov behavioral feature trees.',
    },
    {
      name: 'Support Vector Machine (Margin-Based)',
      tag: 'Hyperplane',
      score: ensemble.svm,
      desc: 'Max-margin hyperplane with RBF kernel separating fraud boundary.',
    },
    {
      name: 'K-Nearest Neighbors (Distance-Based)',
      tag: 'Instance Metric',
      score: ensemble.knn,
      desc: 'Euclidean distance metric against bounded reference sliding window.',
    },
    {
      name: 'Logistic Regression (Linear Probabilistic)',
      tag: 'Sigmoid Logit',
      score: ensemble.logisticRegression,
      desc: 'Calibrated log-odds baseline establishing legitimate prior probability.',
    },
  ]

  return (
    <div className="patent-module-card" role="region" aria-label="Patent Innovations Framework">
      <div className="patent-module-card__header">
        <div>
          <h4>📜 Patent Pipeline: Real-Time Stream Innovation &amp; Hybrid Ensemble</h4>
          <span className="patent-module-subtitle">
            IDF Sharda Univ: Dynamic Class-Imbalance &amp; Multi-Learner Fusion (Fig. 2)
          </span>
        </div>
        <span className="patent-status-badge">PATENT CLAIMS 1–6</span>
      </div>

      {/* 1. Hybrid Ensemble Breakdown */}
      <div className="patent-subpanel">
        <span className="patent-subpanel__title">
          1. Heterogeneous Hybrid Ensemble Fusion (Patent Claim 4)
        </span>
        <div className="ensemble-grid">
          {models.map((m) => (
            <div key={m.name} className="ensemble-card">
              <div className="ensemble-card__top">
                <span className="ensemble-tag">{m.tag}</span>
                <strong className="ensemble-score">{(m.score * 100).toFixed(1)}%</strong>
              </div>
              <strong className="ensemble-name">{m.name}</strong>
              <p className="ensemble-desc">{m.desc}</p>
              <div className="ensemble-bar-track">
                <div
                  className="ensemble-bar-fill"
                  style={{
                    width: `${Math.min(100, Math.max(3, m.score * 100))}%`,
                    background:
                      m.score >= 0.25
                        ? 'var(--color-danger)'
                        : m.score >= 0.1
                          ? 'var(--color-warning)'
                          : 'var(--color-success)',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Real-Time Feature Engineering: Balance Inconsistency */}
      <div className="patent-subpanel">
        <span className="patent-subpanel__title">
          2. Real-Time Behavioral Feature: Balance Inconsistency (Patent Claim 2)
        </span>
        <div className="behavioral-grid">
          <div className="behavioral-item">
            <span className="b-label">Initial Account Balance</span>
            <strong className="b-value">${behavioral.initialBalance.toFixed(2)}</strong>
          </div>
          <div className="behavioral-item">
            <span className="b-label">Transaction Deduction</span>
            <strong className="b-value" style={{ color: 'var(--color-danger)' }}>
              -${behavioral.amount.toFixed(2)}
            </strong>
          </div>
          <div className="behavioral-item">
            <span className="b-label">Computed Expected Balance</span>
            <strong className="b-value">${behavioral.expectedBalance.toFixed(2)}</strong>
          </div>
          <div className="behavioral-item">
            <span className="b-label">Balance Inconsistency Score</span>
            <strong
              className="b-value"
              style={{
                color:
                  behavioral.inconsistencyScore > 0.5
                    ? 'var(--color-danger)'
                    : 'var(--color-success)',
              }}
            >
              {behavioral.inconsistencyScore.toFixed(3)}{' '}
              {behavioral.inconsistencyScore === 0 ? '✓ Consistent' : '⚠️ Anomalous Delta'}
            </strong>
          </div>
        </div>
      </div>

      {/* 3. Adaptive Imbalance & Concept Drift Monitoring */}
      <div className="patent-subpanel">
        <span className="patent-subpanel__title">
          3. Dynamic Class-Imbalance &amp; Concept Drift Monitoring (Patent Claims 3 &amp; 5)
        </span>
        <div className="drift-grid">
          <div className="drift-card">
            <span className="drift-key">Dynamic Class Imbalance</span>
            <strong className="drift-val">{drift.imbalanceRatio}</strong>
            <span className="drift-sub">Maintains bounded sliding window (Size: {drift.bufferSize})</span>
          </div>
          <div className="drift-card">
            <span className="drift-key">Concept Drift Shift Index (Δ)</span>
            <strong className="drift-val" style={{ color: 'var(--color-success)' }}>
              {drift.driftMetric.toFixed(3)}
            </strong>
            <span className="drift-sub">Threshold: 0.150 • Status: {drift.driftStatus}</span>
          </div>
          <div className="drift-card">
            <span className="drift-key">Adaptive Model State</span>
            <strong className="drift-val">Serving (Calibrated RF)</strong>
            <span className="drift-sub">Incremental rebalance buffer responsive</span>
          </div>
        </div>
      </div>
    </div>
  )
}
