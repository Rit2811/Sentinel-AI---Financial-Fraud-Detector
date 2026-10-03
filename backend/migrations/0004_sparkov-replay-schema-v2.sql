-- Up Migration

SET LOCAL lock_timeout = '5s';

ALTER TABLE authorization_events
  ADD COLUMN merchant_category text,
  ADD COLUMN time_basis text,
  ADD COLUMN currency_basis text,
  ALTER COLUMN channel DROP NOT NULL,
  ALTER COLUMN account_token DROP NOT NULL,
  ALTER COLUMN merchant_country DROP NOT NULL,
  ALTER COLUMN entry_mode DROP NOT NULL,
  DROP CONSTRAINT authorization_events_schema_version_check,
  DROP CONSTRAINT authorization_events_data_origin_check,
  DROP CONSTRAINT authorization_events_check;

-- IS TRUE prevents SQL NULL from bypassing version-specific requirements.
ALTER TABLE authorization_events ADD CONSTRAINT authorization_events_version_shape_check
CHECK ((
  (
    schema_version = '1.0' AND data_origin = 'synthetic_enriched'
    AND channel IS NOT NULL AND account_token IS NOT NULL
    AND merchant_country IS NOT NULL AND entry_mode IS NOT NULL
    AND merchant_category IS NULL AND time_basis IS NULL AND currency_basis IS NULL
    AND (
      (channel = 'card_present' AND terminal_token IS NOT NULL AND device_token IS NULL)
      OR (channel = 'card_not_present' AND device_token IS NOT NULL AND terminal_token IS NULL)
    )
  ) OR (
    schema_version = '2.0' AND data_origin = 'sparkov_replay'
    AND channel IS NULL AND account_token IS NULL AND merchant_country IS NULL
    AND entry_mode IS NULL AND terminal_token IS NULL AND device_token IS NULL
    AND currency = 'USD' AND amount_minor <= 9007199254740991
    AND card_token ~ '^card_[0-9a-f]{64}$'
    AND merchant_id ~ '^merchant_[0-9a-f]{64}$'
    AND length(merchant_category) BETWEEN 1 AND 128
    AND merchant_category !~ '^[[:space:]]|[[:space:]]$'
    AND time_basis = 'source_wall_clock_as_utc'
    AND currency_basis = 'simulation_assumption'
  )
) IS TRUE);

-- The API supplies the original JSON. Keep v1 payloads untouched and reject
-- extra v2 keys or nested values even when an insert bypasses HTTP validation.
ALTER TABLE authorization_events ADD CONSTRAINT authorization_events_v2_payload_check
CHECK (schema_version <> '2.0' OR (
  jsonb_typeof(sanitized_payload) = 'object'
  AND sanitized_payload - ARRAY['event_id', 'authorization_id', 'occurred_at'] =
    jsonb_build_object(
      'schema_version', schema_version, 'data_origin', data_origin,
      'amount_minor', amount_minor, 'currency', currency,
      'card_token', card_token, 'merchant_id', merchant_id,
      'merchant_category', merchant_category,
      'time_basis', time_basis, 'currency_basis', currency_basis
    )
  AND jsonb_typeof(sanitized_payload->'event_id') = 'string'
  AND lower(sanitized_payload->>'event_id') = event_id::text
  AND jsonb_typeof(sanitized_payload->'authorization_id') = 'string'
  AND lower(sanitized_payload->>'authorization_id') = authorization_id::text
  AND jsonb_typeof(sanitized_payload->'occurred_at') = 'string'
  AND sanitized_payload->>'occurred_at' ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'
  AND (sanitized_payload->>'occurred_at')::timestamptz = occurred_at
) IS TRUE);

-- Down Migration

SET LOCAL lock_timeout = '5s';

-- Prevent concurrent v2 writes between the downgrade guard and schema change.
LOCK TABLE authorization_events, quarantined_events, idempotency_records IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM authorization_events WHERE schema_version = '2.0')
    OR EXISTS (SELECT 1 FROM quarantined_events WHERE sanitized_payload->>'schema_version' = '2.0')
    OR EXISTS (SELECT 1 FROM idempotency_records WHERE response_body->>'schema_version' = '2.0')
  THEN
    RAISE EXCEPTION 'Cannot downgrade while schema 2.0 audit records exist';
  END IF;
END;
$$;

ALTER TABLE authorization_events
  DROP CONSTRAINT authorization_events_v2_payload_check,
  DROP CONSTRAINT authorization_events_version_shape_check,
  DROP COLUMN merchant_category,
  DROP COLUMN time_basis,
  DROP COLUMN currency_basis,
  ALTER COLUMN channel SET NOT NULL,
  ALTER COLUMN account_token SET NOT NULL,
  ALTER COLUMN merchant_country SET NOT NULL,
  ALTER COLUMN entry_mode SET NOT NULL,
  ADD CONSTRAINT authorization_events_schema_version_check CHECK (schema_version = '1.0'),
  ADD CONSTRAINT authorization_events_data_origin_check CHECK (data_origin = 'synthetic_enriched'),
  ADD CONSTRAINT authorization_events_check CHECK (
    (channel = 'card_present' AND terminal_token IS NOT NULL AND device_token IS NULL)
    OR (channel = 'card_not_present' AND device_token IS NOT NULL AND terminal_token IS NULL)
  );
