export async function scoringReadiness(pool, runId) {
  if (!/^[0-9a-f-]{36}$/i.test(runId ?? '')) return false
  try {
    const result = await pool.query(
      `SELECT r.mode, r.gate_report_sha256, r.durability_contract, h.ready, h.blocked,
              h.heartbeat_at > clock_timestamp() - interval '5 seconds' AS fresh
       FROM scoring_runs r JOIN scoring_worker_health h USING(run_id) WHERE r.run_id=$1`,
      [runId],
    )
    const row = result.rows[0]
    return Boolean(
      row &&
      row.mode === 'application' &&
      row.durability_contract === 'postcommit-v1' &&
      row.gate_report_sha256 &&
      row.ready &&
      !row.blocked &&
      row.fresh,
    )
  } catch {
    return false
  }
}
