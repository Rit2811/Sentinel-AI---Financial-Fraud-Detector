export function createReviewResolutionService(pool, runId) {
  return {
    async resolve(eventId, reviewerId, input) {
      const client = await pool.connect()
      try {
        await client.query('BEGIN')
        const found = await client.query(
          `SELECT state FROM simulated_executions WHERE run_id = $1 AND event_id = $2 FOR UPDATE`,
          [runId, eventId],
        )
        if (!found.rowCount) {
          await client.query('ROLLBACK')
          return { status: 404, body: { code: 'review_not_found' } }
        }
        if (found.rows[0].state !== 'pending_review') {
          await client.query('ROLLBACK')
          return { status: 409, body: { code: 'not_pending_review' } }
        }
        const prior = await client.query(
          `SELECT resolution_id, reviewer_id, resolution, notes, resolved_at
           FROM review_resolutions WHERE run_id = $1 AND event_id = $2`,
          [runId, eventId],
        )
        if (prior.rowCount) {
          const row = prior.rows[0]
          const identical =
            row.resolution_id === input.resolution_id &&
            row.reviewer_id === reviewerId &&
            row.resolution === input.resolution &&
            row.notes === input.notes
          await client.query('COMMIT')
          return identical
            ? { status: 200, body: row }
            : { status: 409, body: { code: 'review_already_resolved' } }
        }
        const saved = await client.query(
          `INSERT INTO review_resolutions (run_id, event_id, resolution_id, reviewer_id, resolution, notes)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING resolution_id, reviewer_id, resolution, notes, resolved_at`,
          [
            runId,
            eventId,
            input.resolution_id,
            reviewerId,
            input.resolution,
            input.notes,
          ],
        )
        await client.query('COMMIT')
        return { status: 201, body: saved.rows[0] }
      } catch (error) {
        await client.query('ROLLBACK').catch(() => {})
        if (error.code === '23505')
          return { status: 409, body: { code: 'resolution_identity_conflict' } }
        throw new Error('review_store_unavailable', { cause: error })
      } finally {
        client.release()
      }
    },
  }
}
