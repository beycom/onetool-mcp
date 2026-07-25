## MODIFIED Requirements

### Requirement: Optional Embeddings

Embeddings SHALL be opt-in and disabled by default. The mem pack SHALL load and
function without embedding credentials when embeddings are disabled. When enabled,
it SHALL use only the independent effective `embeddings` configuration and SHALL
NOT inherit a model, endpoint, or credential from generation configuration.

#### Scenario: Embeddings disabled (default)
- **GIVEN** `embeddings_enabled: false` (default)
- **WHEN** `mem.write()` is called
- **THEN** it SHALL store the memory with NULL embedding
- **AND** `mem.read()`, `mem.list()`, and pattern search SHALL work normally

#### Scenario: Embeddings enabled sync
- **GIVEN** `embeddings_enabled: true`, `embeddings_async: false`, and a valid independent embedding route
- **WHEN** `mem.write()` is called
- **THEN** it SHALL generate the embedding before returning

#### Scenario: Embeddings enabled async
- **GIVEN** `embeddings_enabled: true`, `embeddings_async: true`, and a valid independent embedding route
- **WHEN** `mem.write()` is called
- **THEN** it SHALL return immediately with NULL embedding
- **AND** a background worker SHALL generate the embedding and update the row

#### Scenario: Embedding route does not inherit generation configuration
- **GIVEN** generation uses CLIProxyAPI and no independent embedding route is configured
- **WHEN** an embedding-backed mem operation is requested
- **THEN** it SHALL fail with an actionable embedding-configuration error
- **AND** it SHALL NOT send an embedding request to CLIProxyAPI or a generation endpoint

#### Scenario: Embedding calls do not hold the DB lock
- **GIVEN** any operation that generates an embedding (write, update, append, batch update, refresh, import, restore, reindex, or the background worker)
- **WHEN** the embedding API call is made
- **THEN** the global SQLite connection lock SHALL NOT be held during the API round-trip
- **AND** the background worker's write-back SHALL be guarded on unchanged content so a concurrent update is never overwritten with a stale vector

#### Scenario: Embedding dimension mismatch
- **GIVEN** stored embeddings whose dimensions differ from the query embedding
- **WHEN** cosine similarity is computed during semantic search
- **THEN** it SHALL raise a clear error naming both dimensions and pointing to `mem.reindex(dry_run=False)` and SHALL never silently truncate

#### Scenario: Semantic search when disabled
- **GIVEN** `embeddings_enabled: false`
- **WHEN** `mem.search(mode="semantic")` or `mem.search(mode="hybrid")` is called
- **THEN** it SHALL return a message about enabling `embeddings_enabled`

#### Scenario: Semantic search when enabled but no embeddings
- **GIVEN** `embeddings_enabled: true` but no memories have embeddings yet
- **WHEN** `mem.search(mode="semantic")` is called
- **THEN** it SHALL return a message about running `mem.embed()`

### Requirement: LLM Q&A (mem.ask)

The `mem.ask()` function SHALL synthesise an answer from a memory's content using
the effective shared generation route and SHALL accept optional `model` and
`effort` arguments.

#### Scenario: Single question
- **GIVEN** a topic that exists
- **WHEN** `mem.ask(topic="projects/onetool/rules", q="What are the rules?")` is called
- **THEN** it SHALL retrieve the memory content and pass it to the effective generation route with the question
- **AND** return a synthesised answer

#### Scenario: Multiple questions
- **GIVEN** a topic that exists
- **WHEN** `mem.ask(topic="...", q=["Q1", "Q2"])` is called
- **THEN** it SHALL answer each question in sequence using the same memory content

#### Scenario: Model and effort override
- **GIVEN** a topic that exists
- **WHEN** `mem.ask(topic="...", q="...", model="luna", effort="medium")` is called
- **THEN** it SHALL resolve `luna` from the shared registry and request medium effort for that call

#### Scenario: Topic does not exist
- **GIVEN** a topic that does not exist in the database
- **WHEN** `mem.ask(topic="nonexistent", q="...")` is called
- **THEN** it SHALL raise with a clear "not found" error

#### Scenario: LLM not configured
- **GIVEN** no valid generation route or effective model is configured
- **WHEN** `mem.ask()` is called
- **THEN** it SHALL raise with a clear message identifying the missing generation setting

#### Scenario: CLIProxyAPI generation is independent of embeddings
- **GIVEN** `mem.ask` uses CLIProxyAPI and embeddings are disabled or use a different provider
- **WHEN** `mem.ask()` is called
- **THEN** generation SHALL use CLIProxyAPI without reading or changing the embedding route

