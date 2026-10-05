import { performance } from 'node:perf_hooks'

export function publisherProfiler(log) {
  const records = []
  const enabled = process.env.PUBLISHER_PROFILE === '1'
  return {
    async measure(stage, eventId, operation, eventIds = []) {
      if (!enabled) return operation()
      const start = performance.now()
      const cpu = process.cpuUsage()
      try {
        return await operation()
      } finally {
        const used = process.cpuUsage(cpu)
        records.push({
          kind: 'stage_timing',
          stage,
          event_id: eventId,
          event_ids: eventIds,
          elapsed_ms: performance.now() - start,
          process_cpu_ms: (used.user + used.system) / 1000,
        })
      }
    },
    flush() {
      if (records.length)
        log.info(
          { kind: 'stage_profile_batch', records },
          'Publisher stage timings',
        )
    },
  }
}
