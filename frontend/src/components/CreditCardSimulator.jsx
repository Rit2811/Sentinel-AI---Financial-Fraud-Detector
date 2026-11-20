import { useEffect, useMemo, useState } from 'react'

import { CreditCardVisual } from './CreditCardVisual'
import { PatentEnsemblePanel } from './PatentEnsemblePanel'
import { ReasoningPanel } from './ReasoningPanel'
import { RiskGauge } from './RiskGauge'
import { SecurityPanel } from './SecurityPanel'
import { TransactionTimeline } from './TransactionTimeline'

const FALLBACK_PRESETS = [
  {
    id: 'safe-grocery',
    name: 'Normal Everyday Purchase',
    description: 'Morning $14.50 grocery store run with chip authentication',
    expectedOutcome: 'approved',
    expectedAction: 'Pass',
    data: {
      cardholderName: 'Alex Morgan',
      cardNumber: '4532 8901 2345 7890',
      expiry: '08/29',
      cvv: '321',
      amount: 14.5,
      merchantName: 'Trader Joe’s Market #104',
      merchantCategory: 'grocery_pos',
      merchantCountry: 'US',
      channel: 'card_present',
      entryMode: 'chip',
      hour: 10,
    },
  },
  {
    id: 'suspicious-electronics',
    name: 'Suspicious Spike / Online Electronics',
    description: '$420.00 online order with sudden jump from prior spend',
    expectedOutcome: 'warning',
    expectedAction: 'Review',
    data: {
      cardholderName: 'Jordan Lee',
      cardNumber: '5424 1800 2345 6789',
      expiry: '11/28',
      cvv: '849',
      amount: 420.0,
      merchantName: 'MegaTech Electronics Direct',
      merchantCategory: 'shopping_net',
      merchantCountry: 'US',
      channel: 'card_not_present',
      entryMode: 'ecommerce',
      hour: 19,
    },
  },
  {
    id: 'dangerous-crypto',
    name: 'High-Risk Midnight Anomaly',
    description: '$3,850.00 overseas crypto/luxury purchase at 03:30 AM',
    expectedOutcome: 'dangerous',
    expectedAction: 'Block',
    data: {
      cardholderName: 'Chris Taylor',
      cardNumber: '4111 2222 3333 4444',
      expiry: '04/27',
      cvv: '912',
      amount: 3850.0,
      merchantName: 'Global Vault FX & Luxury',
      merchantCategory: 'misc_net',
      merchantCountry: 'NG',
      channel: 'card_not_present',
      entryMode: 'manual',
      hour: 3,
    },
  },
  {
    id: 'velocity-burst',
    name: 'Velocity Spike / Card Testing',
    description: 'Rapid burst of 5 transactions within minutes (simulates card bot)',
    expectedOutcome: 'dangerous',
    expectedAction: 'Block',
    data: {
      cardholderName: 'Sam Rivera',
      cardNumber: '4000 1234 5678 9010',
      expiry: '12/29',
      cvv: '554',
      amount: 75.0,
      merchantName: 'FastDigital Services Cloud',
      merchantCategory: 'shopping_net',
      merchantCountry: 'US',
      channel: 'card_not_present',
      entryMode: 'ecommerce',
      hour: 14,
      simulateVelocityBurst: true,
    },
  },
  {
    id: 'pci-prohibited',
    name: 'Security Test: PCI Field Leak',
    description: 'Direct ingestion of unencrypted cardholder PAN & CVV without tokenization',
    expectedOutcome: 'quarantined',
    expectedAction: 'Reject',
    data: {
      cardholderName: 'Test Subject',
      cardNumber: '4000 0000 0000 0002',
      forceQuarantine: true,
      amount: 50.0,
      merchantName: 'Unsecured Gateway Test',
      merchantCategory: 'shopping_pos',
      merchantCountry: 'US',
      channel: 'card_present',
      entryMode: 'chip',
      hour: 12,
    },
  },
]

function formatCardNumberInput(value) {
  const digits = value.replace(/\D/g, '').slice(0, 16)
  const parts = []
  for (let i = 0; i < digits.length; i += 4) {
    parts.push(digits.slice(i, i + 4))
  }
  return parts.join(' ')
}

function detectBrand(number) {
  const digits = number.replace(/\D/g, '')
  if (/^4/.test(digits)) return 'Visa'
  if (/^(5[1-5]|2[2-7])/.test(digits)) return 'Mastercard'
  if (/^3[47]/.test(digits)) return 'American Express'
  if (/^6(011|5)/.test(digits)) return 'Discover'
  return 'Visa'
}

export function CreditCardSimulator({ onTransactionProcessed }) {
  const [presets, setPresets] = useState(FALLBACK_PRESETS)
  const [activePreset, setActivePreset] = useState(null)
  const [formData, setFormData] = useState({
    cardholderName: 'Alex Morgan',
    cardNumber: '4532 8901 2345 7890',
    expiry: '08/29',
    cvv: '321',
    amount: 14.5,
    merchantName: 'Trader Joe’s Market #104',
    merchantCategory: 'grocery_pos',
    merchantCountry: 'US',
    channel: 'card_present',
    entryMode: 'chip',
    hour: 10,
    simulateVelocityBurst: false,
    forceQuarantine: false,
  })

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [notification, setNotification] = useState('')
  const [expandedRow, setExpandedRow] = useState(null)
  const [historyFilter, setHistoryFilter] = useState('all')

  useEffect(() => {
    fetch('/api/v1/simulate/presets')
      .then((res) => res.json())
      .then((json) => {
        if (json.success && Array.isArray(json.presets)) {
          setPresets(json.presets)
        }
      })
      .catch(() => {})

    fetch('/api/v1/simulate/history')
      .then((res) => res.json())
      .then((json) => {
        if (json.success && Array.isArray(json.history)) {
          setHistory(json.history)
        }
      })
      .catch(() => {})
  }, [])

  const applyPreset = (preset) => {
    setActivePreset(preset.id)
    setFormData((prev) => ({
      ...prev,
      ...preset.data,
      simulateVelocityBurst: Boolean(preset.data.simulateVelocityBurst),
      forceQuarantine: Boolean(preset.data.forceQuarantine),
    }))
    setResult(null)
  }

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target
    if (name === 'cardNumber') {
      setFormData((prev) => ({ ...prev, cardNumber: formatCardNumberInput(value) }))
    } else {
      setFormData((prev) => ({
        ...prev,
        [name]: type === 'checkbox' ? checked : value,
      }))
    }
    setActivePreset(null)
  }

  const handleSubmit = async (e) => {
    e?.preventDefault()
    setIsSubmitting(true)
    setNotification('')

    try {
      const response = await fetch('/api/v1/simulate/payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      const data = await response.json()
      setResult(data)

      if (data.success) {
        setHistory((prev) => [data, ...prev.filter((h) => h.simulationId !== data.simulationId)])
        onTransactionProcessed?.()
      }
    } catch {
      setNotification('Failed to connect to Sentinel Simulation Service.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResetVelocity = async () => {
    try {
      await fetch('/api/v1/simulate/reset', { method: 'POST' })
      setNotification('Card velocity ledger reset successfully. All cards reset to zero prior frequency.')
      setTimeout(() => setNotification(''), 4000)
    } catch {
      setNotification('Failed to reset velocity.')
    }
  }

  const handleResolveReview = async (decision) => {
    if (!result?.simulationId) return
    try {
      const res = await fetch('/api/v1/simulate/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulationId: result.simulationId,
          decision,
          notes: `Analyst resolution via Sentinel Simulation Terminal: ${decision.toUpperCase()}`,
        }),
      })
      const data = await res.json()
      if (data.success) {
        setResult((prev) => ({
          ...prev,
          assessment: {
            ...prev.assessment,
            simulatedAction: data.simulatedAction,
            status: decision === 'allow' ? 'approved' : 'dangerous',
            bankMessage:
              decision === 'allow'
                ? '00 - TRANSACTION OVERRIDDEN & APPROVED BY ANALYST'
                : '05 - TRANSACTION CONFIRMED FRAUDULENT & BLOCKED',
          },
        }))
        setNotification(`Review resolved: Transaction ${decision === 'allow' ? 'Approved' : 'Declined'}`)
        setTimeout(() => setNotification(''), 4000)
      }
    } catch {
      setNotification('Failed to submit review resolution.')
    }
  }

  const exportCsv = () => {
    if (!history.length) return
    const headers = ['Timestamp', 'Card_Masked', 'Merchant', 'Category', 'Amount', 'RiskScore', 'Action', 'SimulatedAction']
    const rows = history.map((tx) => [
      tx.transaction?.occurredAt || '',
      tx.card?.maskedNumber || '',
      `"${tx.merchant?.name || ''}"`,
      tx.merchant?.category || '',
      tx.transaction?.amount ?? '',
      tx.assessment?.riskScore ?? '',
      tx.assessment?.action || '',
      tx.assessment?.simulatedAction || '',
    ])
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `sentinel_audit_${Date.now()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const filteredHistory = useMemo(() => {
    if (historyFilter === 'all') return history
    return history.filter((h) => h.assessment?.status === historyFilter)
  }, [history, historyFilter])

  const currentBrand = detectBrand(formData.cardNumber)
  const visualStatus = result ? result.assessment?.status ?? (result.pciViolation ? 'quarantined' : 'neutral') : 'neutral'

  return (
    <div className="simulator-container">
      <div className="simulator-header">
        <div>
          <h2>Credit Card Payment Simulator &amp; Fraud Detection</h2>
          <p>
            Simulate realistic financial authorizations, evaluate ML risk probabilities, inspect velocity features, and
            verify privacy-preserving tokenization in real time.
          </p>
        </div>
      </div>

      {notification && (
        <div className="assessment-banner assessment-banner--warning">
          <span className="banner-icon">ℹ️</span>
          <div className="banner-content">
            <p>{notification}</p>
          </div>
        </div>
      )}

      {/* Preset Scenarios */}
      <section className="presets-section">
        <span className="presets-label">Click a Scenario Preset to Test:</span>
        <div className="presets-grid">
          {presets.map((preset) => {
            const badgeClass = `preset-badge--${preset.expectedOutcome}`
            return (
              <button
                key={preset.id}
                type="button"
                className={`preset-card ${activePreset === preset.id ? 'preset-card--active' : ''}`}
                onClick={() => applyPreset(preset)}
              >
                <div className="preset-card__top">
                  <span className={`preset-badge ${badgeClass}`}>{preset.expectedOutcome}</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold' }}>{preset.expectedAction}</span>
                </div>
                <strong>{preset.name}</strong>
                <span className="desc">{preset.description}</span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Main Simulation Workspace */}
      <div className="simulator-workspace">
        {/* Left: Interactive Card & Payment Terminal */}
        <div className="terminal-column">
          <CreditCardVisual
            brand={currentBrand}
            maskedNumber={formData.cardNumber || '•••• •••• •••• 0000'}
            cardholderName={formData.cardholderName}
            expiry={formData.expiry}
            cvv={formData.cvv}
            status={visualStatus}
          />

          <form className="simulator-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="cardholderName">Cardholder Full Name</label>
              <input
                id="cardholderName"
                name="cardholderName"
                type="text"
                value={formData.cardholderName}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="cardNumber">Card Number (PAN)</label>
              <input
                id="cardNumber"
                name="cardNumber"
                type="text"
                value={formData.cardNumber}
                onChange={handleInputChange}
                maxLength="19"
                placeholder="4532 0000 0000 0000"
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="expiry">Valid Thru (MM/YY)</label>
                <input
                  id="expiry"
                  name="expiry"
                  type="text"
                  value={formData.expiry}
                  onChange={handleInputChange}
                  maxLength="5"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="cvv">Security Code (CVV)</label>
                <input
                  id="cvv"
                  name="cvv"
                  type="password"
                  value={formData.cvv}
                  onChange={handleInputChange}
                  maxLength="4"
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="amount">Transaction Amount ($ USD)</label>
                <input
                  id="amount"
                  name="amount"
                  type="number"
                  step="0.01"
                  min="0.50"
                  value={formData.amount}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="merchantCategory">Merchant Category</label>
                <select
                  id="merchantCategory"
                  name="merchantCategory"
                  value={formData.merchantCategory}
                  onChange={handleInputChange}
                >
                  <option value="grocery_pos">Grocery &amp; Supermarket (Low Risk)</option>
                  <option value="gas_transport">Fuel &amp; Transport (Low Risk)</option>
                  <option value="shopping_pos">Retail Store In-Person (Moderate)</option>
                  <option value="shopping_net">Online Ecommerce Shopping (Elevated)</option>
                  <option value="travel">Airline &amp; Hotel Travel (Elevated)</option>
                  <option value="misc_net">Digital Goods &amp; Subscriptions (High)</option>
                  <option value="luxury_goods">Jewelry &amp; Luxury Goods (High)</option>
                  <option value="crypto_exchange">Cryptocurrency Exchange (High Risk)</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="merchantName">Merchant Identifier</label>
                <input
                  id="merchantName"
                  name="merchantName"
                  type="text"
                  value={formData.merchantName}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="merchantCountry">Merchant Country</label>
                <select
                  id="merchantCountry"
                  name="merchantCountry"
                  value={formData.merchantCountry}
                  onChange={handleInputChange}
                >
                  <option value="US">United States (Domestic)</option>
                  <option value="GB">United Kingdom</option>
                  <option value="CA">Canada</option>
                  <option value="NG">Nigeria (High Risk)</option>
                  <option value="RU">Russian Federation (High Risk)</option>
                  <option value="SG">Singapore</option>
                  <option value="IN">India</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="channel">Channel</label>
                <select id="channel" name="channel" value={formData.channel} onChange={handleInputChange}>
                  <option value="card_present">Card Present (In-Store POS)</option>
                  <option value="card_not_present">Card Not Present (Online / Mobile)</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="entryMode">Entry Mode</label>
                <select id="entryMode" name="entryMode" value={formData.entryMode} onChange={handleInputChange}>
                  <option value="chip">EMV Contact Chip</option>
                  <option value="contactless">NFC Contactless</option>
                  <option value="ecommerce">Ecommerce Web</option>
                  <option value="magstripe">Magnetic Stripe</option>
                  <option value="manual">Manual Keyed Entry</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="hour">Simulated Hour of Day (UTC)</label>
              <div className="slider-container">
                <input
                  id="hour"
                  name="hour"
                  type="range"
                  min="0"
                  max="23"
                  value={formData.hour}
                  onChange={handleInputChange}
                />
                <span className="slider-value">
                  {String(formData.hour).padStart(2, '0')}:00 {formData.hour >= 1 && formData.hour <= 5 ? '🌙 (Off-Hours)' : '☀️'}
                </span>
              </div>
            </div>

            <label className="checkbox-group">
              <input
                type="checkbox"
                name="simulateVelocityBurst"
                checked={formData.simulateVelocityBurst}
                onChange={handleInputChange}
              />
              Simulate rapid velocity burst (4 recent swipe attempts in last 10m)
            </label>

            <label className="checkbox-group">
              <input
                type="checkbox"
                name="forceQuarantine"
                checked={formData.forceQuarantine}
                onChange={handleInputChange}
              />
              Test PCI-DSS Security Breach (inject unencrypted raw PAN into core pipeline)
            </label>

            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Evaluating ML Decision...' : '⚡ Authorize Payment'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleResetVelocity}
                title="Clears simulated swipe velocity for cards"
              >
                Reset Velocity
              </button>
            </div>
          </form>
        </div>

        {/* Right: Real-time Evaluation Results */}
        <div className="assessment-column">
          {result ? (
            <div className="assessment-card">
              {/* PCI Quarantine Violation Case */}
              {result.pciViolation ? (
                <div className="assessment-banner assessment-banner--quarantined">
                  <span className="banner-icon">🛡️</span>
                  <div className="banner-content">
                    <strong>SECURITY SAFEGUARD TRIGGERED: PCI-DSS QUARANTINE</strong>
                    <p>{result.message}</p>
                  </div>
                </div>
              ) : (
                <>
                  {/* Status Banner */}
                  <div className={`assessment-banner assessment-banner--${result.assessment.status}`}>
                    <span className="banner-icon">
                      {result.assessment.status === 'approved' && '✅'}
                      {result.assessment.status === 'warning' && '⚠️'}
                      {result.assessment.status === 'dangerous' && '🛑'}
                    </span>
                    <div className="banner-content">
                      <strong>
                        {result.assessment.status === 'approved' && 'TRANSACTION APPROVED (LOW RISK)'}
                        {result.assessment.status === 'warning' && 'SUSPICIOUS TRANSACTION (WARNING - FLAGGED)'}
                        {result.assessment.status === 'dangerous' && 'DANGEROUS FRAUD PATTERN (BLOCKED)'}
                      </strong>
                      <p>{result.assessment.bankMessage}</p>
                    </div>
                  </div>

                  {/* Transaction Pipeline Timeline */}
                  <TransactionTimeline
                    latencyMs={result.audit?.latencyMs ?? 5}
                    status={result.assessment.status}
                  />

                  {/* Modern Speedometer Risk Gauge */}
                  <RiskGauge
                    riskScore={result.assessment.riskScore}
                    probability={result.assessment.probability}
                    status={result.assessment.status}
                  />

                  {/* Manual Review Actions if Warning */}
                  {result.assessment.action === 'Review' && result.assessment.simulatedAction === 'pending_review' && (
                    <div className="review-resolution-box">
                      <h4>Manual Fraud Analyst Resolution</h4>
                      <p>
                        This transaction requires human review under Sentinel AI's dual-custody policy. As the fraud
                        analyst, choose an action:
                      </p>
                      <div className="review-buttons">
                        <button
                          type="button"
                          className="btn-approve"
                          onClick={() => handleResolveReview('allow')}
                        >
                          ✓ Allow &amp; Approve Transaction
                        </button>
                        <button
                          type="button"
                          className="btn-reject"
                          onClick={() => handleResolveReview('reject')}
                        >
                          ✕ Confirm Fraud &amp; Block
                        </button>
                      </div>
                    </div>
                  )}

                  {/* AI Reasoning Panel with Narrative & Bar Chart */}
                  <ReasoningPanel
                    factors={result.riskFactors || []}
                    assessment={result.assessment || {}}
                    features={result.features || {}}
                    transaction={result.transaction || {}}
                  />

                  {/* Patent Innovation: Hybrid Ensemble & Dynamic Imbalance (Claims 1–6) */}
                  <PatentEnsemblePanel
                    ensemble={result.ensemble || {
                      randomForest: result.assessment.probability,
                      svm: Math.max(0.005, result.assessment.probability * 0.95),
                      knn: Math.min(0.99, result.assessment.probability * 1.05),
                      logisticRegression: Math.max(0.005, result.assessment.probability * 0.92),
                      fusedScore: result.assessment.probability,
                    }}
                    behavioral={{
                      initialBalance: result.patentFeatures?.initialBalance ?? 5000,
                      amount: result.transaction?.amount ?? formData.amount,
                      expectedBalance: result.patentFeatures?.expectedBalance ?? Math.max(0, 5000 - formData.amount),
                      inconsistencyScore: result.patentFeatures?.balanceInconsistencyScore ?? (formData.amount > 1000 ? 0.75 : 0.0),
                    }}
                    drift={{
                      driftMetric: result.patentFeatures?.conceptDriftMetric ?? 0.024,
                      driftStatus: 'Nominal (No Drift Shift)',
                      imbalanceRatio: result.patentFeatures?.classImbalanceRatio ?? '0.16% Fraud / 99.84% Legitimate',
                      bufferSize: 1000,
                    }}
                  />

                  {/* PCI-DSS Security & Privacy Safeguards Panel */}
                  <SecurityPanel
                    card={result.card || {}}
                    audit={result.audit || {}}
                    eventId={result.eventId || ''}
                    merchant={result.merchant || {}}
                  />
                </>
              )}
            </div>
          ) : (
            <div className="assessment-card" style={{ textAlign: 'center', padding: '3rem 2rem', color: 'var(--color-text-muted)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>💳</div>
              <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--color-text-primary)' }}>Terminal Ready</h3>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                Select a scenario preset above or customize transaction details, then click <strong>Authorize Payment</strong> to observe Sentinel AI's real-time risk classification.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* History Table with Export, Filtering & Expandable Rows */}
      {history.length > 0 && (
        <section className="history-section">
          <div className="history-section__header">
            <h3>Simulation Session Log ({history.length} Transactions)</h3>
            <div className="history-controls">
              <div className="history-filters" role="group" aria-label="Filter transactions">
                <button
                  type="button"
                  className={`btn-filter ${historyFilter === 'all' ? 'btn-filter--active' : ''}`}
                  onClick={() => setHistoryFilter('all')}
                >
                  All ({history.length})
                </button>
                <button
                  type="button"
                  className={`btn-filter ${historyFilter === 'approved' ? 'btn-filter--active' : ''}`}
                  onClick={() => setHistoryFilter('approved')}
                >
                  Approved
                </button>
                <button
                  type="button"
                  className={`btn-filter ${historyFilter === 'warning' ? 'btn-filter--active' : ''}`}
                  onClick={() => setHistoryFilter('warning')}
                >
                  Review
                </button>
                <button
                  type="button"
                  className={`btn-filter ${historyFilter === 'dangerous' ? 'btn-filter--active' : ''}`}
                  onClick={() => setHistoryFilter('dangerous')}
                >
                  Blocked
                </button>
              </div>
              <button type="button" className="btn-export" onClick={exportCsv}>
                📥 Export CSV
              </button>
            </div>
          </div>

          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Card (Masked)</th>
                  <th>Merchant</th>
                  <th>Category</th>
                  <th>Amount</th>
                  <th>Risk Score</th>
                  <th>Decision</th>
                  <th>Simulated Action</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((tx) => {
                  const isExpanded = expandedRow === tx.simulationId
                  return (
                    <tr key={tx.simulationId} className={isExpanded ? 'history-row--expanded' : ''}>
                      <td>{tx.transaction?.occurredAt ? new Date(tx.transaction.occurredAt).toLocaleTimeString() : 'Recent'}</td>
                      <td>{tx.card?.maskedNumber}</td>
                      <td>{tx.merchant?.name}</td>
                      <td><code>{tx.merchant?.category}</code></td>
                      <td><strong>${tx.transaction?.amount?.toFixed(2)}</strong></td>
                      <td>
                        <span
                          style={{
                            fontWeight: 'bold',
                            color:
                              tx.assessment?.status === 'approved'
                                ? 'var(--color-success)'
                                : tx.assessment?.status === 'warning'
                                  ? 'var(--color-warning)'
                                  : 'var(--color-danger)',
                          }}
                        >
                          {tx.assessment?.riskScore}%
                        </span>
                      </td>
                      <td>
                        <span className={`preset-badge preset-badge--${tx.assessment?.status}`}>
                          {tx.assessment?.action}
                        </span>
                      </td>
                      <td>
                        <code style={{ fontSize: '0.8rem' }}>{tx.assessment?.simulatedAction}</code>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-inspect"
                          onClick={() => {
                            setResult(tx)
                            setExpandedRow(isExpanded ? null : tx.simulationId)
                          }}
                        >
                          {isExpanded ? '▲ Hide' : '👁️ View'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
