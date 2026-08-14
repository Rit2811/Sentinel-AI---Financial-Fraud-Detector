import {
  containsProhibitedField,
  quarantineReasons,
  validateAuthorizationEvent,
} from '../src/contracts/authorizationEvent.js'
import { canonicalize, sha256 } from '../src/services/hashing.js'
import { cardNotPresent, cardPresent } from './fixtures.js'

describe('authorization event version 1 contract', () => {
  test('accepts approved card-not-present and card-present shapes', () => {
    expect(validateAuthorizationEvent(cardNotPresent())).toEqual([])
    expect(validateAuthorizationEvent(cardPresent())).toEqual([])
  })

  test.each([
    [{ amount_minor: -1 }, 'invalid_amount_minor'],
    [{ amount_minor: 12.5 }, 'invalid_amount_minor'],
    [{ currency: 'inr' }, 'invalid_currency'],
    [{ schema_version: '2.0' }, 'invalid_schema_version'],
    [{ data_origin: 'real' }, 'invalid_data_origin'],
    [{ occurred_at: '2026-08-10T12:30:00+05:30' }, 'invalid_occurred_at'],
  ])('rejects invalid scalar rule %p', (override, reason) => {
    expect(validateAuthorizationEvent(cardNotPresent(override))).toContain(
      reason,
    )
  })

  test('rejects missing, unknown and invalid conditional fields', () => {
    const missingDevice = cardNotPresent()
    delete missingDevice.device_token
    expect(validateAuthorizationEvent(missingDevice)).toContain(
      'device_token_required',
    )
    expect(
      validateAuthorizationEvent(cardNotPresent({ unexpected: true })),
    ).toContain('unknown_field')
    expect(
      validateAuthorizationEvent(
        cardNotPresent({ terminal_token: 'terminal_demo_001' }),
      ),
    ).toContain('terminal_token_not_allowed')
    expect(
      validateAuthorizationEvent(cardPresent({ entry_mode: 'ecommerce' })),
    ).toContain('ecommerce_requires_card_not_present')
  })

  test('detects prohibited keys recursively without inspecting values', () => {
    expect(
      containsProhibitedField({ nested: { card_number: 'never-echo-this' } }),
    ).toBe(true)
    expect(containsProhibitedField(cardNotPresent())).toBe(false)
  })

  test('quarantines timestamps more than five minutes in the future', () => {
    const now = new Date('2026-08-10T12:30:00.000Z')
    expect(
      quarantineReasons(
        cardNotPresent({ occurred_at: '2026-08-10T12:36:00.000Z' }),
        now,
      ),
    ).toEqual(['occurred_at_too_far_in_future'])
  })

  test('canonicalization and hashes are deterministic across key order', () => {
    const first = { b: 2, a: { d: 4, c: 3 } }
    const second = { a: { c: 3, d: 4 }, b: 2 }
    expect(canonicalize(first)).toBe(canonicalize(second))
    expect(sha256(canonicalize(first))).toBe(sha256(canonicalize(second)))
  })
})
