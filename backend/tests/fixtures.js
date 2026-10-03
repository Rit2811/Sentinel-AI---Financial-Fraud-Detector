export const correlationId = '985d24e4-42be-4e3b-bb9a-ad43664ca053'
export const idempotencyKey = '4f93f5fb-44f8-4d0a-9f69-c72466ad6402'

export function sparkovReplay(overrides = {}) {
  return {
    schema_version: '2.0',
    event_id: 'd6a69ef3-8b61-5f3c-b87d-ce5e0db51299',
    authorization_id: 'afd883d1-8f43-5dfb-b944-3a77b10349e5',
    occurred_at: '2019-01-01T00:00:00Z',
    data_origin: 'sparkov_replay',
    amount_minor: 1234,
    currency: 'USD',
    card_token: `card_${'a'.repeat(64)}`,
    merchant_id: `merchant_${'b'.repeat(64)}`,
    merchant_category: 'grocery_pos',
    time_basis: 'source_wall_clock_as_utc',
    currency_basis: 'simulation_assumption',
    ...overrides,
  }
}

export function cardNotPresent(overrides = {}) {
  return {
    schema_version: '1.0',
    event_id: 'e82d7cc1-0d61-4f57-a6db-0e50d3708410',
    authorization_id: '1b1e8879-4ec8-47d4-b447-24c7dc17c2a7',
    occurred_at: '2026-08-10T12:30:00.000Z',
    data_origin: 'synthetic_enriched',
    channel: 'card_not_present',
    amount_minor: 129900,
    currency: 'INR',
    card_token: 'card_tok_demo_001',
    account_token: 'acct_tok_demo_001',
    merchant_id: 'merchant_demo_001',
    merchant_country: 'IN',
    entry_mode: 'ecommerce',
    device_token: 'device_tok_demo_001',
    ...overrides,
  }
}

export function cardPresent(overrides = {}) {
  return {
    schema_version: '1.0',
    event_id: '1414dca2-9d7d-47aa-8ab4-96086142ab95',
    authorization_id: 'd85964a0-f5a1-48c9-b1af-216cbb228d63',
    occurred_at: '2026-08-10T12:31:00.000Z',
    data_origin: 'synthetic_enriched',
    channel: 'card_present',
    amount_minor: 250000,
    currency: 'INR',
    card_token: 'card_tok_demo_002',
    account_token: 'acct_tok_demo_002',
    merchant_id: 'merchant_demo_002',
    merchant_country: 'IN',
    entry_mode: 'chip',
    terminal_token: 'terminal_demo_001',
    ...overrides,
  }
}
