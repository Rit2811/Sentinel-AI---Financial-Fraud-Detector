-- Up Migration
SET LOCAL lock_timeout = '5s';
CREATE INDEX ingestion_attempts_accepted_event_idx ON ingestion_attempts(event_id,received_at)
WHERE outcome='accepted';
CREATE INDEX scoring_jobs_work_order_idx ON scoring_jobs(run_id,created_at,event_id)
WHERE status NOT IN ('scored','expired','failed');

-- Down Migration
DROP INDEX scoring_jobs_work_order_idx;
DROP INDEX ingestion_attempts_accepted_event_idx;
