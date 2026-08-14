import pino from 'pino'

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  redact: {
    paths: [
      'req.headers.authorization',
      'req.headers.cookie',
      'req.headers.idempotency-key',
      'body',
      '*.body',
      '*.card_number',
      '*.cvv',
      '*.cvc',
      '*.pin',
      '*.track_data',
    ],
    censor: '[REDACTED]',
  },
})
