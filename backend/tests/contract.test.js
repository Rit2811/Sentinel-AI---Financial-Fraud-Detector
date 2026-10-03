import {
  containsProhibitedField,
  quarantineReasons,
  validateAuthorizationEvent,
  SPARKOV_EVENT_FIELDS,
} from '../src/contracts/authorizationEvent.js'
import { canonicalize, sha256 } from '../src/services/hashing.js'
import { cardNotPresent, cardPresent, sparkovReplay } from './fixtures.js'

describe('authorization event version 1 contract', () => {
  test('accepts approved card-not-present and card-present shapes', () => {
    expect(validateAuthorizationEvent(cardNotPresent())).toEqual([])
    expect(validateAuthorizationEvent(cardPresent())).toEqual([])
  })

  test.each([
    [{ amount_minor: -1 }, 'invalid_amount_minor'],
    [{ amount_minor: 12.5 }, 'invalid_amount_minor'],
    [{ currency: 'inr' }, 'invalid_currency'],
    [{ schema_version: '3.0' }, 'invalid_schema_version'],
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

describe('Sparkov version 2 contract', () => {
  test('accepts exactly the source-derived shape and explicit assumptions', () => {
    expect(validateAuthorizationEvent(sparkovReplay())).toEqual([])
    expect(Object.keys(sparkovReplay()).sort()).toEqual(
      [...SPARKOV_EVENT_FIELDS].sort(),
    )
    expect(
      validateAuthorizationEvent(sparkovReplay({ amount_minor: 0 })),
    ).toEqual([])
  })

  test.each([...SPARKOV_EVENT_FIELDS])('requires %s', (field) => {
    const event = sparkovReplay()
    delete event[field]
    expect(validateAuthorizationEvent(event)).toContain(`missing_${field}`)
  })

  test.each([
    'channel',
    'account_token',
    'entry_mode',
    'device_token',
    'terminal_token',
    'merchant_country',
    'country',
    'balance',
    'unexpected',
  ])('rejects even a null unsupported field: %s', (field) => {
    expect(
      validateAuthorizationEvent(sparkovReplay({ [field]: null })),
    ).toContain('unknown_field')
  })

  test.each([
    ['data_origin', 'synthetic_enriched'],
    ['currency', 'INR'],
    ['currency_basis', 'observed'],
    ['time_basis', 'unix_time'],
    ['amount_minor', -1],
    ['amount_minor', 1.5],
    ['amount_minor', Number.MAX_SAFE_INTEGER + 1],
    ['amount_minor', '100'],
    ['card_token', 'card_not_a_hash'],
    ['card_token', [`card_${'a'.repeat(64)}`]],
    ['merchant_id', 'raw_merchant'],
    ['merchant_category', ''],
    ['merchant_category', ' groceries '],
    ['merchant_category', 'x'.repeat(129)],
    ['merchant_category', {}],
    ['event_id', []],
    ['authorization_id', null],
    ['occurred_at', '2019-02-30T00:00:00Z'],
    ['occurred_at', '2019-01-01T00:00:00+00:00'],
    ['occurred_at', '2019-01-01T00:00:00.000Z'],
  ])('rejects invalid %s', (field, value) => {
    expect(
      validateAuthorizationEvent(sparkovReplay({ [field]: value })),
    ).toContain(`invalid_${field}`)
  })

  test.each([
    'cc_num',
    'is_fraud',
    'first',
    'last',
    'street',
    'trans_num',
    'unix_time',
  ])('detects nested prohibited source field %s in arrays', (field) => {
    expect(containsProhibitedField({ nested: [{ [field]: 'private' }] })).toBe(
      true,
    )
  })

  test('rejects v2 origin on v1 and preserves future quarantine', () => {
    expect(
      validateAuthorizationEvent(
        cardNotPresent({ data_origin: 'sparkov_replay' }),
      ),
    ).toContain('invalid_data_origin')
    expect(
      quarantineReasons(sparkovReplay({ occurred_at: '2099-01-01T00:00:00Z' })),
    ).toEqual(['occurred_at_too_far_in_future'])
  })
})
