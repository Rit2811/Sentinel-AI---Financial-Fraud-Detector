-- Up Migration
SET LOCAL lock_timeout = '5s';
ALTER TABLE scoring_jobs DROP CONSTRAINT scoring_jobs_status_check;
ALTER TABLE scoring_jobs ADD CONSTRAINT scoring_jobs_status_check
  CHECK (status IN ('pending', 'scoring', 'scored', 'unavailable', 'failed', 'expired'));
ALTER TABLE scoring_jobs ADD CONSTRAINT scoring_jobs_expired_check
  CHECK (status <> 'expired' OR (error_code IS NOT NULL AND retryable = false));

-- An immutable row is the local simulated effect, never a bank operation.
CREATE TABLE simulated_executions (
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  state text NOT NULL CHECK (state IN ('allowed', 'pending_review', 'rejected')),
  executed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_results (run_id, event_id)
);
CREATE TABLE review_resolutions (
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  resolution_id uuid NOT NULL UNIQUE,
  reviewer_id text NOT NULL CHECK (reviewer_id ~ '^[A-Za-z0-9_-]{1,128}$'),
  resolution text NOT NULL CHECK (resolution IN ('allow', 'reject')),
  notes text NOT NULL CHECK (length(notes) BETWEEN 1 AND 2000),
  resolved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES simulated_executions (run_id, event_id)
);
CREATE TRIGGER simulated_executions_immutable BEFORE UPDATE OR DELETE ON simulated_executions
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();
CREATE TRIGGER review_resolutions_immutable BEFORE UPDATE OR DELETE ON review_resolutions
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

CREATE FUNCTION validate_simulated_execution() RETURNS trigger AS $$
DECLARE chosen text; deadline timestamptz; expected text;
BEGIN
  SELECT r.action, j.deadline_at INTO chosen, deadline FROM scoring_results r
    JOIN scoring_jobs j USING (run_id, event_id)
    WHERE r.run_id = NEW.run_id AND r.event_id = NEW.event_id;
  NEW.executed_at := clock_timestamp();
  expected := CASE WHEN chosen = 'Pass' THEN 'allowed' WHEN chosen = 'Block' THEN 'rejected'
    WHEN chosen = 'Review' THEN 'pending_review' END;
  IF expected IS NULL OR NEW.state <> expected OR NEW.executed_at > deadline THEN
    RAISE EXCEPTION 'Invalid or expired simulated execution';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER simulated_execution_valid BEFORE INSERT ON simulated_executions
FOR EACH ROW EXECUTE FUNCTION validate_simulated_execution();

CREATE FUNCTION execute_simulated_decision() RETURNS trigger AS $$
BEGIN
  INSERT INTO simulated_executions (run_id, event_id, state) VALUES
    (NEW.run_id, NEW.event_id, CASE WHEN NEW.action = 'Pass' THEN 'allowed'
      WHEN NEW.action = 'Block' THEN 'rejected' ELSE 'pending_review' END);
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
-- Defer effect creation until commit checks; deadline failure rolls back the result.
CREATE CONSTRAINT TRIGGER scoring_results_execute AFTER INSERT ON scoring_results
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION execute_simulated_decision();

CREATE FUNCTION validate_review_resolution() RETURNS trigger AS $$
DECLARE execution_state text;
BEGIN
  SELECT state INTO execution_state FROM simulated_executions
    WHERE run_id = NEW.run_id AND event_id = NEW.event_id FOR UPDATE;
  IF execution_state IS DISTINCT FROM 'pending_review' THEN
    RAISE EXCEPTION 'Only pending reviews can be resolved';
  END IF;
  NEW.resolved_at := clock_timestamp();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER review_resolution_valid BEFORE INSERT ON review_resolutions
FOR EACH ROW EXECUTE FUNCTION validate_review_resolution();

CREATE FUNCTION protect_expired_scoring_job() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'expired' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'Expired scoring job is immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_jobs_expired_immutable BEFORE UPDATE ON scoring_jobs
FOR EACH ROW EXECUTE FUNCTION protect_expired_scoring_job();

-- Down Migration
SET LOCAL lock_timeout = '5s';
LOCK TABLE scoring_jobs, simulated_executions, review_resolutions IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM simulated_executions) OR EXISTS (SELECT 1 FROM scoring_jobs WHERE status = 'expired') THEN
    RAISE EXCEPTION 'Cannot downgrade populated execution evidence';
  END IF;
END $$;
DROP TRIGGER scoring_results_execute ON scoring_results;
DROP TRIGGER scoring_jobs_expired_immutable ON scoring_jobs;
DROP TABLE review_resolutions;
DROP TABLE simulated_executions;
DROP FUNCTION protect_expired_scoring_job();
DROP FUNCTION validate_review_resolution();
DROP FUNCTION execute_simulated_decision();
DROP FUNCTION validate_simulated_execution();
ALTER TABLE scoring_jobs DROP CONSTRAINT scoring_jobs_expired_check;
ALTER TABLE scoring_jobs DROP CONSTRAINT scoring_jobs_status_check;
ALTER TABLE scoring_jobs ADD CONSTRAINT scoring_jobs_status_check
  CHECK (status IN ('pending', 'scoring', 'scored', 'unavailable', 'failed'));
