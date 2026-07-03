## ADDED Requirements

### Requirement: kb.search — Missing or disabled embeddings guidance

`kb.search()` SHALL return a clear, actionable guidance message, instead of a raw internal error, when `mode` is `hybrid`/`semantic` and the target database's embeddings are disabled or were never generated.

This mirrors the existing guidance pattern in `mem.search()`
(`src/otutil/tools/_mem/search.py`), applied to the `knowledge` pack's
per-database config and `sqlite-vec`-backed vector index.

This requirement is distinct from "Error handling — missing sqlite-vec"
(which covers the `sqlite-vec` **package** not being installed at all): this
requirement covers the case where `sqlite-vec` **is** available but the
target database's embeddings are disabled by configuration or have not been
generated yet.

#### Scenario: Embeddings disabled for the target database
- **WHEN** `kb.search(q='...', db='rhino', mode='hybrid')` is called
- **AND** `tools.knowledge.kb.rhino.db.embeddings_enabled` is `false`
- **THEN** the call SHALL return "Semantic search requires embeddings. Enable with: tools.knowledge.kb.rhino.db.embeddings_enabled: true"
- **AND** SHALL NOT open a database connection or attempt a vector query

#### Scenario: Embeddings enabled but never generated
- **WHEN** `kb.search(q='...', db='rhino', mode='semantic')` is called
- **AND** `tools.knowledge.kb.rhino.db.embeddings_enabled` is `true` (or unset, which defaults to `true`)
- **AND** the database's `chunks_vec` table has no rows (no chunk has ever been embedded)
- **THEN** the call SHALL return "No embeddings found for 'rhino'. Run kb.reindex(db='rhino') to generate them."
- **AND** SHALL NOT surface a raw SQL or `sqlite-vec` exception message

#### Scenario: Keyword mode is unaffected
- **WHEN** `kb.search(q='...', db='rhino', mode='keyword')` is called
- **AND** the database has no embeddings
- **THEN** the call SHALL proceed with FTS5-only search and SHALL NOT check embeddings state
