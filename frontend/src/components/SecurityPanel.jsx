export function SecurityPanel({
  card = {},
  audit = {},
  eventId = '',
  merchant = {},
}) {
  const last4 = card.maskedNumber?.slice(-4) || '0000'

  return (
    <div className="security-panel" role="region" aria-label="Security and Data Privacy">
      <div className="security-panel__header">
        <h4>🔒 Security &amp; Data Privacy</h4>
        <span className="pci-badge">
          <span className="pci-badge__icon">🛡️</span> PCI-DSS Level 1
        </span>
      </div>

      {/* Tokenization Flow */}
      <div className="token-flow">
        <div className="token-flow__step">
          <span className="token-flow__label">Raw PAN</span>
          <span className="token-flow__value token-flow__value--masked">
            •••• {last4}
          </span>
        </div>
        <div className="token-flow__arrow" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </div>
        <div className="token-flow__step">
          <span className="token-flow__label">SHA-256</span>
          <span className="token-flow__value token-flow__value--hash">
            🔐 Hashing
          </span>
        </div>
        <div className="token-flow__arrow" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </div>
        <div className="token-flow__step">
          <span className="token-flow__label">Secure Token</span>
          <span className="token-flow__value token-flow__value--token">
            {card.cardToken?.slice(0, 14) || 'card_..'}…
          </span>
        </div>
      </div>

      {/* Security Indicators */}
      <div className="security-indicators">
        <div className="security-indicator">
          <span className="indicator-icon">🛡️</span>
          <div>
            <strong>Zero Raw PANs Stored</strong>
            <span>All card data tokenized before persistence</span>
          </div>
        </div>
        <div className="security-indicator">
          <span className="indicator-icon">🔑</span>
          <div>
            <strong>AES-256 Encryption</strong>
            <span>Data encrypted at rest and in transit</span>
          </div>
        </div>
        <div className="security-indicator">
          <span className="indicator-icon">📋</span>
          <div>
            <strong>Full Audit Trail</strong>
            <span>Every decision logged with immutable event ID</span>
          </div>
        </div>
        <div className="security-indicator">
          <span className="indicator-icon">🔄</span>
          <div>
            <strong>Token Rotation Ready</strong>
            <span>Cryptographic tokens can be rotated without data loss</span>
          </div>
        </div>
      </div>

      {/* Audit Details */}
      <div className="security-audit">
        <div className="security-audit__row">
          <span className="security-audit__key">Event ID</span>
          <code>{eventId}</code>
        </div>
        <div className="security-audit__row">
          <span className="security-audit__key">Card Token</span>
          <code>{card.cardToken?.slice(0, 24)}…</code>
        </div>
        <div className="security-audit__row">
          <span className="security-audit__key">Account Token</span>
          <code>{card.accountToken?.slice(0, 24)}…</code>
        </div>
        <div className="security-audit__row">
          <span className="security-audit__key">Merchant ID</span>
          <code>{merchant.id?.slice(0, 24)}…</code>
        </div>
        <div className="security-audit__row">
          <span className="security-audit__key">Inference Latency</span>
          <span>{audit.latencyMs} ms</span>
        </div>
        <div className="security-audit__row">
          <span className="security-audit__key">Ledger Sync</span>
          <span className="security-audit__synced">
            {audit.dashboardSynced
              ? '✓ Synced to Core PostgreSQL Ledger'
              : '✓ In-Memory Ingested'}
          </span>
        </div>
      </div>
    </div>
  )
}
