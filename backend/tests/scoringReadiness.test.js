import { scoringReadiness } from '../src/services/scoringReadinessService.js'

const runId = '1414dca2-9d7d-47aa-8ab4-96086142ab95'

test('candidate activation hold prevents public readiness without querying', async () => {
  const previous = process.env.SCORING_ACTIVATION_HOLD
  process.env.SCORING_ACTIVATION_HOLD = '1'
  try {
    expect(
      await scoringReadiness(
        {
          query: () => {
            throw Error('must not query')
          },
        },
        runId,
      ),
    ).toBe(false)
  } finally {
    if (previous === undefined) delete process.env.SCORING_ACTIVATION_HOLD
    else process.env.SCORING_ACTIVATION_HOLD = previous
  }
})
const valid = {
  diagnostic_only: false,
  mode: 'application',
  durability_contract: 'postcommit-v1',
  gate_report_sha256: 'a'.repeat(64),
  ready: true,
  blocked: false,
  fresh: true,
}
test.each([
  [valid, true],
  [{ ...valid, diagnostic_only: true }, false],
  [{ ...valid, durability_contract: 'legacy-precommit' }, false],
  [{ ...valid, mode: 'fixture' }, false],
  [{ ...valid, fresh: false }, false],
  [{ ...valid, blocked: true }, false],
  [{ ...valid, ready: false }, false],
  [{ ...valid, gate_report_sha256: null }, false],
  [undefined, false],
])(
  'scoring readiness requires a fresh approved application worker',
  async (row, expected) => {
    expect(
      await scoringReadiness(
        { query: async () => ({ rows: row ? [row] : [] }) },
        runId,
      ),
    ).toBe(expected)
  },
)
test('missing configuration or database failure stays not ready', async () => {
  const pool = {
    query: async () => {
      throw Error('private database detail')
    },
  }
  expect(await scoringReadiness(pool, runId)).toBe(false)
  expect(await scoringReadiness(pool, undefined)).toBe(false)
})
