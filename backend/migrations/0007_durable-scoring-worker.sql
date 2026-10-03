-- Up Migration
SET LOCAL lock_timeout = '5s';
CREATE TABLE scoring_runs (
  run_id uuid PRIMARY KEY,
  mode text NOT NULL CHECK (mode IN ('application', 'fixture')),
  bundle_sha256 text NOT NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
  policy_version text NOT NULL,
  feature_version text NOT NULL CHECK (feature_version = 'sparkov-pit-v1'),
  gate_report_sha256 text CHECK (gate_report_sha256 ~ '^[0-9a-f]{64}$'),
  deadline_ms integer NOT NULL CHECK (deadline_ms = 1000),
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (mode <> 'application' OR gate_report_sha256 IS NOT NULL)
);
CREATE TRIGGER scoring_runs_immutable BEFORE UPDATE OR DELETE ON scoring_runs
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

CREATE TABLE scoring_history (
  run_id uuid NOT NULL REFERENCES scoring_runs(run_id),
  event_id uuid NOT NULL,
  card_token text NOT NULL CHECK (card_token ~ '^card_[0-9a-f]{64}$'),
  occurred_at timestamptz NOT NULL,
  amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_jobs(run_id, event_id)
);
CREATE INDEX scoring_history_window_idx ON scoring_history(run_id, card_token, occurred_at);
CREATE TRIGGER scoring_history_immutable BEFORE UPDATE OR DELETE ON scoring_history
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

CREATE TABLE scoring_worker_health (
  run_id uuid PRIMARY KEY REFERENCES scoring_runs(run_id),
  ready boolean NOT NULL DEFAULT false,
  blocked boolean NOT NULL DEFAULT false,
  heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  error_code text CHECK (error_code ~ '^[a-z][a-z0-9_]{0,63}$')
);
CREATE TABLE scoring_delivery_failures (
  run_id uuid NOT NULL REFERENCES scoring_runs(run_id),
  stream_name text NOT NULL,
  message_id text NOT NULL,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  error_code text NOT NULL CHECK (error_code ~ '^[a-z][a-z0-9_]{0,63}$'),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, stream_name, message_id)
);
CREATE TRIGGER scoring_delivery_failures_immutable BEFORE UPDATE OR DELETE ON scoring_delivery_failures
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

CREATE TABLE scoring_attempt_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  status text NOT NULL,
  attempts integer NOT NULL,
  error_code text,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_jobs(run_id, event_id)
);
CREATE TRIGGER scoring_attempt_audit_immutable BEFORE UPDATE OR DELETE ON scoring_attempt_audit
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();
CREATE FUNCTION audit_scoring_attempt() RETURNS trigger AS $$ BEGIN
  INSERT INTO scoring_attempt_audit (run_id,event_id,status,attempts,error_code)
    VALUES (NEW.run_id,NEW.event_id,NEW.status,NEW.attempts,NEW.error_code);
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_jobs_audit AFTER INSERT OR UPDATE ON scoring_jobs
FOR EACH ROW EXECUTE FUNCTION audit_scoring_attempt();
CREATE FUNCTION protect_failed_scoring_job() RETURNS trigger AS $$ BEGIN
  IF OLD.status = 'failed' AND NOT OLD.retryable AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'Terminal failed scoring job is immutable';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_jobs_failed_immutable BEFORE UPDATE ON scoring_jobs
FOR EACH ROW EXECUTE FUNCTION protect_failed_scoring_job();

-- Down Migration
SET LOCAL lock_timeout = '5s';
LOCK TABLE scoring_runs, scoring_history, scoring_attempt_audit, scoring_delivery_failures IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM scoring_runs) OR EXISTS(SELECT 1 FROM scoring_attempt_audit) THEN
    RAISE EXCEPTION 'Cannot downgrade populated worker evidence';
  END IF;
END $$;
DROP TRIGGER scoring_jobs_failed_immutable ON scoring_jobs;
DROP TRIGGER scoring_jobs_audit ON scoring_jobs;
DROP FUNCTION protect_failed_scoring_job();
DROP FUNCTION audit_scoring_attempt();
DROP TABLE scoring_attempt_audit;
DROP TABLE scoring_delivery_failures;
DROP TABLE scoring_worker_health;
DROP TABLE scoring_history;
DROP TABLE scoring_runs;
