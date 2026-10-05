-- Up Migration
SET LOCAL lock_timeout = '5s';
CREATE INDEX authorization_events_scoring_order_idx
ON authorization_events(created_at,event_id) WHERE schema_version='2.0';

-- Down Migration
DROP INDEX authorization_events_scoring_order_idx;
