import { useState } from 'react'

export function CreditCardVisual({
  brand = 'Visa',
  maskedNumber = '•••• •••• •••• 4532',
  cardholderName = 'ALEX MORGAN',
  expiry = '12/28',
  cvv = '321',
  status = 'neutral', // 'neutral' | 'approved' | 'warning' | 'dangerous' | 'quarantined'
}) {
  const [isFlipped, setIsFlipped] = useState(false)

  const getBrandLogo = (name) => {
    switch (name) {
      case 'Mastercard':
        return (
          <div className="card-brand card-brand--mastercard">
            <span className="mc-circle mc-circle--red" />
            <span className="mc-circle mc-circle--yellow" />
          </div>
        )
      case 'American Express':
        return <div className="card-brand card-brand--amex">AMEX</div>
      case 'Discover':
        return <div className="card-brand card-brand--discover">DISCOVER</div>
      default:
        return <div className="card-brand card-brand--visa">VISA</div>
    }
  }

  const statusClass =
    {
      approved: 'credit-card--approved',
      warning: 'credit-card--warning',
      dangerous: 'credit-card--dangerous',
      quarantined: 'credit-card--quarantined',
      neutral: '',
    }[status] ?? ''

  return (
    <div className="card-container">
      <div
        className={`credit-card ${statusClass} ${isFlipped ? 'credit-card--flipped' : ''}`}
        onClick={() => setIsFlipped((prev) => !prev)}
        role="button"
        tabIndex={0}
        aria-label="Toggle credit card front and back view"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setIsFlipped((prev) => !prev)
          }
        }}
      >
        {/* FRONT VIEW */}
        <div className="card-side card-side--front">
          <div className="credit-card__top">
            <div className="credit-card__chip">
              <div className="chip-lines" />
            </div>
            <div className="credit-card__contactless">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M8.5 16.5a5 5 0 0 1 0-7" strokeLinecap="round" />
                <path d="M12 19a8.5 8.5 0 0 0 0-12" strokeLinecap="round" />
                <path d="M15.5 21.5a12 12 0 0 0 0-17" strokeLinecap="round" />
              </svg>
            </div>
            <div className="credit-card__network">{getBrandLogo(brand)}</div>
          </div>

          <div className="credit-card__number">{maskedNumber}</div>

          <div className="credit-card__bottom">
            <div className="credit-card__holder">
              <span className="card-label">CARDHOLDER</span>
              <span className="card-value">{cardholderName.toUpperCase() || 'VALUED CUSTOMER'}</span>
            </div>
            <div className="credit-card__expiry">
              <span className="card-label">EXPIRES</span>
              <span className="card-value">{expiry || 'MM/YY'}</span>
            </div>
          </div>

          <div className="credit-card__hologram" />
        </div>

        {/* BACK VIEW */}
        <div className="card-side card-side--back">
          <div className="card-back__magnetic-strip" />
          <div className="card-back__signature-bar">
            <div className="signature-pattern" />
            <div className="cvv-display">
              <span className="cvv-label">CVV</span>
              <span className="cvv-code">{cvv || '•••'}</span>
            </div>
          </div>
          <div className="card-back__notice">
            <p>Authorized Signature — Not Valid Unless Signed</p>
            <p>Issued under Sentinel AI Fraud Protection Protocol. EMV-Compliant.</p>
          </div>
          <div className="card-back__network-watermark">{getBrandLogo(brand)}</div>
        </div>
      </div>

      <div className="card-flip-prompt">
        <button
          type="button"
          className="flip-toggle-btn"
          onClick={() => setIsFlipped((prev) => !prev)}
        >
          🔄 {isFlipped ? 'View Front Side' : 'View Back Side (CVV & Magnetic Stripe)'}
        </button>
      </div>
    </div>
  )
}
