const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{8,128}$/
const IDENTIFIER_PATTERN = /^[A-Za-z0-9_-]{3,128}$/
const UTC_TIMESTAMP_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/

export const AUTHORIZATION_EVENT_FIELDS = new Set([
  'schema_version',
  'event_id',
  'authorization_id',
  'occurred_at',
  'data_origin',
  'channel',
  'amount_minor',
  'currency',
  'card_token',
  'account_token',
  'merchant_id',
  'merchant_country',
  'entry_mode',
  'terminal_token',
  'device_token',
])

export const PROHIBITED_FIELDS = new Set([
  'pan',
  'card_number',
  'cardnumber',
  'cvv',
  'cvc',
  'pin',
  'track_data',
  'track1',
  'track2',
  'magnetic_stripe',
])

const REQUIRED_FIELDS = [
  'schema_version',
  'event_id',
  'authorization_id',
  'occurred_at',
  'data_origin',
  'channel',
  'amount_minor',
  'currency',
  'card_token',
  'account_token',
  'merchant_id',
  'merchant_country',
  'entry_mode',
]

function normalizedKey(key) {
  return key.toLowerCase().replaceAll('-', '_')
}

export function containsProhibitedField(value) {
  if (!value || typeof value !== 'object') return false
  if (Array.isArray(value)) return value.some(containsProhibitedField)
  return Object.entries(value).some(
    ([key, child]) =>
      PROHIBITED_FIELDS.has(normalizedKey(key)) ||
      containsProhibitedField(child),
  )
}

export function validateAuthorizationEvent(body) {
  const reasons = []
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return ['body_must_be_object']
  }

  for (const field of REQUIRED_FIELDS) {
    if (!(field in body)) reasons.push(`missing_${field}`)
  }
  if (
    Object.keys(body).some((field) => !AUTHORIZATION_EVENT_FIELDS.has(field))
  ) {
    reasons.push('unknown_field')
  }
  if (body.schema_version !== '1.0') reasons.push('invalid_schema_version')
  if (!UUID_PATTERN.test(body.event_id ?? '')) reasons.push('invalid_event_id')
  if (!UUID_PATTERN.test(body.authorization_id ?? ''))
    reasons.push('invalid_authorization_id')

  const occurredAt = new Date(body.occurred_at)
  if (
    typeof body.occurred_at !== 'string' ||
    !UTC_TIMESTAMP_PATTERN.test(body.occurred_at) ||
    Number.isNaN(occurredAt.valueOf())
  ) {
    reasons.push('invalid_occurred_at')
  }
  if (body.data_origin !== 'synthetic_enriched')
    reasons.push('invalid_data_origin')
  if (!['card_present', 'card_not_present'].includes(body.channel)) {
    reasons.push('invalid_channel')
  }
  if (!Number.isSafeInteger(body.amount_minor) || body.amount_minor < 0) {
    reasons.push('invalid_amount_minor')
  }
  if (!/^[A-Z]{3}$/.test(body.currency ?? '')) reasons.push('invalid_currency')
  if (!TOKEN_PATTERN.test(body.card_token ?? ''))
    reasons.push('invalid_card_token')
  if (!TOKEN_PATTERN.test(body.account_token ?? ''))
    reasons.push('invalid_account_token')
  if (!IDENTIFIER_PATTERN.test(body.merchant_id ?? ''))
    reasons.push('invalid_merchant_id')
  if (!/^[A-Z]{2}$/.test(body.merchant_country ?? '')) {
    reasons.push('invalid_merchant_country')
  }
  if (
    !['chip', 'contactless', 'magstripe', 'manual', 'ecommerce'].includes(
      body.entry_mode,
    )
  ) {
    reasons.push('invalid_entry_mode')
  }

  if (body.channel === 'card_present') {
    if (!TOKEN_PATTERN.test(body.terminal_token ?? ''))
      reasons.push('terminal_token_required')
    if ('device_token' in body) reasons.push('device_token_not_allowed')
  }
  if (body.channel === 'card_not_present') {
    if (!TOKEN_PATTERN.test(body.device_token ?? ''))
      reasons.push('device_token_required')
    if ('terminal_token' in body) reasons.push('terminal_token_not_allowed')
  }
  if (
    ['chip', 'contactless', 'magstripe'].includes(body.entry_mode) &&
    body.channel !== 'card_present'
  ) {
    reasons.push('physical_entry_requires_card_present')
  }
  if (body.entry_mode === 'ecommerce' && body.channel !== 'card_not_present') {
    reasons.push('ecommerce_requires_card_not_present')
  }

  return [...new Set(reasons)].sort()
}

export function quarantineReasons(body, now = new Date()) {
  const occurredAt = new Date(body.occurred_at)
  return occurredAt.valueOf() > now.valueOf() + 5 * 60 * 1000
    ? ['occurred_at_too_far_in_future']
    : []
}
