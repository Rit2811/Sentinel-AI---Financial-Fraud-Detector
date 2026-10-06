import pg from 'pg'

import { importedObjectProtection } from '../src/databaseSnapshot.js'

test('app-only lockdown quotes identifiers and preserves built-in schemas', () => {
  const client = new pg.Client()
  const sql = importedObjectProtection(client, {
    fingerprints: { 'events"quoted': { count: '1' } },
    sequences: [{ sequencename: 'audit_id_seq' }],
    functions: [{ proname: 'guard_event', arguments: '' }],
  })
  expect(sql).toContain(
    'ALTER TABLE public."events""quoted" ENABLE ROW LEVEL SECURITY;',
  )
  expect(sql).toContain(
    'REVOKE ALL ON TABLE public."events""quoted" FROM PUBLIC, anon, authenticated, service_role;',
  )
  expect(sql).toContain('REVOKE ALL ON SEQUENCE public."audit_id_seq"')
  expect(sql).toContain('REVOKE ALL ON FUNCTION public."guard_event"()')
  expect(sql).not.toContain('auth.')
  expect(sql).not.toContain('ALTER SCHEMA')
})
