-- Up Migration

CREATE INDEX authorization_events_created_at_idx
ON authorization_events (created_at);

CREATE INDEX stream_processing_receipts_processed_at_idx
ON stream_processing_receipts (processed_at, event_id);

CREATE INDEX ingestion_attempts_rejected_time_idx
ON ingestion_attempts (created_at)
WHERE outcome <> 'accepted';

-- Down Migration

DROP INDEX IF EXISTS ingestion_attempts_rejected_time_idx;
DROP INDEX IF EXISTS stream_processing_receipts_processed_at_idx;
DROP INDEX IF EXISTS authorization_events_created_at_idx;
