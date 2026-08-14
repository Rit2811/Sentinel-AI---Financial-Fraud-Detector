export const openApiDocument = {
  openapi: '3.1.0',
  info: {
    title: 'Sentinel AI Authorization Ingestion API',
    version: '1.0.0',
    description:
      'Synthetic/tokenized event ingestion only; no fraud or payment decision is returned.',
  },
  paths: {
    '/health': {
      get: {
        summary: 'Process liveness',
        responses: { 200: { description: 'Alive' } },
      },
    },
    '/ready': {
      get: {
        summary: 'PostgreSQL and Redis readiness',
        responses: {
          200: { description: 'Dependencies ready' },
          503: { description: 'A dependency is unavailable' },
        },
      },
    },
    '/api/v1/authorization-events': {
      post: {
        summary: 'Ingest one version 1 authorization event',
        parameters: [
          {
            in: 'header',
            name: 'Idempotency-Key',
            required: true,
            schema: { type: 'string', format: 'uuid' },
          },
          {
            in: 'header',
            name: 'X-Correlation-ID',
            required: false,
            schema: { type: 'string', format: 'uuid' },
          },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/AuthorizationEventV1' },
              examples: {
                cardNotPresent: {
                  $ref: '#/components/examples/CardNotPresent',
                },
                cardPresent: { $ref: '#/components/examples/CardPresent' },
              },
            },
          },
        },
        responses: {
          200: { description: 'Identical idempotent replay' },
          202: {
            description: 'Accepted or quarantined after transaction commit',
          },
          400: { description: 'Malformed JSON' },
          409: { description: 'Same key with a different canonical payload' },
          413: { description: 'Payload exceeds 32 KiB' },
          415: { description: 'Content-Type is not application/json' },
          422: {
            description: 'Contract validation or prohibited field failure',
          },
          503: { description: 'PostgreSQL unavailable; no false success' },
        },
      },
    },
  },
  components: {
    schemas: {
      AuthorizationEventV1: {
        type: 'object',
        additionalProperties: false,
        required: [
          'schema_version',
          'event_id',
          'authorization_id',
          'occurred_at',
          'data_origin',
          'channel',
          'amount_minor',
          'currency',
          'card_token',
          'account_token',
          'merchant_id',
          'merchant_country',
          'entry_mode',
        ],
        properties: {
          schema_version: { const: '1.0' },
          event_id: { type: 'string', format: 'uuid' },
          authorization_id: { type: 'string', format: 'uuid' },
          occurred_at: { type: 'string', format: 'date-time' },
          data_origin: { const: 'synthetic_enriched' },
          channel: { enum: ['card_present', 'card_not_present'] },
          amount_minor: { type: 'integer', minimum: 0 },
          currency: { type: 'string', pattern: '^[A-Z]{3}$' },
          card_token: { type: 'string', pattern: '^[A-Za-z0-9_-]{8,128}$' },
          account_token: { type: 'string', pattern: '^[A-Za-z0-9_-]{8,128}$' },
          merchant_id: { type: 'string', pattern: '^[A-Za-z0-9_-]{3,128}$' },
          merchant_country: { type: 'string', pattern: '^[A-Z]{2}$' },
          entry_mode: {
            enum: ['chip', 'contactless', 'magstripe', 'manual', 'ecommerce'],
          },
          terminal_token: { type: 'string' },
          device_token: { type: 'string' },
        },
        allOf: [
          {
            if: { properties: { channel: { const: 'card_present' } } },
            then: {
              required: ['terminal_token'],
              not: { required: ['device_token'] },
            },
          },
          {
            if: { properties: { channel: { const: 'card_not_present' } } },
            then: {
              required: ['device_token'],
              not: { required: ['terminal_token'] },
            },
          },
        ],
      },
    },
    examples: {
      CardNotPresent: {
        value: {
          schema_version: '1.0',
          event_id: 'e82d7cc1-0d61-4f57-a6db-0e50d3708410',
          authorization_id: '1b1e8879-4ec8-47d4-b447-24c7dc17c2a7',
          occurred_at: '2026-08-10T12:30:00.000Z',
          data_origin: 'synthetic_enriched',
          channel: 'card_not_present',
          amount_minor: 129900,
          currency: 'INR',
          card_token: 'card_tok_demo_001',
          account_token: 'acct_tok_demo_001',
          merchant_id: 'merchant_demo_001',
          merchant_country: 'IN',
          entry_mode: 'ecommerce',
          device_token: 'device_tok_demo_001',
        },
      },
      CardPresent: {
        value: {
          schema_version: '1.0',
          event_id: '1414dca2-9d7d-47aa-8ab4-96086142ab95',
          authorization_id: 'd85964a0-f5a1-48c9-b1af-216cbb228d63',
          occurred_at: '2026-08-10T12:31:00.000Z',
          data_origin: 'synthetic_enriched',
          channel: 'card_present',
          amount_minor: 250000,
          currency: 'INR',
          card_token: 'card_tok_demo_002',
          account_token: 'acct_tok_demo_002',
          merchant_id: 'merchant_demo_002',
          merchant_country: 'IN',
          entry_mode: 'chip',
          terminal_token: 'terminal_demo_001',
        },
      },
    },
  },
}
