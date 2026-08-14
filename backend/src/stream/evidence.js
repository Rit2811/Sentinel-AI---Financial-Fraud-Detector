import { pool } from '../db.js'
import { getStreamingEvidence } from '../repositories/streamRepository.js'

const eventId = process.argv[2]
if (!eventId) {
  console.error('Usage: npm run stream:evidence -- <event-id>')
  process.exitCode = 1
} else {
  const evidence = await getStreamingEvidence(pool, eventId)
  console.log(JSON.stringify(evidence, null, 2))
  if (!evidence) process.exitCode = 2
}
await pool.end()
