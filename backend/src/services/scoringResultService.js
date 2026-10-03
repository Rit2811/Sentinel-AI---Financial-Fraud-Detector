export function createScoringResultService(pool, runId) {
  return {
    async lookup(eventId) {
      const result = await pool.query(
        `SELECT e.event_id, e.schema_version, j.status, j.correlation_id,
                j.bundle_sha256, j.model_version, j.policy_version, j.feature_version,
                j.attempts, j.retryable, j.next_attempt_at, j.deadline_at, j.error_code,
                r.probability, r.action, r.review_threshold, r.block_threshold, r.decision_at,
                x.state AS execution_state, x.executed_at, h.resolution,
                h.resolution_id, h.reviewer_id, h.notes, h.resolved_at
         FROM authorization_events e
         LEFT JOIN scoring_jobs j ON j.event_id = e.event_id AND j.run_id = $2
         LEFT JOIN scoring_results r ON r.event_id = j.event_id AND r.run_id = j.run_id
         LEFT JOIN simulated_executions x ON x.event_id = j.event_id AND x.run_id = j.run_id
         LEFT JOIN review_resolutions h ON h.event_id = j.event_id AND h.run_id = j.run_id
         WHERE e.event_id = $1`,
        [eventId, runId],
      )
      const row = result.rows[0]
      if (!row) return null
      let assignedRun = false
      if (!row.status && row.schema_version === '2.0') {
        try {
          const eligibility = await pool.query(
            `SELECT EXISTS(SELECT 1 FROM scoring_runs s JOIN authorization_events e
               ON e.event_id=$1 AND e.created_at>=s.started_at WHERE s.run_id=$2) AS eligible`,
            [eventId, runId],
          )
          assignedRun = eligibility.rows[0]?.eligible === true
        } catch (error) {
          if (error.code !== '42P01') throw error
          assignedRun = false
        }
      }
      const status = row.status ?? (assignedRun ? 'pending' : 'unavailable')
      if (
        ![
          'pending',
          'scoring',
          'scored',
          'unavailable',
          'failed',
          'expired',
        ].includes(status)
      ) {
        throw new Error('invalid_stored_scoring_state')
      }
      const scored = status === 'scored'
      const { probability: p, review_threshold: r, block_threshold: b } = row
      if (
        scored &&
        (![p, r, b].every(
          (value) => typeof value === 'number' && Number.isFinite(value),
        ) ||
          p < 0 ||
          p > 1 ||
          r < 0 ||
          r >= b ||
          b > 1 ||
          row.action !== (p < r ? 'Pass' : p < b ? 'Review' : 'Block') ||
          !row.decision_at)
      )
        throw new Error('invalid_stored_scoring_evidence')
      return {
        event_id: row.event_id,
        run_id: runId,
        correlation_id: row.correlation_id ?? null,
        status,
        available: scored,
        probability: scored ? p : null,
        risk_score: scored ? 100 * p : null,
        action: scored ? row.action : null,
        thresholds: scored ? { review: r, block: b } : null,
        versions: {
          bundle_sha256: row.bundle_sha256 ?? null,
          model: row.model_version ?? null,
          policy: row.policy_version ?? null,
          features: row.feature_version ?? null,
        },
        decision_at: scored ? row.decision_at : null,
        deadline_at: row.deadline_at ?? null,
        retryable: row.retryable ?? assignedRun,
        next_attempt_at: row.next_attempt_at ?? null,
        attempts: row.attempts ?? 0,
        reason_code:
          row.error_code ??
          (assignedRun
            ? 'awaiting_worker'
            : row.status
              ? null
              : row.schema_version === '2.0'
                ? 'scoring_not_activated'
                : 'unsupported_scoring_schema'),
        execution_state: row.resolution
          ? row.resolution === 'allow'
            ? 'allowed'
            : 'rejected'
          : (row.execution_state ?? 'not_executed'),
        executed_at: row.resolved_at ?? row.executed_at ?? null,
        review_resolution: row.resolution
          ? {
              resolution_id: row.resolution_id,
              reviewer_id: row.reviewer_id,
              resolution: row.resolution,
              notes: row.notes,
              resolved_at: row.resolved_at,
            }
          : null,
      }
    },
  }
}
