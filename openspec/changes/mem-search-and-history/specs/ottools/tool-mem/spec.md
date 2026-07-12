# tool-mem Delta Specification

## MODIFIED Requirements

### Requirement: Memory Search

The `mem.search()` function SHALL search memories in three modes: `semantic` (vector similarity), `keyword` (FTS5 BM25 full-text ranking), and `hybrid` (Reciprocal Rank Fusion of both).

#### Scenario: Semantic search
- **GIVEN** a query string
- **WHEN** `mem.search(query="authentication patterns")` is called
- **THEN** it SHALL generate a query embedding
- **AND** rank results by cosine similarity (via the vector index when available, otherwise via the fallback scan)
- **AND** report each result's score as a cosine similarity in [0, 1] rounded to 4 decimal places

#### Scenario: Keyword search
- **GIVEN** a keyword query
- **WHEN** `mem.search(query="database", mode="keyword")` is called
- **THEN** it SHALL rank results by BM25 relevance against the FTS5 index over topic and content
- **AND** report each result's score as the absolute BM25 value (higher = more relevant), not a hardcoded constant

#### Scenario: Keyword query sanitisation and prefix fallback
- **GIVEN** a query containing FTS5 operator characters or only stopwords
- **WHEN** `mem.search(mode="keyword")` is called
- **THEN** operator characters SHALL be stripped and stopwords removed before matching
- **AND** if the sanitised query yields no rows, it SHALL retry with `*` prefix-suffixed terms for partial matching

#### Scenario: Hybrid search
- **GIVEN** a query with mode="hybrid"
- **WHEN** `mem.search(query="error handling", mode="hybrid")` is called
- **THEN** it SHALL combine the BM25-ranked keyword results and the similarity-ranked semantic results via Reciprocal Rank Fusion (k=60)
- **AND** both input lists SHALL be genuinely relevance-ranked

#### Scenario: Search extract length
- **GIVEN** a search query and content longer than the extract limit
- **WHEN** `mem.search(query="test", extract=50)` is called
- **THEN** result content extracts SHALL be truncated to 50 characters with "..."
- **AND** `extract=0` SHALL return full content without truncation
- **AND** default extract length SHALL come from config `search_extract` (default: 200)

#### Scenario: Topic and category filtering
- **GIVEN** optional topic, category, and tags filters
- **WHEN** `mem.search(query="rules", topic="projects/", category="rule")` is called
- **THEN** it SHALL restrict results to matching topic prefix, category, and tags in all three modes

### Requirement: Embedding Token Handling

Content exceeding the embedding model's token limit SHALL be chunked and averaged rather than truncated, preserving semantic coverage of the full document.

#### Scenario: Content within token limit
- **GIVEN** content within the model's token limit (minus safety margin)
- **WHEN** an embedding is generated
- **THEN** the full content SHALL be embedded as a single string

#### Scenario: Content exceeding token limit (chunk and average)
- **GIVEN** content exceeding `max_embedding_tokens` minus safety margin (default: 8191 - 100 = 8091)
- **WHEN** an embedding is generated
- **THEN** content SHALL be split into token-limited chunks using tiktoken
- **AND** each chunk SHALL be embedded via a single batch API call
- **AND** the resulting vectors SHALL be averaged element-wise
- **AND** the chunk count SHALL be logged

#### Scenario: Safety margin
- **GIVEN** the configured `max_embedding_tokens` limit
- **WHEN** chunking is performed
- **THEN** a safety margin of 100 tokens SHALL be subtracted from the limit

#### Scenario: Configurable token limit
- **GIVEN** a custom `max_embedding_tokens` value in config
- **WHEN** an embedding is generated
- **THEN** the configured limit SHALL be used instead of the default

#### Scenario: Unknown model fallback
- **GIVEN** an embedding model not recognized by tiktoken
- **WHEN** token counting is performed
- **THEN** it SHALL fall back to the `cl100k_base` encoding

#### Scenario: Keyword search unaffected by chunking
- **GIVEN** content that was chunked for embedding
- **WHEN** `mem.search(mode="keyword")` is used
- **THEN** it SHALL search the full stored content (not the chunked version)

## ADDED Requirements

### Requirement: Keyword Search Index

The mem database SHALL maintain an FTS5 external-content index (`memories_fts`) over `memories(topic, content)`, kept in sync by insert/update/delete triggers, with graceful degradation to LIKE matching when FTS5 is unavailable.

#### Scenario: Index kept in sync by triggers
- **WHEN** a memory is written, updated, appended to, rolled back, imported, restored, or deleted
- **THEN** the FTS5 index SHALL reflect the change without any explicit index maintenance call

#### Scenario: Existing database migration
- **GIVEN** an existing mem database created before this change
- **WHEN** a connection is established
- **THEN** the `memories_fts` table and its triggers SHALL be created
- **AND** the index SHALL be rebuilt once from existing rows so prior memories are immediately searchable
- **AND** the migration SHALL be idempotent (safe on every connection)

#### Scenario: FTS5 unavailable fallback
- **GIVEN** a SQLite build without FTS5 support
- **WHEN** `mem.search(mode="keyword")` is called
- **THEN** it SHALL fall back to the previous LIKE-based matching
- **AND** log a warning identifying the degraded mode
- **AND** all other mem operations SHALL work normally

### Requirement: Vector Search Index

When sqlite-vec is available, the mem database SHALL maintain a `vec0` virtual table (`memories_vec`) holding L2-normalised embedding vectors keyed by memory id, used for KNN semantic search. The `memories.embedding` BLOB SHALL remain the source of truth; the vec table is a derived index.

#### Scenario: Indexed semantic search
- **GIVEN** sqlite-vec is available and the vec index is populated
- **WHEN** `mem.search(mode="semantic")` or `mem.search(mode="hybrid")` is called
- **THEN** it SHALL retrieve candidates via a KNN query against `memories_vec` instead of a full-table scan
- **AND** the reported score SHALL equal the cosine similarity of the raw vectors (derived from the normalised L2 distance)
- **AND** when topic/category/tags filters are present, it SHALL over-fetch KNN candidates (at least 4x the limit) before filtering

#### Scenario: Dual-write on embedding storage
- **WHEN** any operation stores or replaces a memory's embedding (write, update, append, batch update, refresh, import, restore, reindex, or the background worker write-back)
- **THEN** the raw vector SHALL be written to `memories.embedding` as today
- **AND** the L2-normalised vector SHALL be upserted into `memories_vec` when its dimensions match config `dimensions`
- **AND** a dimension mismatch SHALL skip the vec upsert with a log entry (never truncate or corrupt the index)

#### Scenario: Vec rows removed with their memory
- **WHEN** a memory is deleted
- **THEN** its `memories_vec` row SHALL be removed automatically

#### Scenario: Backfill migration for existing embeddings
- **GIVEN** an existing database with stored embedding BLOBs and no vec index rows
- **WHEN** a connection is established with sqlite-vec available
- **THEN** missing vec rows SHALL be backfilled from the stored BLOBs (normalised)
- **AND** BLOBs whose dimensions mismatch config `dimensions` SHALL be skipped, with the skip count logged and a pointer to `mem.reindex(dry_run=False)`

#### Scenario: Configured dimensions change
- **GIVEN** an existing `memories_vec` table whose declared dimensions differ from config `dimensions`
- **WHEN** a connection is established
- **THEN** the vec table SHALL be dropped, recreated with the configured dimensions, and backfilled from matching BLOBs

#### Scenario: sqlite-vec unavailable fallback
- **GIVEN** sqlite-vec is not installed
- **WHEN** `mem.search(mode="semantic")` is called
- **THEN** it SHALL fall back to the cosine-similarity full-scan path with identical result semantics
- **AND** all other mem operations SHALL work normally

### Requirement: Memory History Listing

The `mem.history()` function SHALL list the stored versions of a single memory from `memory_history`.

#### Scenario: List versions
- **GIVEN** a memory that has been updated at least once
- **WHEN** `mem.history(topic="projects/rules")` is called
- **THEN** it SHALL list history entries newest-first, numbered v1..vN (v1 = most recent prior version)
- **AND** each entry SHALL show the version number, a history-id prefix, timestamp, content length, and a first-line preview
- **AND** the header SHALL show the current content's length and updated_at

#### Scenario: Resolution rules
- **GIVEN** a `topic` that matches zero or multiple memories
- **WHEN** `mem.history(topic=...)` is called
- **THEN** it SHALL return a "not found" or "multiple matches — use id=" error, matching `mem.update()` semantics
- **AND** `id=` SHALL override topic matching

#### Scenario: No history
- **GIVEN** a memory that has never been updated
- **WHEN** `mem.history()` is called for it
- **THEN** it SHALL return a message that no history exists for the memory

### Requirement: Memory Rollback

The `mem.rollback()` function SHALL restore a memory to a previous version from `memory_history`, applying the same invariants as a normal update.

#### Scenario: Rollback to most recent version
- **GIVEN** a memory with history
- **WHEN** `mem.rollback(topic="projects/rules")` is called (default `version=1`)
- **THEN** it SHALL replace the current content with the most recent prior version
- **AND** the pre-rollback content SHALL be saved to history first (rollback is undoable)
- **AND** redaction SHALL be re-applied to the restored content
- **AND** the embedding SHALL be regenerated (sync or async per config) and TOC sections recomputed, as in `mem.update()`

#### Scenario: Rollback to specific version
- **WHEN** `mem.rollback(id="abc-123", version=3)` is called
- **THEN** it SHALL restore the 3rd most recent prior version as listed by `mem.history()`

#### Scenario: Rollback by history id
- **WHEN** `mem.rollback(id="abc-123", history_id="d4e5f6a7")` is called with a full or unambiguous history-id prefix
- **THEN** it SHALL restore that exact history entry, overriding `version`
- **AND** an ambiguous or unknown prefix SHALL return an error

#### Scenario: Invalid version
- **GIVEN** a memory with N history entries
- **WHEN** `mem.rollback(version=N+1)` is called
- **THEN** it SHALL return an error naming the valid version range without modifying the memory

### Requirement: Search Index Status in Stats

The `mem.stats()` output SHALL report which search index paths are active.

#### Scenario: Index status lines
- **WHEN** `mem.stats()` is called
- **THEN** the output SHALL include the keyword index status (`fts5` or LIKE fallback)
- **AND** the vector index status (sqlite-vec with indexed row count, or scan fallback)
