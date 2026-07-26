<!-- Generated from skills/ot-db/SKILL.md; do not edit. -->
# OneTool Database

Use `db` for controlled database introspection and queries.

## Capability boundary

Check `__ot ot.packs(pattern='db', info='min')`, then confirm the intended `db_url` without
exposing credentials. If `[dev]`, a driver, or a database connection is missing, stop and offer
installation or configuration guidance; do not install drivers or add secrets without a separate request.

Use `tables` for inventory, `schema` for exact columns/constraints, `sample` for bounded
representative data, and `query` for explicit SQL. `db.query` currently defaults
`read_only=False`; therefore every call must make the mutation decision explicit. Execution uses
SQLAlchemy AUTOCOMMIT semantics, so a successful write may already be committed.

## Workflow

1. Select the exact connection and inspect tables and schema.
2. Start with schema/sample or a bounded query using `read_only=True`.
3. Parameterize values; never interpolate untrusted SQL fragments.
4. Explain expected rows and side effects before a write.
5. Execute mutation only on explicit request, then verify affected state.

## Safety and side effects

The database account defines the real authorization boundary; `read_only=True` is a query guard,
not a substitute for least-privilege credentials. URLs may contain secrets and must not be logged
or echoed. Parameterize values, bound scans/results, and never interpolate untrusted identifiers or
SQL fragments without validation. AUTOCOMMIT makes write recovery database-specific.

## Verification and recovery

Inspect the structured return shape, row counts, and a targeted follow-up read. For mutation,
verify exact affected state and disclose transaction/autocommit behavior. On failure, do not retry a
write until checking whether it committed; repair one connection/driver/config issue, then retry
only when idempotence is established.
