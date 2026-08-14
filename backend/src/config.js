export const config = Object.freeze({
  port: Number(process.env.PORT ?? 8000),
  postgresUrl:
    process.env.POSTGRES_URL ??
    'postgresql://sentinel:sentinel_local_only@127.0.0.1:15432/sentinel',
  redisUrl:
    process.env.REDIS_URL ?? 'redis://:sentinel_local_only@127.0.0.1:16379/0',
  readinessTimeoutMs: Number(process.env.READINESS_TIMEOUT_SECONDS ?? 2) * 1000,
  bodyLimit: '32kb',
  stream: Object.freeze({
    name: process.env.STREAM_NAME ?? 'authorization.events.v1',
    deadLetterName:
      process.env.STREAM_DEAD_LETTER_NAME ??
      'authorization.events.v1.dead-letter',
    group: process.env.STREAM_CONSUMER_GROUP ?? 'fraud-proof-v1',
    consumerPurpose:
      process.env.STREAM_CONSUMER_PURPOSE ?? 'task4-proof-consumer',
    batchSize: Number(process.env.STREAM_BATCH_SIZE ?? 50),
    blockMs: Number(process.env.STREAM_BLOCK_MS ?? 2000),
    claimIdleMs: Number(process.env.STREAM_CLAIM_IDLE_MS ?? 10000),
    pollMs: Number(process.env.STREAM_POLL_MS ?? 500),
    maxAttempts: Number(process.env.STREAM_MAX_ATTEMPTS ?? 5),
    retention: Number(process.env.STREAM_RETENTION ?? 10000),
  }),
})
