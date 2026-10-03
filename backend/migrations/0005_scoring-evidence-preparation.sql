-- Up Migration

SET LOCAL lock_timeout = '5s';

-- Preparation only: no worker or policy is activated by this migration.
CREATE TABLE scoring_jobs (
  run_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES authorization_events(event_id),
  correlation_id uuid NOT NULL,
  bundle_sha256 text NOT NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
  model_version text NOT NULL CHECK (length(model_version) BETWEEN 1 AND 128),
  policy_version text NOT NULL CHECK (length(policy_version) BETWEEN 1 AND 128),
  feature_version text NOT NULL CHECK (feature_version = 'sparkov-pit-v1'),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'scoring', 'scored', 'unavailable', 'failed')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  retryable boolean NOT NULL DEFAULT true,
  next_attempt_at timestamptz,
  deadline_at timestamptz NOT NULL,
  error_code text CHECK (error_code ~ '^[a-z][a-z0-9_]{0,63}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, event_id),
  CHECK (deadline_at >= created_at),
  CHECK (status NOT IN ('unavailable', 'failed') OR error_code IS NOT NULL),
  CHECK (status <> 'scored' OR (error_code IS NULL AND retryable = false))
);
CREATE INDEX scoring_jobs_pending_idx ON scoring_jobs (run_id, status, next_attempt_at);

CREATE TABLE scoring_feature_snapshots (
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  feature_sha256 text NOT NULL CHECK (feature_sha256 ~ '^[0-9a-f]{64}$'),
  history_sequence bigint NOT NULL CHECK (history_sequence >= 0),
  amount double precision NOT NULL CHECK (amount >= 0 AND amount < 'Infinity'::float8),
  hour integer NOT NULL CHECK (hour BETWEEN 0 AND 23),
  day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  prior_count_1h integer NOT NULL CHECK (prior_count_1h >= 0),
  prior_count_24h integer NOT NULL CHECK (prior_count_24h >= prior_count_1h),
  prior_sum_24h double precision NOT NULL CHECK (prior_sum_24h >= 0 AND prior_sum_24h < 'Infinity'::float8),
  prior_mean_24h double precision NOT NULL CHECK (prior_mean_24h >= 0 AND prior_mean_24h < 'Infinity'::float8),
  merchant_category text NOT NULL CHECK (length(merchant_category) BETWEEN 1 AND 128 AND merchant_category = btrim(merchant_category)),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_jobs (run_id, event_id)
);

CREATE TABLE scoring_results (
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  probability double precision NOT NULL CHECK (probability BETWEEN 0 AND 1),
  action text NOT NULL CHECK (action IN ('Pass', 'Review', 'Block')),
  review_threshold double precision NOT NULL CHECK (review_threshold >= 0),
  block_threshold double precision NOT NULL CHECK (block_threshold <= 1),
  reason_code text NOT NULL CHECK (reason_code IN ('below_review', 'review_region', 'block_region')),
  inference_started_at timestamptz NOT NULL,
  inference_finished_at timestamptz NOT NULL,
  inference_ms double precision NOT NULL CHECK (inference_ms >= 0 AND inference_ms < 'Infinity'::float8),
  decision_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_feature_snapshots (run_id, event_id),
  CHECK (review_threshold < block_threshold),
  CHECK (inference_started_at <= inference_finished_at AND inference_finished_at <= decision_at),
  CHECK (
    (probability < review_threshold AND action = 'Pass' AND reason_code = 'below_review') OR
    (probability >= review_threshold AND probability < block_threshold AND action = 'Review' AND reason_code = 'review_region') OR
    (probability >= block_threshold AND action = 'Block' AND reason_code = 'block_region')
  )
);

CREATE FUNCTION protect_scoring_job_identity() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Scoring job identity is immutable'; END IF;
  IF ROW(NEW.run_id, NEW.event_id, NEW.correlation_id, NEW.bundle_sha256, NEW.model_version,
         NEW.policy_version, NEW.feature_version, NEW.deadline_at, NEW.created_at)
     IS DISTINCT FROM
     ROW(OLD.run_id, OLD.event_id, OLD.correlation_id, OLD.bundle_sha256, OLD.model_version,
         OLD.policy_version, OLD.feature_version, OLD.deadline_at, OLD.created_at)
  THEN RAISE EXCEPTION 'Assigned scoring versions and identity are immutable'; END IF;
  IF OLD.status = 'scored' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'Completed scoring job is immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_jobs_identity_immutable BEFORE UPDATE OR DELETE ON scoring_jobs
FOR EACH ROW EXECUTE FUNCTION protect_scoring_job_identity();
CREATE TRIGGER scoring_feature_snapshots_immutable BEFORE UPDATE OR DELETE ON scoring_feature_snapshots
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();
CREATE TRIGGER scoring_results_immutable BEFORE UPDATE OR DELETE ON scoring_results
FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();

-- Deferred checks require result + terminal status to be committed atomically.
CREATE FUNCTION check_scoring_completion() RETURNS trigger AS $$
DECLARE job_status text; job_deadline timestamptz; result_time timestamptz;
BEGIN
  SELECT status, deadline_at INTO job_status, job_deadline FROM scoring_jobs
    WHERE run_id = NEW.run_id AND event_id = NEW.event_id;
  SELECT decision_at INTO result_time FROM scoring_results
    WHERE run_id = NEW.run_id AND event_id = NEW.event_id;
  IF (job_status = 'scored') IS DISTINCT FROM (result_time IS NOT NULL) THEN
    RAISE EXCEPTION 'Scored status and immutable result must commit atomically';
  END IF;
  IF result_time > job_deadline THEN RAISE EXCEPTION 'Expired scoring cannot execute a decision'; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER scoring_jobs_completion AFTER INSERT OR UPDATE ON scoring_jobs
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_scoring_completion();
CREATE CONSTRAINT TRIGGER scoring_results_completion AFTER INSERT ON scoring_results
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_scoring_completion();

-- Down Migration

SET LOCAL lock_timeout = '5s';
LOCK TABLE scoring_jobs, scoring_feature_snapshots, scoring_results IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM scoring_jobs) THEN RAISE EXCEPTION 'Cannot downgrade while scoring evidence exists'; END IF;
END;
$$;
DROP TABLE scoring_results;
DROP TABLE scoring_feature_snapshots;
DROP TABLE scoring_jobs;
DROP FUNCTION check_scoring_completion();
DROP FUNCTION protect_scoring_job_identity();
