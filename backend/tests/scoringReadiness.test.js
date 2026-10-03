import { scoringReadiness } from '../src/services/scoringReadinessService.js'

const runId = '1414dca2-9d7d-47aa-8ab4-96086142ab95'
const valid = {
  mode: 'application',
  durability_contract: 'postcommit-v1',
  gate_report_sha256: 'a'.repeat(64),
  ready: true,
  blocked: false,
  fresh: true,
}
test.each([
  [valid, true],
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
