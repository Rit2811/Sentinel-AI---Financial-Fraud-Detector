-- Up Migration
SET LOCAL lock_timeout = '5s';
-- A separate immutable run may exercise the owner-authorized deadline trial.
-- Existing runs/jobs retain their identities and original one-second deadline.
ALTER TABLE scoring_runs ADD COLUMN diagnostic_only boolean NOT NULL DEFAULT false;
ALTER TABLE scoring_runs DROP CONSTRAINT scoring_runs_deadline_ms_check;
ALTER TABLE scoring_runs ADD CONSTRAINT scoring_runs_deadline_ms_check
  CHECK ((NOT diagnostic_only AND deadline_ms=1000) OR (diagnostic_only AND deadline_ms=2000));
CREATE FUNCTION validate_diagnostic_job_deadline() RETURNS trigger AS $$
DECLARE configured scoring_runs%ROWTYPE;
BEGIN
  SELECT * INTO configured FROM scoring_runs WHERE run_id=NEW.run_id;
  IF configured.diagnostic_only AND
    NEW.deadline_at IS DISTINCT FROM NEW.created_at + configured.deadline_ms * interval '1 millisecond' THEN
    RAISE EXCEPTION 'Diagnostic deadline must match immutable run';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_jobs_diagnostic_deadline BEFORE INSERT ON scoring_jobs
FOR EACH ROW EXECUTE FUNCTION validate_diagnostic_job_deadline();
-- Down Migration
SET LOCAL lock_timeout = '5s';
LOCK TABLE scoring_runs IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM scoring_runs WHERE diagnostic_only) THEN
    RAISE EXCEPTION 'Cannot downgrade recorded diagnostic runs';
  END IF;
END $$;
DROP TRIGGER scoring_jobs_diagnostic_deadline ON scoring_jobs;
DROP FUNCTION validate_diagnostic_job_deadline();
ALTER TABLE scoring_runs DROP CONSTRAINT scoring_runs_deadline_ms_check;
ALTER TABLE scoring_runs ADD CONSTRAINT scoring_runs_deadline_ms_check CHECK (deadline_ms=1000);
ALTER TABLE scoring_runs DROP COLUMN diagnostic_only;
