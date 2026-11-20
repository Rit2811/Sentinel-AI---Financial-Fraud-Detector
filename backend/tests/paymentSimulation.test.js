import { jest } from '@jest/globals'
import request from 'supertest'

import { createApp } from '../src/app.js'
import {
  createPaymentSimulationService,
  detectCardBrand,
  maskCardNumber,
  sha256,
} from '../src/services/paymentSimulationService.js'

describe('Payment Simulation Service & Utilities', () => {
  test('detects card brands correctly', () => {
    expect(detectCardBrand('4532111122223333')).toBe('Visa')
    expect(detectCardBrand('5424111122223333')).toBe('Mastercard')
    expect(detectCardBrand('378282246310005')).toBe('American Express')
    expect(detectCardBrand('6011111122223333')).toBe('Discover')
    expect(detectCardBrand('9999111122223333')).toBe('Card')
  })

  test('masks card numbers preserving last 4 digits', () => {
    expect(maskCardNumber('4532 8901 2345 7890')).toBe('•••• •••• •••• 7890')
    expect(maskCardNumber('')).toBe('•••• •••• •••• 0000')
  })

  test('hashes tokens deterministically with sha256', () => {
    expect(sha256('test')).toBe('9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')
  })

  test('simulates normal safe transaction as Pass / approved', async () => {
    const service = createPaymentSimulationService()
    const result = await service.simulatePayment({
      cardNumber: '4532 1111 2222 3333',
      amount: 12.5,
      merchantCategory: 'grocery_pos',
      merchantCountry: 'US',
      channel: 'card_present',
      entryMode: 'chip',
      hour: 10,
    })

    expect(result.success).toBe(true)
    expect(result.assessment.action).toBe('Pass')
    expect(result.assessment.status).toBe('approved')
    expect(result.assessment.probability).toBeLessThan(0.1)
    expect(result.assessment.simulatedAction).toBe('allowed')
    expect(result.card.brand).toBe('Visa')
    expect(result.card.maskedNumber).toBe('•••• •••• •••• 3333')
  })

  test('simulates high-risk midnight overseas transaction as Block / dangerous', async () => {
    const service = createPaymentSimulationService()
    const result = await service.simulatePayment({
      cardNumber: '4111 2222 3333 4444',
      amount: 4500.0,
      merchantCategory: 'crypto_exchange',
      merchantCountry: 'NG',
      channel: 'card_not_present',
      entryMode: 'manual',
      hour: 3,
    })

    expect(result.success).toBe(true)
    expect(result.assessment.action).toBe('Block')
    expect(result.assessment.status).toBe('dangerous')
    expect(result.assessment.probability).toBeGreaterThanOrEqual(0.25)
    expect(result.assessment.simulatedAction).toBe('rejected')
  })

  test('simulates suspicious transaction as Review / warning', async () => {
    const service = createPaymentSimulationService()
    const result = await service.simulatePayment({
      cardNumber: '5424 1111 2222 5555',
      amount: 400.0,
      merchantCategory: 'shopping_net',
      merchantCountry: 'US',
      channel: 'card_not_present',
      entryMode: 'ecommerce',
      hour: 19,
    })

    expect(result.success).toBe(true)
    expect(result.assessment.action).toBe('Review')
    expect(result.assessment.status).toBe('warning')
    expect(result.assessment.probability).toBeGreaterThanOrEqual(0.1)
    expect(result.assessment.probability).toBeLessThan(0.25)
    expect(result.assessment.simulatedAction).toBe('pending_review')
  })

  test('rejects unencrypted PAN injection under PCI safeguards', async () => {
    const service = createPaymentSimulationService()
    const result = await service.simulatePayment({
      cardNumber: '4000 0000 0000 0002',
      forceQuarantine: true,
    })

    expect(result.success).toBe(false)
    expect(result.pciViolation).toBe(true)
    expect(result.status).toBe('quarantined')
    expect(result.action).toBe('Reject')
  })

  test('allows resolving pending review transactions', async () => {
    const service = createPaymentSimulationService()
    const sim = await service.simulatePayment({
      cardNumber: '5424 1111 2222 5555',
      amount: 380.0,
      merchantCategory: 'shopping_net',
      channel: 'card_not_present',
      entryMode: 'ecommerce',
    })

    expect(sim.assessment.action).toBe('Review')

    const res = await service.resolveReview(sim.simulationId, 'allow', 'Customer confirmed order by phone')
    expect(res.success).toBe(true)
    expect(res.decision).toBe('allow')
    expect(res.simulatedAction).toBe('allowed')
  })
})

describe('Payment Simulation HTTP Router', () => {
  let app
  let simulationService

  beforeEach(() => {
    simulationService = createPaymentSimulationService()
    app = createApp({
      paymentSimulationService: simulationService,
      pool: { query: jest.fn().mockResolvedValue({ rows: [{ value: 1 }] }) },
    })
  })

  test('GET /api/v1/simulate/presets returns preset scenarios', async () => {
    const res = await request(app).get('/api/v1/simulate/presets')
    expect(res.status).toBe(200)
    expect(res.body.success).toBe(true)
    expect(Array.isArray(res.body.presets)).toBe(true)
    expect(res.body.presets.length).toBeGreaterThanOrEqual(4)
  })

  test('POST /api/v1/simulate/payment runs a simulation', async () => {
    const res = await request(app)
      .post('/api/v1/simulate/payment')
      .send({
        cardNumber: '4532 9999 8888 7777',
        amount: 25.0,
        merchantCategory: 'grocery_pos',
      })

    expect(res.status).toBe(200)
    expect(res.body.success).toBe(true)
    expect(res.body.assessment.action).toBe('Pass')
    expect(res.body.assessment.status).toBe('approved')
  })

  test('POST /api/v1/simulate/payment handles PCI violation with 422', async () => {
    const res = await request(app)
      .post('/api/v1/simulate/payment')
      .send({
        forceQuarantine: true,
      })

    expect(res.status).toBe(422)
    expect(res.body.success).toBe(false)
    expect(res.body.pciViolation).toBe(true)
  })

  test('POST /api/v1/simulate/reset resets memory ledger', async () => {
    const res = await request(app).post('/api/v1/simulate/reset')
    expect(res.status).toBe(200)
    expect(res.body.success).toBe(true)
  })

  test('GET /api/v1/simulate/history returns history array', async () => {
    await request(app)
      .post('/api/v1/simulate/payment')
      .send({ amount: 15.0 })

    const res = await request(app).get('/api/v1/simulate/history')
    expect(res.status).toBe(200)
    expect(res.body.success).toBe(true)
    expect(res.body.history.length).toBeGreaterThanOrEqual(1)
  })
})
