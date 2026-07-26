---
name: ot-db
description: Use when inspecting tables, sampling rows, reading schemas, or executing parameterized SQL against a SQLAlchemy-compatible database through OneTool. Apply schema-first, read-only-by-default behavior.
user-invocable: false
---

# OneTool Database

Use `db` for controlled database introspection and queries.

## Availability

Check `__ot ot.packs(pattern='db', info='min')`, then confirm the intended `db_url` without
exposing credentials. If `[dev]`, a driver, or a database connection is missing, stop and offer
installation or configuration guidance; do not install drivers or add secrets without a separate request.

## Workflow

1. Select the exact connection and inspect tables and schema.
2. Start with a bounded read-only query or sample.
3. Parameterize values; never interpolate untrusted SQL fragments.
4. Explain expected rows and side effects before a write.
5. Execute mutation only on explicit request, then verify affected state.

Avoid broad selects, unbounded scans, and production writes by default. A successful query does
not establish data correctness; report the connection and scope used.
