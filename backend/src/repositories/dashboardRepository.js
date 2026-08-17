const DASHBOARD_SNAPSHOT_QUERY = `
  WITH current_clock AS (
    SELECT clock_timestamp() AS current_time
  ),
  bounds AS (
    SELECT
      current_clock.current_time - $1::interval AS from_time,
      current_clock.current_time AS to_time,
      $2::interval AS bucket_width
    FROM current_clock
  ),
  buckets AS (
    SELECT series AS bucket_start
    FROM bounds,
      generate_series(
        bounds.from_time,
        bounds.to_time - bounds.bucket_width,
        bounds.bucket_width
      ) AS series
  ),
  activity AS (
    SELECT
      bucket.bucket_start,
      (
        SELECT count(*)::int
        FROM authorization_events AS event
        WHERE event.created_at >= bucket.bucket_start
          AND event.created_at < bucket.bucket_start + bounds.bucket_width
      ) AS ingested,
      (
        SELECT count(DISTINCT receipt.event_id)::int
        FROM stream_processing_receipts AS receipt
        WHERE receipt.processed_at >= bucket.bucket_start
          AND receipt.processed_at < bucket.bucket_start + bounds.bucket_width
      ) AS processed,
      (
        SELECT count(*)::int
        FROM ingestion_attempts AS attempt
        WHERE attempt.outcome <> 'accepted'
          AND attempt.created_at >= bucket.bucket_start
          AND attempt.created_at < bucket.bucket_start + bounds.bucket_width
      ) AS rejected
    FROM buckets AS bucket
    CROSS JOIN bounds
  ),
  summary AS (
    SELECT
      (SELECT count(*)::int FROM authorization_events) AS total_events,
      (
        SELECT count(DISTINCT event_id)::int
        FROM stream_processing_receipts
      ) AS processed_events,
      (
        SELECT count(*)::int
        FROM ingestion_attempts
        WHERE outcome <> 'accepted'
      ) AS rejected_attempts,
      (SELECT count(*)::int FROM quarantined_events) AS quarantined_events,
      (
        SELECT count(*)::int
        FROM authorization_event_outbox
        WHERE status IN ('pending', 'publishing')
      ) AS pending_events,
      (
        SELECT count(*)::int
        FROM authorization_event_outbox
        WHERE status = 'dead_letter'
      ) AS dead_letter_events,
      (SELECT max(created_at) FROM authorization_events) AS last_event_at
  ),
  channels AS (
    SELECT
      count(*) FILTER (WHERE channel = 'card_present')::int AS card_present,
      count(*) FILTER (WHERE channel = 'card_not_present')::int AS card_not_present
    FROM authorization_events
  )
  SELECT
    bounds.from_time,
    bounds.to_time,
    extract(epoch FROM bounds.bucket_width)::int AS bucket_seconds,
    summary.*,
    channels.card_present,
    channels.card_not_present,
    COALESCE(
      (
        SELECT json_agg(
          json_build_object(
            'started_at', activity.bucket_start,
            'ingested', activity.ingested,
            'processed', activity.processed,
            'rejected', activity.rejected
          )
          ORDER BY activity.bucket_start
        )
        FROM activity
      ),
      '[]'::json
    ) AS activity
  FROM bounds
  CROSS JOIN summary
  CROSS JOIN channels
`

export async function getDashboardSnapshot(pool, range) {
  const result = await pool.query(DASHBOARD_SNAPSHOT_QUERY, [
    range.duration,
    range.bucket,
  ])
  return result.rows[0]
}
