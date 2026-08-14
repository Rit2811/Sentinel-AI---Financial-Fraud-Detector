-- Up Migration

CREATE TABLE authorization_event_outbox (
  outbox_id uuid PRIMARY KEY,
  event_id uuid NOT NULL UNIQUE REFERENCES authorization_events(event_id),
  envelope jsonb NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'publishing', 'published', 'dead_letter')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  claimed_at timestamptz,
  claimed_by text,
  published_at timestamptz,
  stream_message_id text,
  last_error_code text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (jsonb_typeof(envelope) = 'object')
);

CREATE INDEX authorization_event_outbox_publish_idx
ON authorization_event_outbox (status, available_at, created_at);

CREATE TABLE stream_processing_receipts (
  consumer_purpose text NOT NULL,
  event_id uuid NOT NULL REFERENCES authorization_events(event_id),
  stream_message_id text NOT NULL,
  envelope_hash char(64) NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (consumer_purpose, event_id)
);

-- Down Migration

DROP TABLE IF EXISTS stream_processing_receipts;
DROP TABLE IF EXISTS authorization_event_outbox;
