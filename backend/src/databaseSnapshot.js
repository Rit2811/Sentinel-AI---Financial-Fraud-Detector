export async function applicationSnapshot(client) {
  await client.query("SET TIME ZONE 'UTC'")
  await client.query('SET extra_float_digits=3')
  const tables = (
    await client.query(
      "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
    )
  ).rows.map((row) => row.tablename)
  const fingerprints = {}
  for (const table of tables) {
    const ident = client.escapeIdentifier(table)
    fingerprints[table] = (
      await client.query(`
      SELECT count(*)::text AS count,
             encode(sha256(convert_to(coalesce(string_agg(md5(to_jsonb(t)::text), '' ORDER BY md5(to_jsonb(t)::text)), ''), 'UTF8')), 'hex') AS sha256
      FROM public.${ident} t
    `)
    ).rows[0]
  }
  const constraints = (
    await client.query(
      "SELECT c.conrelid::regclass::text AS relation,c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public' ORDER BY 1,2",
    )
  ).rows
  const indexes = (
    await client.query(
      "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
    )
  ).rows
  const functions = (
    await client.query(
      "SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY 1,2",
    )
  ).rows
  const triggers = (
    await client.query(
      "SELECT t.tgrelid::regclass::text AS relation,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2",
    )
  ).rows
  const sequences = (
    await client.query(
      "SELECT sequencename,start_value,min_value,max_value,increment_by,cycle,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",
    )
  ).rows
  return { fingerprints, constraints, indexes, functions, triggers, sequences }
}

export function importedObjectProtection(client, snapshot) {
  const identifier = (name) => 'public.' + client.escapeIdentifier(name)
  const roles = 'PUBLIC, anon, authenticated, service_role'
  const statements = []
  for (const table of Object.keys(snapshot.fingerprints)) {
    statements.push(
      `ALTER TABLE ${identifier(table)} ENABLE ROW LEVEL SECURITY;`,
    )
    statements.push(`REVOKE ALL ON TABLE ${identifier(table)} FROM ${roles};`)
  }
  for (const sequence of snapshot.sequences) {
    statements.push(
      `REVOKE ALL ON SEQUENCE ${identifier(sequence.sequencename)} FROM ${roles};`,
    )
  }
  for (const fn of snapshot.functions) {
    // Identity arguments are PostgreSQL catalog syntax, not user-provided SQL.
    statements.push(
      `REVOKE ALL ON FUNCTION ${identifier(fn.proname)}(${fn.arguments}) FROM ${roles};`,
    )
  }
  return statements.join('\n') + '\n'
}
