-- Up Migration
SET LOCAL lock_timeout = '5s';

CREATE FUNCTION prepare_scoring_checkpoints(
    p_run uuid,p_bundle text,p_policy text,p_feature text,p_deadline integer,p_rows jsonb
) RETURNS SETOF scoring_jobs LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE i record; job public.scoring_jobs; configured public.scoring_runs;
BEGIN
  SELECT * INTO configured FROM public.scoring_runs WHERE run_id=p_run;
  IF NOT FOUND OR ROW(configured.bundle_sha256,configured.policy_version,configured.feature_version,configured.deadline_ms)
    IS DISTINCT FROM ROW(p_bundle,p_policy,p_feature,p_deadline) THEN
    RAISE EXCEPTION 'Checkpoint parameters do not match immutable run';
  END IF;
  IF p_rows IS NULL OR jsonb_typeof(p_rows)<>'array' OR jsonb_array_length(p_rows) NOT BETWEEN 1 AND 4 THEN
    RAISE EXCEPTION 'Checkpoint batch must contain one to four rows';
  END IF;
  FOR i IN SELECT * FROM jsonb_to_recordset(p_rows) AS x(
    event_id uuid,correlation_id uuid,accepted_at timestamptz,occurred_at timestamptz,
    card_token text,amount_minor bigint,publication_status text,out_of_order boolean,
    feature_sha256 text,history_sequence bigint,amount double precision,hour integer,
    day_of_week integer,prior_count_1h integer,prior_count_24h integer,
    prior_sum_24h double precision,prior_mean_24h double precision,merchant_category text
  ) LOOP
    INSERT INTO public.scoring_jobs(run_id,event_id,correlation_id,bundle_sha256,
      model_version,policy_version,feature_version,created_at,deadline_at)
    VALUES(p_run,i.event_id,i.correlation_id,p_bundle,'random_forest.sigmoid',p_policy,p_feature,
      i.accepted_at,i.accepted_at+p_deadline*interval '1 millisecond')
    ON CONFLICT DO NOTHING RETURNING * INTO job;
    IF NOT FOUND THEN CONTINUE; END IF;
    IF i.feature_sha256 IS NOT NULL THEN
      INSERT INTO public.scoring_feature_snapshots(run_id,event_id,feature_sha256,
        history_sequence,amount,hour,day_of_week,prior_count_1h,prior_count_24h,
        prior_sum_24h,prior_mean_24h,merchant_category)
      VALUES(p_run,i.event_id,i.feature_sha256,i.history_sequence,i.amount,i.hour,i.day_of_week,
        i.prior_count_1h,i.prior_count_24h,i.prior_sum_24h,i.prior_mean_24h,i.merchant_category);
      INSERT INTO public.scoring_history(run_id,event_id,card_token,occurred_at,amount_minor)
      VALUES(p_run,i.event_id,i.card_token,i.occurred_at,i.amount_minor);
    END IF;
    UPDATE public.scoring_jobs SET
      status=CASE WHEN i.out_of_order OR i.publication_status='dead_letter' THEN 'failed'
        WHEN clock_timestamp()>=deadline_at THEN 'expired'
        WHEN i.publication_status='published' THEN 'scoring' ELSE 'pending' END,
      error_code=CASE WHEN i.out_of_order THEN 'out_of_order_event'
        WHEN i.publication_status='dead_letter' THEN 'publication_failed'
        WHEN clock_timestamp()>=deadline_at THEN 'deadline_expired' ELSE NULL END,
      attempts=CASE WHEN NOT i.out_of_order AND i.publication_status='published'
        AND clock_timestamp()<deadline_at THEN 1 ELSE 0 END,
      retryable=false,updated_at=clock_timestamp()
    WHERE run_id=p_run AND event_id=i.event_id RETURNING * INTO job;
    RETURN NEXT job;
  END LOOP;
END $$;

-- No browser/Data API role may call the checkpoint writer.
REVOKE ALL ON FUNCTION prepare_scoring_checkpoints(uuid,text,text,text,integer,jsonb) FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE format('REVOKE ALL ON FUNCTION public.prepare_scoring_checkpoints(uuid,text,text,text,integer,jsonb) FROM %I',role_name);
    END IF;
  END LOOP;
END $$;

-- Down Migration
SET LOCAL lock_timeout = '5s';
DROP FUNCTION prepare_scoring_checkpoints(uuid,text,text,text,integer,jsonb);
