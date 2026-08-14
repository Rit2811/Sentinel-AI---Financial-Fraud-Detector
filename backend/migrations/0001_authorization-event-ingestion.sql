-- Up Migration

CREATE TABLE authorization_events (
  event_id uuid PRIMARY KEY,
  authorization_id uuid NOT NULL UNIQUE,
  occurred_at timestamptz NOT NULL,
  schema_version text NOT NULL CHECK (schema_version = '1.0'),
  data_origin text NOT NULL CHECK (data_origin = 'synthetic_enriched'),
  channel text NOT NULL CHECK (channel IN ('card_present', 'card_not_present')),
  amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  card_token text NOT NULL,
  account_token text NOT NULL,
  merchant_id text NOT NULL,
  merchant_country char(2) NOT NULL CHECK (merchant_country ~ '^[A-Z]{2}$'),
  entry_mode text NOT NULL,
  terminal_token text,
  device_token text,
  sanitized_payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (
    (channel = 'card_present' AND terminal_token IS NOT NULL AND device_token IS NULL)
    OR
    (channel = 'card_not_present' AND device_token IS NOT NULL AND terminal_token IS NULL)
  )
);

CREATE TABLE idempotency_records (
  key_hash char(64) PRIMARY KEY,
  payload_hash char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('processing', 'completed')),
  response_status integer,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz,
  CHECK (
    (status = 'processing' AND response_status IS NULL AND response_body IS NULL)
    OR
    (status = 'completed' AND response_status IS NOT NULL AND response_body IS NOT NULL)
  )
);

CREATE TABLE ingestion_attempts (
  ingestion_id uuid PRIMARY KEY,
  event_id uuid,
  correlation_id uuid NOT NULL,
  key_hash char(64),
  payload_hash char(64),
  outcome text NOT NULL CHECK (
    outcome IN (
      'accepted', 'quarantined', 'idempotency_conflict', 'event_identity_conflict',
      'malformed_json', 'unsupported_media_type', 'payload_too_large',
      'validation_failed', 'prohibited_field'
    )
  ),
  reason_codes text[] NOT NULL DEFAULT '{}',
  received_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ingestion_attempts_correlation_idx ON ingestion_attempts (correlation_id);
CREATE INDEX ingestion_attempts_outcome_time_idx ON ingestion_attempts (outcome, created_at DESC);

CREATE TABLE quarantined_events (
  quarantine_id uuid PRIMARY KEY,
  event_id uuid NOT NULL UNIQUE,
  sanitized_payload jsonb NOT NULL,
  reason_codes text[] NOT NULL,
  status text NOT NULL DEFAULT 'held' CHECK (status = 'held'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION reject_task3_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Task 3 event records are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER authorization_events_immutable
BEFORE UPDATE OR DELETE ON authorization_events
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

CREATE TRIGGER quarantined_events_immutable
BEFORE UPDATE OR DELETE ON quarantined_events
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

-- Down Migration

DROP TRIGGER IF EXISTS quarantined_events_immutable ON quarantined_events;
DROP TRIGGER IF EXISTS authorization_events_immutable ON authorization_events;
DROP FUNCTION IF EXISTS reject_task3_mutation();
DROP TABLE IF EXISTS quarantined_events;
DROP TABLE IF EXISTS ingestion_attempts;
DROP TABLE IF EXISTS idempotency_records;
DROP TABLE IF EXISTS authorization_events;
