-- Up Migration
SET LOCAL lock_timeout = '5s';
-- Preserve legacy fixture evidence; new connected runs use the stronger contract.
ALTER TABLE scoring_runs ADD COLUMN durability_contract text NOT NULL DEFAULT 'legacy-precommit'
  CHECK (durability_contract IN ('legacy-precommit', 'postcommit-v1'));
CREATE TABLE scoring_predictions (
  LIKE scoring_results INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
  PRIMARY KEY (run_id, event_id),
  FOREIGN KEY (run_id, event_id) REFERENCES scoring_feature_snapshots(run_id, event_id)
);
CREATE TRIGGER scoring_predictions_immutable BEFORE UPDATE OR DELETE ON scoring_predictions
  FOR EACH ROW EXECUTE FUNCTION reject_task3_mutation();
CREATE FUNCTION validate_durable_prediction() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM scoring_runs s JOIN scoring_jobs j USING(run_id)
      WHERE s.run_id=NEW.run_id AND j.event_id=NEW.event_id
        AND s.durability_contract='postcommit-v1'
        AND j.status='scoring' AND clock_timestamp()<j.deadline_at) THEN
    RAISE EXCEPTION 'Prediction requires a timely postcommit scoring run';
  END IF;
  NEW.decision_at := clock_timestamp();
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_prediction_valid BEFORE INSERT ON scoring_predictions
  FOR EACH ROW EXECUTE FUNCTION validate_durable_prediction();
CREATE FUNCTION validate_postcommit_result() RETURNS trigger AS $$
DECLARE prediction scoring_predictions%ROWTYPE; source_xid bigint; contract text;
BEGIN
  SELECT durability_contract INTO contract FROM scoring_runs WHERE run_id=NEW.run_id;
  IF contract IS DISTINCT FROM 'postcommit-v1' THEN RETURN NEW; END IF;
  SELECT p.* INTO prediction FROM scoring_predictions p
    WHERE p.run_id=NEW.run_id AND p.event_id=NEW.event_id;
  -- Same-transaction insertion cannot prove durable storage.
  SELECT xmin::text::bigint INTO source_xid FROM scoring_predictions
    WHERE run_id=NEW.run_id AND event_id=NEW.event_id;
  IF source_xid IS NULL OR source_xid = mod(txid_current(), 4294967296) THEN
    RAISE EXCEPTION 'Previously committed prediction required';
  END IF;
  IF ROW(NEW.probability,NEW.action,NEW.review_threshold,NEW.block_threshold,
         NEW.reason_code,NEW.inference_started_at,NEW.inference_finished_at,NEW.inference_ms)
     IS DISTINCT FROM
     ROW(prediction.probability,prediction.action,prediction.review_threshold,prediction.block_threshold,
         prediction.reason_code,prediction.inference_started_at,prediction.inference_finished_at,prediction.inference_ms) THEN
    RAISE EXCEPTION 'Final result differs from immutable prediction';
  END IF;
  -- Witness follows acknowledged prediction COMMIT; existing guard forbids late effects.
  NEW.decision_at := clock_timestamp();
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER scoring_result_postcommit BEFORE INSERT ON scoring_results
  FOR EACH ROW EXECUTE FUNCTION validate_postcommit_result();
-- Down Migration
SET LOCAL lock_timeout = '5s';
LOCK TABLE scoring_runs, scoring_predictions IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM scoring_predictions)
    OR EXISTS (SELECT 1 FROM scoring_runs WHERE durability_contract='postcommit-v1') THEN
    RAISE EXCEPTION 'Cannot downgrade populated postcommit evidence';
  END IF;
END $$;
DROP TRIGGER scoring_result_postcommit ON scoring_results;
DROP TABLE scoring_predictions;
DROP FUNCTION validate_postcommit_result();
DROP FUNCTION validate_durable_prediction();
ALTER TABLE scoring_runs DROP COLUMN durability_contract;
