# tool-mem Specification

## Purpose

Persistent memory for AI agents with SQLite storage and optional
OpenAI-compatible embeddings. Provides topic-based memory storage with semantic
search, content dedup, secret redaction, and importance decay. Embeddings are
opt-in via `embeddings_enabled` and use the independent top-level `embeddings`
route when enabled.
## Requirements
### Requirement: Memory Storage

The `mem.write()` function SHALL store memories with topic, content, and metadata.

#### Scenario: Basic write
- **GIVEN** a topic and content
- **WHEN** `mem.write(topic="projects/onetool/rules", content="Always use keyword-only args")` is called
- **THEN** it SHALL store the memory with a generated UUID
- **AND** it SHALL generate an embedding if `embeddings_enabled` is true (sync or async per `embeddings_async`)
- **AND** it SHALL store NULL embedding if `embeddings_enabled` is false
- **AND** it SHALL compute a SHA-256 content hash for dedup
- **AND** it SHALL store an empty `meta` JSON object by default

#### Scenario: Duplicate detection
- **GIVEN** a memory already exists with the same topic and content hash
- **WHEN** `mem.write()` is called with identical content for the same topic
- **THEN** it SHALL reject the write with a "Duplicate" message
- **AND** it SHALL return the existing memory ID

#### Scenario: Write from file
- **GIVEN** a file path
- **WHEN** `mem.write(topic="config", file="~/.onetool/onetool.yaml")` is called
- **THEN** it SHALL read content from the file
- **AND** store it as a memory
- **AND** auto-populate `source`, `source_mtime`, and `content_type` in meta

#### Scenario: Write with table of contents
- **GIVEN** markdown content with headings
- **WHEN** `mem.write(topic="spec", file="spec.md")` is called (toc defaults to True)
- **THEN** it SHALL parse headings (H1-H3 by default) and store a section index in `meta['sections']`
- **AND** store `section_count` in meta
- **AND** callers MAY pass `toc=False` to skip section indexing

#### Scenario: Relevance validation
- **GIVEN** a relevance value outside 1-10
- **WHEN** `mem.write(topic="test", content="text", relevance=0)` is called
- **THEN** it SHALL return an error indicating relevance must be between 1 and 10

#### Scenario: File size limit
- **GIVEN** a file larger than 1MB
- **WHEN** `mem.write(topic="test", file="large_file.bin")` is called
- **THEN** it SHALL reject the write with a "file too large" error

#### Scenario: Batch write from glob
- **GIVEN** a glob pattern
- **WHEN** `mem.write_batch(topic="docs", glob_pattern="docs/**/*.md")` is called
- **THEN** it SHALL create a memory per file using the `file=` write path
- **AND** preserve directory structure relative to the glob root as subtopic, including the file extension (e.g., `docs/sub/file.md` not `docs/sub/file`)
- **AND** auto-populate `source`, `source_mtime`, and `content_type` in meta for each file

#### Scenario: Batch write with toc
- **GIVEN** a glob pattern
- **WHEN** `mem.write_batch(topic="specs", glob_pattern="specs/**/*.md")` is called (toc defaults to True)
- **THEN** each file SHALL have its headings parsed and section index stored in meta
- **AND** callers MAY pass `toc=False` to skip section indexing

### Requirement: Memory Retrieval

The `mem.read()` function SHALL retrieve memories by topic or ID.

#### Scenario: Read by topic
- **GIVEN** a memory exists with the topic
- **WHEN** `mem.read(topic="projects/onetool/rules")` is called
- **THEN** it SHALL return the content (metadata included only when `meta=True`)
- **AND** increment the access count

#### Scenario: Read topic matching rules
- **GIVEN** a topic argument
- **WHEN** `mem.read(topic=...)` is called
- **THEN** a plain topic SHALL match exactly, a trailing `/` SHALL match the topic and everything under it, and `*` SHALL act as a wildcard
- **AND** when multiple memories match, the most recently created one SHALL be returned

#### Scenario: Read by ID
- **GIVEN** a memory ID
- **WHEN** `mem.read(id="abc-123")` is called
- **THEN** it SHALL return the memory regardless of topic

### Requirement: Batch Retrieval

The `mem.read_batch()` function SHALL retrieve full content for multiple memories.

#### Scenario: Read by topic prefix
- **GIVEN** memories exist under a topic prefix
- **WHEN** `mem.read_batch(topic="projects/onetool/agents/")` is called
- **THEN** it SHALL return full content for all matching memories
- **AND** increment access counts for each

#### Scenario: Read by IDs
- **GIVEN** a list of memory IDs
- **WHEN** `mem.read_batch(ids=["abc-123", "def-456"])` is called
- **THEN** it SHALL return full content for those specific memories

#### Scenario: IDs cannot combine with other filters
- **GIVEN** `ids` is provided alongside `topic`, `category`, or `tags`
- **WHEN** `mem.read_batch(ids=["abc"], category="rule")` is called
- **THEN** it SHALL return an error indicating ids cannot be combined with other filters

#### Scenario: Filter required
- **GIVEN** no filter parameters provided
- **WHEN** `mem.read_batch()` is called
- **THEN** it SHALL return an error requiring at least one filter

#### Scenario: Metadata headers
- **GIVEN** `meta=True`
- **WHEN** `mem.read_batch(topic="projects/", meta=True)` is called
- **THEN** each memory SHALL include a metadata header (topic, category, tags, etc.)

### Requirement: Read Modes

The `mem.read()` and `mem.read_batch()` functions SHALL support a `mode` parameter for different output formats.

#### Scenario: Content mode (default)
- **WHEN** `mem.read(topic="spec")` is called
- **THEN** it SHALL return the full content (same as before)

#### Scenario: TOC mode
- **WHEN** `mem.read(topic="spec", mode="toc")` is called
- **THEN** it SHALL return a numbered section index with line ranges

#### Scenario: Meta mode
- **WHEN** `mem.read(topic="spec", mode="meta")` is called
- **THEN** it SHALL return metadata only (topic, category, tags, relevance, meta map) without content

#### Scenario: All mode
- **WHEN** `mem.read(topic="spec", mode="all")` is called
- **THEN** it SHALL return metadata header, meta map, and full content

#### Scenario: read_batch mode
- **WHEN** `mem.read_batch(topic="specs/", mode="toc")` is called
- **THEN** it SHALL return toc for each matching memory

### Requirement: Table of Contents

The `mem.toc()` function SHALL display a numbered section index with staleness detection.

#### Scenario: Display TOC
- **GIVEN** a memory written with toc enabled (the default)
- **WHEN** `mem.toc(topic="spec")` is called
- **THEN** it SHALL return a numbered list of sections with line ranges

#### Scenario: Staleness warning
- **GIVEN** a memory with `source` and `source_mtime` in meta
- **WHEN** `mem.toc()` is called and the source file has been modified since storage
- **THEN** it SHALL append a staleness warning

#### Scenario: Source file deleted
- **GIVEN** a memory with `source` in meta pointing to a deleted file
- **WHEN** `mem.toc()` is called
- **THEN** it SHALL append a warning that the source file no longer exists

### Requirement: Section Extraction

The `mem.slice()` function SHALL extract content by section number, heading path, line range, or mixed list.

#### Scenario: Slice by section number
- **WHEN** `mem.slice(topic="spec", select=1)` is called
- **THEN** it SHALL return the content of the first section

#### Scenario: Slice by heading path
- **WHEN** `mem.slice(topic="spec", select="Requirements")` is called
- **THEN** it SHALL match section headings case-insensitively and return matching content

#### Scenario: Slice by line range
- **WHEN** `mem.slice(topic="spec", select=":50")` is called
- **THEN** it SHALL return the first 50 lines

#### Scenario: Slice by mixed list
- **WHEN** `mem.slice(topic="spec", select=[1, "Requirements", "200:300"])` is called
- **THEN** it SHALL apply the appropriate rule to each element and concatenate results

### Requirement: TOC Recomputation

When `mem.update()`, `mem.append()`, or `mem.update_batch()` modifies a memory that has `sections` in meta, it SHALL reparse headings and update the section index.

#### Scenario: Update with existing TOC
- **GIVEN** a memory with `sections` in meta
- **WHEN** `mem.update()` is called with new content
- **THEN** it SHALL recompute the section index from the new content

#### Scenario: Append with existing TOC
- **GIVEN** a memory with `sections` in meta
- **WHEN** `mem.append()` is called with new content
- **THEN** it SHALL recompute the section index from the combined content

#### Scenario: Batch update with existing TOC
- **GIVEN** a memory with `sections` in meta
- **WHEN** `mem.update_batch()` replaces content that changes line positions
- **THEN** it SHALL recompute the section index from the updated content

### Requirement: Schema Migration

The memories table SHALL include a `meta TEXT DEFAULT '{}'` column for extensible key-value metadata stored as JSON.

#### Scenario: New database
- **WHEN** a new database is created
- **THEN** the memories table SHALL include the `meta` column

#### Scenario: Existing database migration
- **GIVEN** an existing database without the `meta` column
- **WHEN** the connection is established
- **THEN** the `meta` column SHALL be added via ALTER TABLE

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

### Requirement: Memory Management

The `mem.update()`, `mem.append()`, and `mem.delete()` functions SHALL manage existing memories.

#### Scenario: Update single memory
- **GIVEN** a topic matching exactly one memory
- **WHEN** `mem.update(topic="projects/rules", content="new text")` is called
- **THEN** it SHALL update the content and re-generate the embedding (when embeddings are enabled)
- **AND** it SHALL store the old content in memory_history

#### Scenario: Update preserves embedding when embeddings disabled
- **GIVEN** `embeddings_enabled: false` and a memory with a stored embedding
- **WHEN** `mem.update()`, `mem.append()`, `mem.update_batch()`, or `mem.refresh()` modifies the memory
- **THEN** the stored embedding SHALL be preserved (not overwritten with NULL)

#### Scenario: Update rejects multiple matches
- **GIVEN** a topic matching multiple memories
- **WHEN** `mem.update()` is called
- **THEN** it SHALL return an error suggesting to use id= parameter

#### Scenario: Append content
- **GIVEN** an existing memory
- **WHEN** `mem.append(topic="rules", content="new rule")` is called
- **THEN** it SHALL append to existing content with separator
- **AND** store old content in history

#### Scenario: Delete by ID
- **GIVEN** a memory ID
- **WHEN** `mem.delete(id="abc-123")` is called
- **THEN** it SHALL delete the memory and its history

#### Scenario: Delete by topic requires confirm
- **GIVEN** a topic matching multiple memories
- **WHEN** `mem.delete(topic="projects/old/")` is called without confirm=True
- **THEN** it SHALL return a warning with the count
- **AND** require confirm=True to proceed

### Requirement: Secret Redaction

Content SHALL be automatically redacted before storage.

#### Scenario: API key redaction
- **GIVEN** content containing API keys (sk-..., ghp_..., AKIA...)
- **WHEN** stored via `mem.write()`
- **THEN** keys SHALL be replaced with [REDACTED:api_key] or similar

#### Scenario: Connection string redaction
- **GIVEN** content containing connection strings
- **WHEN** stored via `mem.write()`
- **THEN** credentials SHALL be redacted

#### Scenario: Redaction can be disabled
- **GIVEN** config `redaction_enabled: false`
- **WHEN** content is stored
- **THEN** no redaction SHALL be applied

### Requirement: Tag Validation

Tags SHALL be validated against a configurable whitelist.

#### Scenario: No whitelist allows all
- **GIVEN** empty tags_whitelist config
- **WHEN** any tags are provided
- **THEN** all tags SHALL be accepted

#### Scenario: Whitelist restricts tags
- **GIVEN** `tags_whitelist: ["project/*", "language"]`
- **WHEN** tag "forbidden" is provided
- **THEN** it SHALL raise a validation error

### Requirement: Context Loading

The `mem.context()` function SHALL load most-accessed memories.

#### Scenario: Hot cache
- **WHEN** `mem.context(topic="projects/onetool/", limit=5)` is called
- **THEN** it SHALL return the top-5 memories by access count
- **AND** increment their access counts

### Requirement: Batch Update

The `mem.update_batch()` function SHALL support search-and-replace.

#### Scenario: Dry run preview
- **WHEN** `mem.update_batch(search_text="old", replace_text="new", dry_run=True)` is called
- **THEN** it SHALL preview matching memories without modifying

#### Scenario: Apply changes
- **WHEN** `mem.update_batch(search_text="old", replace_text="new", dry_run=False)` is called
- **THEN** it SHALL update content, save history, re-generate embeddings, and recompute TOC if sections exist

### Requirement: Importance Decay

The `mem.decay()` function SHALL apply time-based importance decay.

#### Scenario: Decay formula
- **GIVEN** a memory with relevance, age, and access count
- **WHEN** decay is applied
- **THEN** new score = relevance * 0.5^(age/half_life) * (1 + log(access+1) * 0.1)
- **AND** result is clamped to range [1, original_relevance] (decay never increases relevance)

### Requirement: Dump and Import

The `mem.dump()` function SHALL output YAML. The `mem.load()` function SHALL import from YAML, always skipping duplicates.

#### Scenario: Dump to YAML
- **WHEN** `mem.dump()` is called
- **THEN** it SHALL output all memories in YAML format (emitted with a YAML library, not string templating)
- **AND** it SHALL include the `meta` column in the YAML output
- **AND** quotes and special characters in topics, tags, and content SHALL round-trip losslessly through `mem.load()`

#### Scenario: Dump to file
- **WHEN** `mem.dump(output="memories.yaml")` is called
- **THEN** it SHALL write YAML to the specified file

#### Scenario: Import from YAML
- **WHEN** `mem.load(file="backup.yaml")` is called
- **THEN** it SHALL import memories, skipping duplicates
- **AND** it SHALL restore the `meta` column from the YAML if present

#### Scenario: Import applies write invariants
- **WHEN** `mem.load()` imports entries
- **THEN** content SHALL be redacted with the same rules as `mem.write()`
- **AND** category and tags SHALL be validated; invalid entries are reported and skipped without aborting the import

### Requirement: Snapshot and Restore

The `mem.snapshot()` and `mem.restore()` functions SHALL provide lossless file-based round-trip of memories with full metadata preservation.

#### Scenario: Snapshot creates files and index
- **WHEN** `mem.snapshot(output="backup/consult", topic="consult/")` is called
- **THEN** it SHALL create one file per memory in the output directory
- **AND** it SHALL strip the topic filter prefix from file paths
- **AND** it SHALL write an `index.yaml` containing metadata (topic, file, category, tags, relevance, meta) for each memory

#### Scenario: Snapshot without topic filter
- **WHEN** `mem.snapshot(output="backup/all")` is called
- **THEN** it SHALL snapshot all memories
- **AND** use the full topic as the file path (no extension appended by default)

#### Scenario: Snapshot custom extension
- **WHEN** `mem.snapshot(output="backup/config", ext=".yaml")` is called
- **THEN** content files SHALL have the specified extension appended to the topic path
- **NOTE** `ext` defaults to `""` — the topic itself is the file path

#### Scenario: Snapshot skip existing
- **GIVEN** a file already exists at the output path
- **WHEN** `mem.snapshot(output="dir", on_conflict="skip")` is called
- **THEN** it SHALL skip writing that file but still include it in the index

#### Scenario: Snapshot overwrite existing
- **GIVEN** a file already exists at the output path
- **WHEN** `mem.snapshot(output="dir", on_conflict="overwrite")` is called
- **THEN** it SHALL overwrite the existing file

#### Scenario: Snapshot nested topics
- **GIVEN** memories with nested topic paths (e.g., `consult/sub/deep`)
- **WHEN** `mem.snapshot(output="dir", topic="consult/")` is called
- **THEN** it SHALL preserve the directory hierarchy (e.g., `sub/deep`)

#### Scenario: Restore from snapshot
- **WHEN** `mem.restore(input="backup/consult")` is called
- **THEN** it SHALL read `index.yaml` from the directory
- **AND** recreate each memory with its original topic, category, tags, relevance, and meta
- **AND** skip duplicates (same topic + content hash) by default

#### Scenario: Restore with overwrite
- **WHEN** `mem.restore(input="backup/consult", overwrite=True)` is called
- **THEN** it SHALL replace existing memories with same topic and content hash
- **AND** it SHALL delete the replaced memory's `memory_history` rows (no orphans)

#### Scenario: Path confinement
- **GIVEN** a topic or index `file` entry containing `..`, an absolute path, or other traversal
- **WHEN** `mem.snapshot()` writes content files or `mem.restore()` reads them
- **THEN** the entry SHALL be rejected and reported as an error
- **AND** every final resolved path SHALL be validated against `allowed_file_dirs` and `exclude_file_patterns`

#### Scenario: Restore applies write invariants
- **WHEN** `mem.restore()` recreates memories
- **THEN** content SHALL be redacted with the same rules as `mem.write()`
- **AND** category and tags SHALL be validated; invalid entries are reported and skipped without aborting the restore

#### Scenario: Restore topic override
- **WHEN** `mem.restore(input="backup/consult", topic="new-base")` is called
- **THEN** it SHALL remap topics by stripping the original filter prefix and prepending the new base topic

#### Scenario: Restore missing index
- **GIVEN** the input directory does not contain `index.yaml`
- **WHEN** `mem.restore(input="dir")` is called
- **THEN** it SHALL return an error about missing index.yaml

#### Scenario: Restore missing content file
- **GIVEN** a file referenced in index.yaml does not exist
- **WHEN** `mem.restore(input="dir")` is called
- **THEN** it SHALL report the error and continue with remaining files

#### Scenario: Round-trip lossless
- **GIVEN** memories with specific content, category, tags, and relevance
- **WHEN** `mem.snapshot()` followed by `mem.restore()` is performed
- **THEN** all metadata SHALL be preserved identically

### Requirement: Read Cache

Repeated reads of the same topic or ID SHALL be served from an in-memory cache to avoid redundant database queries.

#### Scenario: Cache hit
- **GIVEN** a memory was recently read
- **WHEN** `mem.read(topic=...)` is called again for the same topic
- **THEN** it SHALL return cached content without a database SELECT
- **AND** it SHALL still increment access_count in the database

#### Scenario: Cache invalidation on write
- **GIVEN** a cached memory
- **WHEN** `mem.write()`, `mem.update()`, `mem.append()`, or `mem.delete()` modifies that topic
- **THEN** the cache entry SHALL be invalidated

#### Scenario: Bulk invalidation
- **WHEN** `mem.update_batch()` or `mem.load()` completes
- **THEN** the entire cache SHALL be cleared

#### Scenario: Cache disabled
- **GIVEN** `read_cache_max_size: 0` in config
- **WHEN** `mem.read()` is called
- **THEN** every read SHALL query the database directly

#### Scenario: TTL expiry
- **GIVEN** a cached entry older than `read_cache_ttl_seconds`
- **WHEN** `mem.read()` is called
- **THEN** the stale entry SHALL be evicted and a fresh query executed

#### Scenario: LRU eviction
- **GIVEN** the cache is at `read_cache_max_size` capacity
- **WHEN** a new entry is cached
- **THEN** the oldest entry (by timestamp) SHALL be evicted

#### Scenario: Manual cache clear
- **WHEN** `mem.cache_clear()` is called
- **THEN** it SHALL clear all entries from the read cache
- **AND** return the number of evicted entries and remaining entries

#### Scenario: Manual cache clear by topic
- **WHEN** `mem.cache_clear(topic="proj")` is called
- **THEN** it SHALL clear only cache entries matching the topic prefix
- **AND** leave other entries intact

### Requirement: Optional Embeddings

Embeddings SHALL be opt-in and disabled by default. The mem pack SHALL load and
function without embedding credentials when embeddings are disabled. When enabled,
it SHALL use only the independent effective `embeddings` configuration and SHALL
NOT inherit a model, endpoint, credential, dimensions, batching, or token limit
from generation or pack-level provider configuration. Pack-level
`embeddings_enabled` and `embeddings_async` SHALL remain behavior controls only.

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

#### Scenario: Removed mem embedding provider fields are rejected
- **GIVEN** `tools.mem.model`, `tools.mem.base_url`, `tools.mem.dimensions`, or `tools.mem.max_embedding_tokens` is configured
- **WHEN** OneTool loads mem configuration
- **THEN** strict validation SHALL reject each removed field as an extra input
- **AND** OneTool SHALL NOT interpret it as an override or alias for top-level `embeddings`

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

### Requirement: Embedding Backfill

The `mem.embed()` function SHALL generate embeddings for memories that don't have them.

#### Scenario: Dry run preview
- **WHEN** `mem.embed(dry_run=True)` is called
- **THEN** it SHALL show the count of memories without embeddings

#### Scenario: Generate embeddings
- **WHEN** `mem.embed(dry_run=False)` is called
- **THEN** it SHALL generate embeddings for all un-embedded memories
- **AND** it SHALL commit per memory so a mid-run failure does not lose earlier progress
- **AND** on partial failure it SHALL report the generated and failed counts with the first error

#### Scenario: Topic-scoped backfill
- **WHEN** `mem.embed(topic="project/", dry_run=False)` is called
- **THEN** it SHALL only generate embeddings for memories matching the topic prefix

#### Scenario: Embeddings disabled
- **GIVEN** `embeddings_enabled: false`
- **WHEN** `mem.embed()` is called
- **THEN** it SHALL return a message about enabling embeddings first

### Requirement: Flush

The `mem.flush()` function SHALL wait for pending background embeddings to complete, bounded by a timeout.

#### Scenario: Flush queue
- **GIVEN** background embeddings are in progress
- **WHEN** `mem.flush()` is called
- **THEN** it SHALL block until the async queue is empty

#### Scenario: No pending work
- **GIVEN** no background worker is running
- **WHEN** `mem.flush()` is called
- **THEN** it SHALL return immediately

#### Scenario: Timeout
- **GIVEN** the queue does not drain within `timeout` seconds (default: 60)
- **WHEN** `mem.flush(timeout=...)` is called
- **THEN** it SHALL return an error reporting the timeout and pending job count instead of hanging

#### Scenario: Dead worker detected
- **GIVEN** the background worker thread has died while jobs are pending
- **WHEN** `mem.flush()` is called
- **THEN** it SHALL return an error indicating the worker is not running instead of waiting forever

### Requirement: Staleness Check

The `mem.stale()` function SHALL check which file-backed memories have outdated content relative to their source files.

#### Scenario: Bulk staleness check
- **WHEN** `mem.stale(topic="docs/")` is called
- **THEN** it SHALL query all memories under the topic prefix
- **AND** compare `meta.source_mtime` against the current file modification time for each
- **AND** return a summary with counts of fresh, stale, and missing memories

#### Scenario: Stale detection
- **WHEN** a memory's source file has been modified since storage
- **THEN** it SHALL be reported as stale with stored and current dates

#### Scenario: Missing source detection
- **WHEN** a memory's source file no longer exists
- **THEN** it SHALL be reported as missing

#### Scenario: Non-file-backed memories skipped
- **WHEN** a memory has no `source` or `source_mtime` in meta
- **THEN** it SHALL be skipped from staleness checking

#### Scenario: No file-backed memories
- **WHEN** no memories with source metadata are found
- **THEN** it SHALL return "No file-backed memories found"

### Requirement: Memory Listing Format

The `mem.list()` function SHALL display memories with parenthesised metadata. Parameters: `format` (`"list"` default, or `"tree"`), `depth` (int, default `0` = unlimited, only used with `format="tree"`).

#### Scenario: List output format
- **WHEN** `mem.list()` is called
- **THEN** each entry SHALL show topic followed by parenthesised metadata
- **AND** metadata SHALL always include id (first 8 chars), len, and category
- **AND** sec SHALL only appear when section_count > 0
- **AND** rel SHALL only appear when not the default value (5)
- **AND** tags SHALL be pipe-separated and only shown when non-empty
- **AND** access_count SHALL NOT appear in list output

#### Scenario: Tree format
- **WHEN** `mem.list(format="tree", topic="proj/docs/")` is called
- **THEN** it SHALL group topics by path components into a tree structure
- **AND** directory nodes SHALL show `(mem_count=N)` with total descendant count
- **AND** leaf nodes SHALL show the same parenthesised metadata as flat list format

#### Scenario: Tree depth limit
- **WHEN** `mem.list(format="tree", topic="proj/", depth=1)` is called
- **THEN** it SHALL show only the top-level groups without expanding children

#### Scenario: Tree unlimited depth
- **WHEN** `mem.list(format="tree", depth=0)` is called (default)
- **THEN** it SHALL expand the full tree hierarchy

### Requirement: Memory Refresh

The `mem.refresh()` function SHALL re-read source files for stale file-backed memories.

#### Scenario: Dry run (default)
- **WHEN** `mem.refresh(topic="docs/")` is called
- **THEN** it SHALL report stale files that would be updated without modifying the database

#### Scenario: Apply refresh
- **WHEN** `mem.refresh(topic="docs/", dry_run=False)` is called
- **THEN** it SHALL re-read each stale source file
- **AND** store old content in `memory_history`
- **AND** update content, content_hash, and updated_at
- **AND** update `meta.source_mtime` to current
- **AND** re-generate embedding if embeddings are enabled

#### Scenario: TOC recomputation on refresh
- **WHEN** a refreshed memory has `sections` in meta
- **THEN** it SHALL reparse headings and update the section index

#### Scenario: Missing source files skipped
- **WHEN** a memory's source file no longer exists during refresh
- **THEN** it SHALL skip the memory with a warning (not delete it)

#### Scenario: File size limit
- **WHEN** a source file exceeds 1MB during refresh
- **THEN** it SHALL skip the file with a warning

#### Scenario: Fresh memories unchanged
- **WHEN** a memory's source file has not been modified
- **THEN** it SHALL leave the memory untouched

### Requirement: Batch Slice

The `mem.slice_batch()` function SHALL extract sections from multiple memories in a single call. Each item in `items` is a dict with `topic` (str) or `id` (str), and `select` (int, str, or list). Max 20 items.

#### Scenario: Multiple topics with selectors
- **WHEN** `mem.slice_batch(items=[...])` is called with multiple topic/selector pairs
- **THEN** it SHALL return sliced content for each item separated by dividers
- **AND** include a topic header with selector label for each result

#### Scenario: Mixed selector types
- **WHEN** items contain int, str, and line-range selectors
- **THEN** each SHALL be resolved using the same logic as `mem.slice()`

#### Scenario: Per-item errors
- **WHEN** an item references a non-existent topic or unmatched selector
- **THEN** it SHALL include an error for that item without failing the entire batch

#### Scenario: Item limit
- **WHEN** more than 20 items are provided
- **THEN** it SHALL return an error

#### Scenario: Access count increment
- **WHEN** `mem.slice_batch()` fetches memories from the database
- **THEN** it SHALL increment `access_count` and update `last_accessed` for all fetched rows

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

### Requirement: Memory Inspect (mem.inspect)

The `mem.inspect()` function SHALL return structured metadata for a single memory.

#### Scenario: Inspect by topic
- **GIVEN** a topic matching exactly one memory
- **WHEN** `mem.inspect(topic="projects/onetool/rules")` is called
- **THEN** it SHALL return fields: id, topic, created_at, updated_at, size, toc entry count, category, tags

#### Scenario: Inspect by id
- **GIVEN** a valid memory id
- **WHEN** `mem.inspect(topic="...", id="abc-123")` is called
- **THEN** it SHALL return metadata for that specific memory

#### Scenario: Topic does not exist
- **GIVEN** a topic that does not exist
- **WHEN** `mem.inspect(topic="nonexistent")` is called
- **THEN** it SHALL raise with a clear "not found" error

### Requirement: JMESPath Query (mem.query)

The `mem.query()` function SHALL evaluate a JMESPath expression against a JSON or YAML memory.

#### Scenario: Query JSON memory
- **GIVEN** a memory whose content is valid JSON
- **WHEN** `mem.query(topic="config", expr="tools.mem.model")` is called
- **THEN** it SHALL parse the content as JSON and return the JMESPath result

#### Scenario: Query YAML memory
- **GIVEN** a memory whose content is valid YAML
- **WHEN** `mem.query(topic="config", expr="tools.mem.model")` is called
- **THEN** it SHALL parse the content as YAML and return the JMESPath result

#### Scenario: Query by id
- **GIVEN** a valid memory id
- **WHEN** `mem.query(topic="...", id="abc-123", expr="key")` is called
- **THEN** it SHALL evaluate the expression against that specific memory

#### Scenario: Non-JSON/YAML content
- **GIVEN** a memory whose content is neither valid JSON nor valid YAML
- **WHEN** `mem.query()` is called
- **THEN** it SHALL raise with a clear error indicating the content is not parseable

### Requirement: Regex Search

The `mem.grep()` function SHALL search memory content using regular expressions and return line-level results with context.

Parameters: `pattern` (str, required), `topic` (str|None), `category` (str|None), `tags` (list[str]|None), `context` (int, default 2), `case_sensitive` (bool, default True), `limit` (int, default 50 - max memories to search), `max_per_memory` (int, default 10 - max matches per memory), `fixed_strings` (bool, default False).

#### Scenario: Basic regex search
- **WHEN** `mem.grep(pattern="def \\w+\\(")` is called
- **THEN** it SHALL search all memory content for the regex pattern
- **AND** return matching lines grouped by topic with line numbers

#### Scenario: Fixed string search
- **WHEN** `mem.grep(pattern="foo.bar()", fixed_strings=True)` is called
- **THEN** it SHALL escape the pattern and match literally

#### Scenario: Case-insensitive search
- **WHEN** `mem.grep(pattern="error", case_sensitive=False)` is called
- **THEN** it SHALL match regardless of case

#### Scenario: Context lines
- **WHEN** `mem.grep(pattern="TODO", context=3)` is called
- **THEN** it SHALL include 3 lines before and after each match
- **AND** merge overlapping context ranges into single blocks

#### Scenario: Topic filtering
- **WHEN** `mem.grep(pattern="auth", topic="docs/")` is called
- **THEN** it SHALL only search memories under the topic prefix

#### Scenario: Category and tag filtering
- **WHEN** `mem.grep(pattern="config", category="rule", tags=["python"])` is called
- **THEN** it SHALL restrict search to memories matching category and tags

#### Scenario: SQL pre-filtering
- **GIVEN** a database with many memories
- **WHEN** `mem.grep()` is called
- **THEN** it SHALL use a `REGEXP` SQL function to pre-filter memories at the database level before performing line-level matching in Python

#### Scenario: Result limits
- **GIVEN** more than `limit` memories match
- **WHEN** `mem.grep(pattern="common", limit=10)` is called
- **THEN** it SHALL search at most 10 memories

#### Scenario: Per-memory match limit
- **GIVEN** a memory with many matches
- **WHEN** `mem.grep(pattern="the", max_per_memory=3)` is called
- **THEN** it SHALL return at most 3 match groups per memory

#### Scenario: Output format
- **WHEN** results are returned
- **THEN** each memory's results SHALL be grouped under a header showing topic and match count
- **AND** matching lines SHALL be marked with `>`
- **AND** context lines SHALL be shown without marker
- **AND** all lines SHALL include line numbers
- **AND** a `[slice: N-M]` hint SHALL indicate the line range for `slice_batch()` follow-up

#### Scenario: No matches
- **WHEN** no memories contain matching content
- **THEN** it SHALL return a message indicating no matches found

#### Scenario: Invalid regex
- **WHEN** an invalid regex pattern is provided
- **THEN** it SHALL return an error describing the regex issue

## Configuration

```yaml
tools:
  mem:
    db_path: data/mem/default.db  # relative to .onetool/
    search_limit: 10
    search_extract: 200
    read_cache_max_size: 128
    read_cache_ttl_seconds: 300
    redaction_enabled: true
    redaction_patterns: []
    tags_whitelist: []
    decay_half_life_days: 30
    allowed_file_dirs: []
    exclude_file_patterns: [".git", "node_modules", "__pycache__", ".venv", "venv"]
    embeddings_enabled: false
    embeddings_async: true
```

## Schema

```sql
CREATE TABLE memories (
    id             TEXT PRIMARY KEY,
    topic          TEXT NOT NULL,
    content        TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    category       TEXT DEFAULT 'note',
    tags           TEXT DEFAULT '[]',          -- JSON array
    relevance      INTEGER DEFAULT 5,
    access_count   INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    last_accessed  TEXT DEFAULT (datetime('now')),
    embedding      BLOB,                       -- packed float32 via struct
    meta           TEXT DEFAULT '{}'            -- JSON object
);

CREATE INDEX idx_memories_topic ON memories(topic);
CREATE INDEX idx_memories_content_hash ON memories(content_hash);

CREATE TABLE memory_history (
    id             TEXT PRIMARY KEY,
    memory_id      TEXT NOT NULL,
    content        TEXT NOT NULL,
    updated_at     TEXT DEFAULT (datetime('now'))
);
```

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

### Requirement: Embedding API retry on transient failures

Embedding API calls (synchronous and background-worker paths alike) SHALL retry on transient failures — HTTP 429, 500, or 503 — up to 3 attempts with exponential backoff before the error propagates. Non-retryable errors (e.g. HTTP 400, authentication failures) SHALL propagate without API-level retry. The background worker's existing job-level retry remains layered on top and its failure counter (`_embedding_errors`, surfaced in `mem.stats()`) SHALL still increment once per failed job.

#### Scenario: Sync write survives a transient 429
- **GIVEN** `embeddings_enabled: true` and `embeddings_async: false`
- **WHEN** the embeddings API returns HTTP 429 once and then succeeds
- **THEN** `mem.write()` SHALL succeed with the embedding stored, without surfacing an error

#### Scenario: Non-retryable error surfaces immediately
- **WHEN** the embeddings API returns a non-retryable error (e.g. invalid API key)
- **THEN** the error SHALL propagate without exhausting the retry budget

### Requirement: Query embedding cache for semantic search

Query embeddings generated for `mem.search()` semantic and hybrid modes SHALL be served from a bounded in-memory LRU cache keyed on a hash of the query text plus model and dimensions (never the raw text), with a 15-minute TTL. Document/content embeddings (write, update, reindex, worker) SHALL NOT use the cache.

#### Scenario: Repeated query embeds once
- **WHEN** the same query is searched twice within the TTL
- **THEN** the embeddings API SHALL be called at most once for the query vector

#### Scenario: Content writes bypass the cache
- **WHEN** `mem.write()` stores identical content twice with embeddings enabled
- **THEN** each write's embedding SHALL be generated by an API call, not served from the query cache

### Requirement: Canonical embedding vector serialization

All embedding vectors stored by the mem pack SHALL be serialized as explicit little-endian float32 (`struct` format `<{n}f`) via the shared otpack serialization helper, and the `cosine_similarity` SQLite function SHALL interpret blobs in the same encoding. Existing stores (already written little-endian) SHALL remain readable without migration; `mem.reindex(dry_run=False)` SHALL regenerate all vectors in canonical form.

#### Scenario: Stored vectors are little-endian
- **WHEN** any operation stores an embedding
- **THEN** the stored blob SHALL equal `struct.pack(f"<{n}f", *vector)`

#### Scenario: Pre-existing stores need no migration
- **WHEN** a database written before this change is searched semantically after upgrading
- **THEN** results SHALL be identical to before, with no reindex required
