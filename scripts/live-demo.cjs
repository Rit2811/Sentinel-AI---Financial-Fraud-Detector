const { chromium } = require('C:/Users/siddh/AppData/Roaming/npm/node_modules/playwright')

async function runLiveDemo() {
  console.log('🚀 Launching Google Chrome for Live Interactive Simulation Demo...')

  const browser = await chromium.launch({
    channel: 'chrome',
    headless: false,
    slowMo: 700,
    args: ['--start-maximized', '--window-size=1440,900'],
  })

  const context = await browser.newContext({
    viewport: null,
  })

  const page = await context.newPage()

  try {
    console.log('🌐 Navigating to Sentinel AI (http://localhost:15173)...')
    await page.goto('http://localhost:15173', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)

    const highlight = async (selector, color = '#0bb3a7') => {
      try {
        await page.evaluate(
          ({ sel, col }) => {
            const el = document.querySelector(sel)
            if (el) {
              el.style.outline = `3px solid ${col}`
              el.style.transition = 'outline 0.3s ease'
              setTimeout(() => {
                if (el) el.style.outline = ''
              }, 2500)
            }
          },
          { sel: selector, col: color },
        )
      } catch {}
    }

    // Reset velocity ledger before starting scenarios
    console.log('🔄 Resetting velocity ledger for clean baseline...')
    await page.click('button:has-text("Reset Velocity")')
    await page.waitForTimeout(1000)

    // -------------------------------------------------------------
    // SCENARIO 1: Normal Everyday Grocery Run (Pass / Approved)
    // -------------------------------------------------------------
    console.log('\n🟢 Step 1: Testing Normal Everyday Purchase ($14.50 Grocery)...')
    await page.click('button:has-text("Normal Everyday Purchase")')
    await highlight('.credit-card', '#08b45b')
    await page.waitForTimeout(1000)

    console.log('⚡ Authorizing payment...')
    await page.click('button:has-text("Authorize Payment")')
    await page.waitForSelector('.assessment-banner--approved', { timeout: 10000 })
    await highlight('.radial-gauge', '#08b45b')
    await highlight('.reasoning-panel', '#08b45b')
    console.log('✅ Result: Transaction Approved (Risk Score: Low, Radial Gauge & Timeline Updated)')
    await page.waitForTimeout(2500)

    // -------------------------------------------------------------
    // SCENARIO 2: Suspicious Electronics Order (Warning / Review)
    // -------------------------------------------------------------
    console.log('\n🟡 Step 2: Testing Suspicious Online Order ($420.00 Electronics)...')
    await page.click('button:has-text("Suspicious Spike / Online Electronics")')
    await highlight('.credit-card', '#c66a08')
    await page.waitForTimeout(1000)

    console.log('⚡ Authorizing payment...')
    await page.click('button:has-text("Authorize Payment")')
    await page.waitForSelector('.assessment-banner', { timeout: 10000 })
    const reviewBox = await page.$('.review-resolution-box')
    if (reviewBox) {
      await highlight('.review-resolution-box', '#c66a08')
      console.log('⚠️ Result: Flagged for Review (Dual-Custody Policy Triggered)')
      await page.waitForTimeout(2000)

      console.log('👤 Demonstrating Fraud Analyst Manual Resolution (Allow & Approve)...')
      await page.click('button:has-text("Allow & Approve")')
      await page.waitForTimeout(2000)
      console.log('✅ Analyst Resolution: Approved and logged to audit trail.')
    }
    await page.waitForTimeout(2000)

    // -------------------------------------------------------------
    // SCENARIO 3: High-Risk Midnight Crypto Anomaly (Block / Dangerous)
    // -------------------------------------------------------------
    console.log('\n🔴 Step 3: Testing High-Risk Midnight Anomaly ($3,850.00 Crypto at 03:30 AM)...')
    await page.click('button:has-text("High-Risk Midnight Anomaly")')
    await highlight('.credit-card', '#ff2028')
    await page.waitForTimeout(1000)

    console.log('⚡ Authorizing payment...')
    await page.click('button:has-text("Authorize Payment")')
    await page.waitForSelector('.assessment-banner--dangerous', { timeout: 10000 })
    await highlight('.radial-gauge', '#ff2028')
    await highlight('.security-panel', '#ff2028')
    console.log('🛑 Result: Transaction Automatically Blocked (High Risk Probability)')
    await page.waitForTimeout(2500)

    // -------------------------------------------------------------
    // SCENARIO 4: Security Test - PCI Prohibited Field Leak (Quarantine)
    // -------------------------------------------------------------
    console.log('\n🛡️ Step 4: Testing PCI-DSS Security Safeguards (Raw PAN Leak Injection)...')
    await page.click('button:has-text("Security Test: PCI")')
    await page.waitForTimeout(1000)

    console.log('⚡ Attempting unencrypted transmission...')
    await page.click('button:has-text("Authorize Payment")')
    await page.waitForSelector('.assessment-banner--quarantined', { timeout: 10000 })
    await highlight('.assessment-banner--quarantined', '#7e22ce')
    console.log('🛡️ Result: Intercepted & Quarantined under PCI-DSS Data Protection Policy.')
    await page.waitForTimeout(2500)

    // -------------------------------------------------------------
    // STEP 5: History Filtering & CSV Export
    // -------------------------------------------------------------
    console.log('\n📥 Step 5: Demonstrating History Filters & CSV Export...')
    await page.click('.btn-filter:has-text("Approved")')
    await page.waitForTimeout(1000)
    await page.click('.btn-filter:has-text("Blocked")')
    await page.waitForTimeout(1000)
    await page.click('.btn-filter:has-text("All")')
    await page.waitForTimeout(1000)

    console.log('📥 Triggering CSV Audit Download...')
    await page.click('button:has-text("Export CSV")')
    await page.waitForTimeout(1200)

    // -------------------------------------------------------------
    // STEP 6: Switch to the Ingestion Dashboard
    // -------------------------------------------------------------
    console.log('\n📊 Step 6: Switching to Live Ingestion & Stream Dashboard...')
    await page.click('button[role="tab"]:has-text("Ingestion & Stream Dashboard")')
    await page.waitForSelector('.dashboard__primary-grid', { timeout: 10000 })
    await highlight('.dashboard__metric-grid', '#3569d4')
    console.log('📈 Showing Evaluator: Real-time PostgreSQL ledger sync and stream telemetry.')
    await page.waitForTimeout(3500)

    // -------------------------------------------------------------
    // STEP 7: Return to Simulator for Presentation Finish
    // -------------------------------------------------------------
    console.log('\n💳 Step 7: Returning to Simulator for presentation finish...')
    await page.click('button[role="tab"]:has-text("Credit Card Simulator")')
    await page.waitForTimeout(2500)

    console.log('\n🎉 Live Interactive Demonstration Completed Successfully!')
  } catch (err) {
    console.error('❌ Demo encountered an issue:', err)
  } finally {
    console.log('Keeping Chrome open for 10 seconds for viewing...')
    await page.waitForTimeout(10000)
    await browser.close()
    console.log('Browser closed.')
  }
}

runLiveDemo()
