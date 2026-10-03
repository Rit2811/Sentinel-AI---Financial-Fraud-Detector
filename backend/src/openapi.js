export const openApiDocument = {
  openapi: '3.1.0',
  info: {
    title: 'Sentinel AI Authorization Ingestion API',
    version: '1.0.0',
    description:
      'Synthetic event ingestion and gated, protected stored-result retrieval. No scoring worker is active during Task 6 preparation.',
  },
  paths: {
    '/api/v1/transactions/{eventId}/review-resolution': {
      post: {
        summary:
          'Resolve a pending simulated review once; preserve the model action',
        description:
          'Uses a separate REVIEW_API_TOKEN bound to server-configured REVIEWER_ID and SCORING_RUN_ID. No confirmed fraud label is created. Never include card numbers or personal data in notes.',
        security: [{ ReviewBearer: [] }],
        parameters: [
          {
            in: 'path',
            name: 'eventId',
            required: true,
            schema: { type: 'string', format: 'uuid' },
          },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                additionalProperties: false,
                required: ['resolution_id', 'resolution', 'notes'],
                properties: {
                  resolution_id: { type: 'string', format: 'uuid' },
                  resolution: { enum: ['allow', 'reject'] },
                  notes: { type: 'string', minLength: 1, maxLength: 2000 },
                },
              },
            },
          },
        },
        responses: {
          200: {
            description: 'Identical retry returns the original resolution',
          },
          201: {
            description:
              'Human resolution and simulated outcome durably recorded',
          },
          400: { description: 'Invalid UUID or JSON' },
          401: { description: 'Invalid reviewer credential' },
          404: { description: 'No review execution exists' },
          409: {
            description:
              'Not a pending review, already resolved differently, or reused resolution identity',
          },
          413: { description: 'Body too large' },
          415: { description: 'JSON required' },
          422: { description: 'Invalid fields, resolution or notes' },
          503: {
            description:
              'Review access is unconfigured or storage is unavailable',
          },
        },
      },
    },
    '/ready/scoring': {
      get: {
        summary: 'Scoring readiness, separate from infrastructure readiness',
        responses: {
          503: { description: 'Scoring is not activated during preparation' },
        },
      },
    },
    '/api/v1/transactions/{eventId}/result': {
      get: {
        summary:
          'Retrieve the original stored scoring state for the configured run',
        description:
          'Requires RESULT_API_TOKEN and SCORING_RUN_ID. Pending and unavailable states have no score/action. Model action is not simulator execution or confirmed fraud.',
        security: [{ ResultBearer: [] }],
        parameters: [
          {
            in: 'path',
            name: 'eventId',
            required: true,
            schema: { type: 'string', format: 'uuid' },
          },
        ],
        responses: {
          200: {
            description: 'Stored state; no decision is inferred from ingestion',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/ScoringResult' },
              },
            },
          },
          400: { description: 'Invalid event UUID' },
          401: { description: 'Missing or invalid access token' },
          404: { description: 'No accepted event exists' },
          503: {
            description:
              'Result access is not configured, schema is absent or storage is unavailable',
          },
        },
      },
    },
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
    '/api/v1/dashboard': {
      get: {
        summary: 'Read a non-sensitive operational dashboard snapshot',
        description:
          'Returns PostgreSQL-backed ingestion and stream-processing aggregates. It does not return fraud scores or payment decisions.',
        parameters: [
          {
            in: 'query',
            name: 'range',
            required: false,
            schema: { enum: ['1h', '24h', '7d'], default: '24h' },
          },
        ],
        responses: {
          200: {
            description: 'Current aggregate dashboard snapshot',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/DashboardSnapshotV1' },
              },
            },
          },
          400: { description: 'Unsupported activity range' },
          503: { description: 'PostgreSQL dashboard query unavailable' },
        },
      },
    },
    '/api/v1/authorization-events': {
      post: {
        summary: 'Ingest one version 1 or Sparkov version 2 event',
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
              schema: {
                oneOf: [
                  { $ref: '#/components/schemas/AuthorizationEventV1' },
                  { $ref: '#/components/schemas/AuthorizationEventV2' },
                ],
              },
              examples: {
                cardNotPresent: {
                  $ref: '#/components/examples/CardNotPresent',
                },
                cardPresent: { $ref: '#/components/examples/CardPresent' },
                sparkovReplay: { $ref: '#/components/examples/SparkovReplay' },
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
    securitySchemes: {
      ResultBearer: { type: 'http', scheme: 'bearer' },
      ReviewBearer: { type: 'http', scheme: 'bearer' },
    },
    schemas: {
      ScoringResult: {
        type: 'object',
        properties: {
          event_id: { type: 'string', format: 'uuid' },
          run_id: { type: 'string', format: 'uuid' },
          status: {
            enum: [
              'pending',
              'scoring',
              'scored',
              'unavailable',
              'failed',
              'expired',
            ],
          },
          available: { type: 'boolean' },
          probability: { type: ['number', 'null'], minimum: 0, maximum: 1 },
          risk_score: { type: ['number', 'null'], minimum: 0, maximum: 100 },
          action: { enum: ['Pass', 'Review', 'Block', null] },
          thresholds: { type: ['object', 'null'] },
          versions: { type: 'object' },
          decision_at: { type: ['string', 'null'], format: 'date-time' },
          retryable: { type: 'boolean' },
          reason_code: { type: ['string', 'null'] },
          execution_state: {
            enum: ['not_executed', 'allowed', 'pending_review', 'rejected'],
          },
          executed_at: { type: ['string', 'null'], format: 'date-time' },
          review_resolution: { type: ['object', 'null'] },
        },
      },
      AuthorizationEventV2: {
        type: 'object',
        additionalProperties: false,
        description:
          'Simulated replay. Source wall clock is interpreted as UTC and USD is assumed; neither is an observed source fact. Raw identifiers, labels and personal fields are forbidden recursively.',
        required: [
          'schema_version',
          'event_id',
          'authorization_id',
          'occurred_at',
          'data_origin',
          'amount_minor',
          'currency',
          'card_token',
          'merchant_id',
          'merchant_category',
          'time_basis',
          'currency_basis',
        ],
        properties: {
          schema_version: { const: '2.0' },
          data_origin: { const: 'sparkov_replay' },
          event_id: { type: 'string', format: 'uuid' },
          authorization_id: { type: 'string', format: 'uuid' },
          occurred_at: {
            type: 'string',
            format: 'date-time',
            pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$',
          },
          amount_minor: {
            type: 'integer',
            minimum: 0,
            maximum: 9007199254740991,
          },
          currency: { const: 'USD' },
          card_token: { type: 'string', pattern: '^card_[0-9a-f]{64}$' },
          merchant_id: { type: 'string', pattern: '^merchant_[0-9a-f]{64}$' },
          merchant_category: {
            type: 'string',
            minLength: 1,
            maxLength: 128,
            pattern: '^\\S(?:[\\s\\S]*\\S)?$',
          },
          time_basis: { const: 'source_wall_clock_as_utc' },
          currency_basis: { const: 'simulation_assumption' },
        },
      },
      DashboardActivityBucketV1: {
        type: 'object',
        additionalProperties: false,
        required: ['started_at', 'ingested', 'processed', 'rejected'],
        properties: {
          started_at: { type: 'string', format: 'date-time' },
          ingested: { type: 'integer', minimum: 0 },
          processed: { type: 'integer', minimum: 0 },
          rejected: { type: 'integer', minimum: 0 },
        },
      },
      DashboardSnapshotV1: {
        type: 'object',
        additionalProperties: false,
        required: [
          'schema_version',
          'generated_at',
          'range',
          'window',
          'summary',
          'channels',
          'activity',
        ],
        properties: {
          schema_version: { const: '1.0' },
          generated_at: { type: 'string', format: 'date-time' },
          range: { enum: ['1h', '24h', '7d'] },
          window: { type: 'object' },
          summary: { type: 'object' },
          channels: { type: 'object' },
          activity: {
            type: 'array',
            items: {
              $ref: '#/components/schemas/DashboardActivityBucketV1',
            },
          },
        },
      },
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
      SparkovReplay: {
        value: {
          schema_version: '2.0',
          event_id: 'd6a69ef3-8b61-5f3c-b87d-ce5e0db51299',
          authorization_id: 'afd883d1-8f43-5dfb-b944-3a77b10349e5',
          occurred_at: '2019-01-01T00:00:00Z',
          data_origin: 'sparkov_replay',
          amount_minor: 1234,
          currency: 'USD',
          card_token: `card_${'a'.repeat(64)}`,
          merchant_id: `merchant_${'b'.repeat(64)}`,
          merchant_category: 'grocery_pos',
          time_basis: 'source_wall_clock_as_utc',
          currency_basis: 'simulation_assumption',
        },
      },
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
