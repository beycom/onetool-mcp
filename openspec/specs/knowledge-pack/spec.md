# Knowledge Pack Specification

## Purpose

Defines the `knowledge` pack (`kb` short alias), a retrieval-augmented knowledge base tool for querying, annotating, and managing offline knowledge bases backed by SQLite with FTS5 and vector search (sqlite-vec). Supports scraping sources, indexing markdown, hybrid search, AI-powered synthesis, and personal annotations.

---
## Requirements
### Requirement: Pack registration and short alias
The `knowledge` pack SHALL be registered in the tool loader and available under the metadata-declared short alias `kb`.

#### Scenario: Short alias resolves to pack
- **WHEN** a user calls `kb.search(...)` in the execution namespace
- **THEN** the call is routed to the `knowledge` pack's `search` tool

#### Scenario: Full pack name also works
- **WHEN** a user calls `knowledge.search(...)`
- **THEN** the call succeeds identically to `kb.search(...)`

---

### Requirement: Multi-database registry
The `knowledge` pack SHALL read named database configurations from `onetool.yaml` under `tools.knowledge.kb`. Each entry maps a short name to a `KBProjectConfig` containing at minimum a `db` sub-config. The `db.path` field is resolved relative to `.onetool/`.

#### Scenario: Named database resolves to file path
- **WHEN** a user calls `kb.search(q='...', db='rhino')`
- **THEN** the pack opens the path configured under `tools.knowledge.kb.rhino.db.path`

#### Scenario: Unregistered db name uses convention
- **WHEN** a user calls `kb.search(q='...', db='custom')` and `custom` is not in the registry
- **THEN** the pack opens `.onetool/mem/custom.db`

#### Scenario: dbs() lists configured databases
- **WHEN** a user calls `kb.dbs()`
- **THEN** the tool returns the list of database names and descriptions from `tools.knowledge.kb`

---

### Requirement: kb.write — Personal annotation
`kb.write()` SHALL add a single personal entry (category: `rule`, `note`, or `mistake`) to the target database.

#### Scenario: Personal note is stored
- **WHEN** `kb.write(topic='python/tips/loops', content='...', db='docs', category='rule')` is called
- **THEN** a new chunk is inserted with the given topic, content, and category

#### Scenario: Default category is 'note'
- **WHEN** `kb.write(topic='...', content='...', db='docs')` is called without `category`
- **THEN** the chunk is stored with `category='note'`

#### Scenario: Duplicate topic rejected atomically
- **WHEN** two writers race `kb.write()` with the same topic
- **THEN** at most one row is inserted — a partial UNIQUE index on `topic` (for rows with `source_path IS NULL`) backs the application-level check, and the losing writer receives the "already exists" error instead of an exception

---

### Requirement: kb.search — Hybrid retrieval
`kb.search()` SHALL retrieve chunks using a hybrid FTS5 BM25 + sqlite-vec KNN pipeline fused with RRF (k=60). The `mode` parameter SHALL select `hybrid` (default), `semantic` (vector-only), or `keyword` (FTS5-only). The search text parameter SHALL be named `query` (not `q`).

#### Scenario: Hybrid mode returns fused results
- **WHEN** `kb.search(query='nudge keys', db='docs', mode='hybrid', k=5)` is called
- **THEN** up to 5 chunks are returned ranked by RRF-fused BM25 and cosine scores

#### Scenario: Metadata filters narrow results
- **WHEN** `kb.search(query='...', db='docs', source='docs.example.test', k=10)` is called
- **THEN** only chunks whose `meta.source` starts with `'docs.example.test'` are returned

#### Scenario: category filter applies
- **WHEN** `kb.search(query='...', db='docs', category='rule')` is called
- **THEN** only chunks with `category='rule'` are returned

#### Scenario: Interaction boost applied
- **WHEN** a chunk has been returned by previous searches
- **THEN** its `hit_count` is incremented and its RRF score receives a small additive boost of `0.1 * min(hit_count, 10) / 10` (max +0.1)

#### Scenario: FTS query is preprocessed
- **WHEN** a keyword or hybrid search is issued
- **THEN** the query is stripped of FTS5 operator characters (`?`, `!`, `"`, `:`, `^`, `*`, `(`, `)`, `-`) and common English stopwords before the FTS5 MATCH is executed

#### Scenario: Prefix fallback on empty FTS result
- **WHEN** a keyword search returns no results after preprocessing
- **THEN** a second pass is attempted with each query term suffixed by `*` for prefix matching

#### Scenario: FTS uses Porter stemmer
- **WHEN** the `chunks_fts` virtual table is created
- **THEN** it uses `tokenize = 'porter unicode61'` so inflected word forms match their stems

#### Scenario: query parameter accepts the query= prefix match
- **WHEN** `kb.search(q='nudge keys', db='docs')` is called (using the short `q=` keyword instead of the full `query=`)
- **THEN** it SHALL succeed identically to `kb.search(query='nudge keys', db='docs')`, because `q` is a prefix of the `query` parameter name and is resolved by the run-tool's keyword-argument prefix matching

---

### Requirement: kb.ask — Retrieval-augmented synthesis
`kb.ask()` SHALL retrieve relevant chunks via `kb.search`, optionally re-rank them, optionally expand context with 1-hop graph neighbours, then synthesise an answer through the shared generation client with source citations. The question-text parameter SHALL be named `query` (not `q`).

#### Scenario: Answer is returned with citations
- **WHEN** `kb.ask(query='How do I nudge objects?', db='docs')` is called
- **THEN** a text answer is returned alongside a list of source citations (topic + url)

#### Scenario: Re-ranking is applied by default
- **WHEN** `kb.ask(query='...', db='docs', rerank=True)` is called
- **THEN** candidate chunks are re-ordered by relevance via a single batched LLM scoring call before synthesis

#### Scenario: Re-ranking failure preserves retrieval results
- **WHEN** the optional LLM re-ranking call fails
- **THEN** `kb.ask()` SHALL retain the original retrieval order
- **AND** it SHALL return a visible warning and continue through graph expansion and synthesis
- **AND** it SHALL NOT retry through another interface, backend, model, or credential

#### Scenario: Graph expansion adds neighbours
- **WHEN** `kb.ask(query='...', db='docs', expand=True)` is called
- **THEN** 1-hop outbound neighbours of top-k chunks are included as supplementary context (deduplicated)
- **AND** neighbours are retained even when retrieval already filled all `k` slots — expansion may grow the context beyond `k` (bounded at `2k`)

### Requirement: kb.grep — Regex content search
`kb.grep()` SHALL search entry content with a regex pattern, returning matching chunks with matched lines.

#### Scenario: Regex matches are returned
- **WHEN** `kb.grep(pattern='CPlane', db='docs')` is called
- **THEN** all chunks whose content matches the pattern are returned

---

### Requirement: kb.read — Entry retrieval
`kb.read()` SHALL return a list of chunks matching the given `topic` or `source_path`. A `topic` match may return multiple chunks (topic is not unique). An `id` match returns at most one chunk. `id=` (chunk UUID) overrides topic when provided.

`id=` is also supported on `kb.update()`, `kb.append()`, and `kb.delete()` as a stable alternative to topic — consistent with `mem` CRUD behaviour.

#### Scenario: Read by topic returns list
- **WHEN** `kb.read(topic='commands/move', db='rhino')` is called
- **THEN** all chunks with that topic are returned as a list (may be one or more)

#### Scenario: Read by id
- **WHEN** `kb.read(id='abc-123', db='docs')` is called
- **THEN** the chunk with that UUID is returned

#### Scenario: Read by source_path returns all anchors
- **WHEN** `kb.read(source_path='rhino/8mac/help/en-us/commands/move', db='rhino')` is called
- **THEN** all chunks (page-level and per-section) from that file are returned

#### Scenario: Missing topic returns empty list
- **WHEN** `kb.read(topic='nonexistent', db='rhino')` is called
- **THEN** an empty list is returned

#### Scenario: source_path filter in CRUD
- **WHEN** `kb.read(source_path='rhino/8mac/help/en-us/commands/move', db='rhino')` is called
- **THEN** all chunks with that `source_path` are returned (may span multiple anchors)

#### Scenario: topic, id, or source_path required
- **WHEN** `kb.read(db='docs')` is called without any parameter
- **THEN** an error is returned

---

### Requirement: kb.slice — Section extraction
`kb.slice()` SHALL extract a section from an entry's content by heading name or line range.

#### Scenario: Section by heading
- **WHEN** `kb.slice(topic='...', heading='Options', db='docs')` is called
- **THEN** the content from that heading to the next same-level heading is returned

---

### Requirement: kb.toc — Table of contents
`kb.toc()` SHALL return the heading structure of an entry.

#### Scenario: Headings listed
- **WHEN** `kb.toc(topic='...', db='docs')` is called
- **THEN** all headings with their levels are returned in order

---

### Requirement: kb.list — Entry listing
`kb.list()` SHALL list entries, optionally filtered by topic prefix, category, or tags.

#### Scenario: List all entries
- **WHEN** `kb.list(db='docs')` is called
- **THEN** a paginated list of all chunks is returned

#### Scenario: Filter by category
- **WHEN** `kb.list(db='docs', category='rule')` is called
- **THEN** only `rule` entries are returned

---

### Requirement: kb.info — DB metadata
`kb.info()` SHALL return the `_meta` reserved chunk and connection info (file path, chunk count, embedding coverage).

#### Scenario: Info returned for configured DB
- **WHEN** `kb.info(db='docs')` is called
- **THEN** author, description, version, chunk count, and embedding coverage are returned

---

### Requirement: kb.stats — Entry statistics
`kb.stats()` SHALL return entry counts broken down by category, embedding coverage percentage, total DB size, link graph summary, and most-accessed pages.

Parameters:
- `db` (required) — database name
- `top` (optional, default 5) — number of most-accessed pages to include

#### Scenario: Stats returned
- **WHEN** `kb.stats(db='docs')` is called
- **THEN** counts per category, embedding coverage, and DB file size are returned

#### Scenario: Link stats included
- **WHEN** `kb.stats(db='docs')` is called and the DB has edges
- **THEN** the total edge count and the top 5 most-linked pages (by in-degree) are included

#### Scenario: Most accessed pages included
- **WHEN** `kb.stats(db='docs')` is called and some chunks have been retrieved
- **THEN** the top `top` chunks by hit count are listed; if none have been accessed, a "none yet" message is shown

---

### Requirement: kb.append — Append to entry
`kb.append()` SHALL append content to an existing entry's `content` field.

#### Scenario: Content appended
- **WHEN** `kb.append(topic='python/tips/loops', content='\n- new note', db='docs')` is called
- **THEN** the entry's content has the new text appended and `updated_at` is refreshed

---

### Requirement: kb.update — Replace entry content
`kb.update()` SHALL replace the `content` of all chunks matching the given `topic`. For precision targeting, `source_path=` and `anchor=` parameters may be supplied.

#### Scenario: Content replaced
- **WHEN** `kb.update(topic='python/tips/loops', content='new content', db='docs')` is called
- **THEN** the entry's content is replaced and `updated_at` is refreshed

#### Scenario: Update by topic affects all matching chunks
- **WHEN** `kb.update(topic='commands/move', content='new content', db='rhino')` is called and two chunks have that topic
- **THEN** both chunks have their content replaced and `updated_at` refreshed

#### Scenario: Update by source_path and anchor targets one chunk
- **WHEN** `kb.update(source_path='rhino/8mac/help/en-us/commands/move', anchor='', db='rhino', content='new content')` is called
- **THEN** exactly the page-level preamble chunk for that file is updated

#### Scenario: Re-embed failure is surfaced, previous vector retained
- **WHEN** the re-embedding of updated content fails
- **THEN** the content update still succeeds, the previously stored vector is NOT deleted (embed-then-swap), and the return message carries an embedding-failure warning

---

### Requirement: kb.delete — Remove entry
`kb.delete()` SHALL remove all chunks matching the given `topic`, cascading to FTS5, `chunks_vec`, and `edges`. For precision targeting, `source_path=` and `anchor=` parameters may be supplied.

#### Scenario: Entry deleted
- **WHEN** `kb.delete(topic='python/tips/loops', db='docs')` is called
- **THEN** the chunk row and all related FTS5/vec/edge rows are removed

#### Scenario: Delete by topic removes all matching chunks
- **WHEN** `kb.delete(topic='commands/move', db='rhino')` is called and two chunks have that topic
- **THEN** both chunks and all related FTS5/vec/edge rows are removed

#### Scenario: Delete by source_path removes entire file's chunks
- **WHEN** `kb.delete(source_path='rhino/8mac/help/en-us/commands/move', db='rhino')` is called
- **THEN** all chunks (all anchors) from that source path are removed

---

### Requirement: kb.related — Link graph traversal
`kb.related()` SHALL return chunks connected by link edges to a given topic, supporting `in`, `out`, or `both` directions and depth 1–2.

#### Scenario: Outbound neighbours returned
- **WHEN** `kb.related(topic='guides/move', db='docs', direction='out', depth=1)` is called
- **THEN** chunks that `move` links to are returned with their `anchor_text`

#### Scenario: Inbound references returned
- **WHEN** `kb.related(topic='guides/move', db='docs', direction='in')` is called
- **THEN** chunks that link to `move` are returned

#### Scenario: Depth-2 traversal includes neighbours-of-neighbours
- **WHEN** `kb.related(topic='...', db='docs', direction='out', depth=2)` is called
- **THEN** direct and 2-hop neighbours are included (deduplicated)

---

### Requirement: kb.index — Stub chunk filtering
When indexing markdown files, the chunker SHALL skip or merge low-content chunks to avoid polluting semantic search results.

#### Scenario: Heading-only stubs are skipped
- **WHEN** a section heading has no body text (the next line is another heading)
- **THEN** the chunk is not stored or embedded

#### Scenario: Short chunks are merged into predecessor
- **WHEN** a section's non-heading body text is fewer than `min_chunk_chars` characters (default 200)
- **THEN** the chunk is merged into the preceding chunk rather than stored separately
- **AND** if there is no preceding chunk, the short chunk is skipped

#### Scenario: min_chunk_chars=0 disables merge
- **WHEN** `tools.knowledge.min_chunk_chars` is set to 0
- **THEN** short chunks are stored as-is (heading-only stubs are still skipped)

---

### Requirement: Resilient embedding phase
The `kb index` embedding phase SHALL be resilient to transient API failures.

#### Scenario: Retry on transient errors
- **WHEN** the OpenAI embeddings API returns HTTP 429, 500, or 503, or raises `ValueError` (e.g. empty response)
- **THEN** the call SHALL be retried up to 3 times with exponential backoff before giving up

#### Scenario: Empty / mismatched response guard
- **WHEN** the API returns fewer vectors than requested
- **THEN** a `ValueError` is raised immediately (triggering the retry path) rather than silently producing a count mismatch

#### Scenario: Per-batch commit on partial failure
- **WHEN** one sub-batch fails after exhausting retries
- **THEN** all previously successful sub-batches are already committed; only the failed sub-batch's chunks lack embeddings
- **AND** the overall error count reflects only the failed sub-batch, not the entire pending set

#### Scenario: Non-default dimensions are passed to the API
- **WHEN** `tools.knowledge.dimensions` differs from the embedding model's native output size
- **THEN** every `embeddings.create` call SHALL pass `dimensions=` so the returned vectors match the `vec0` table created from `config.dimensions`

#### Scenario: Same text embeds identically on every code path
- **WHEN** a text longer than the embedding token limit is embedded via the single path (`generate_embedding`) or the batch path
- **THEN** both paths SHALL embed the first token window only, producing the same vector for the same text

#### Scenario: reindex counts only newly generated embeddings
- **WHEN** `kb reindex` runs against a database where some chunks already have embeddings
- **THEN** the reported "Reindexed N" count SHALL include only embeddings added by this run, and the error count SHALL never be negative

---

### Requirement: Query embedding cache
Repeated query embeddings within a session SHALL be served from a short-lived in-memory cache. The cache SHALL be a bounded LRU and SHALL key on a hash of the text (never the full text), so long-running sessions do not retain document contents or grow without bound.

#### Scenario: Cache hit avoids API call
- **WHEN** `kb.search` or `kb.ask` issues the same query within 15 minutes
- **THEN** the embedding API is called only once; subsequent calls hit the cache

#### Scenario: Cache keyed on query + model + dimensions
- **WHEN** two queries differ in text, model, or dimensions
- **THEN** each generates a distinct API call

#### Scenario: Cache is bounded
- **WHEN** more distinct texts are embedded than the cache capacity
- **THEN** the least-recently-used entries are evicted and the cache never exceeds its cap

---

### Requirement: Config schema — tools.knowledge
The `onetool.yaml` `tools.knowledge` block SHALL support `kb` (map of project name
to `KBProjectConfig`), optional pack-level `model` and `effort` generation
overrides, `enrich_prompt`, `enrich_batch_size`, `enrich_min_chars`, `enrich_max_chars`,
`min_chunk_chars`, `search_limit`, and `search_extract`. Embedding provider, model,
endpoint, credentials, dimensions, batching, and token limits SHALL come from the
independent top-level `embeddings` configuration.

Enrichment keys:
- `enrich_prompt` (default `""`) — custom summarisation instruction for `kb enrich`; empty uses the built-in default
- `enrich_batch_size` (default 20, 1–500) — summaries per DB commit during `kb enrich`
- `enrich_min_chars` (default 400, ≥0) — chunks with shorter content are skipped by enrichment (0 disables skipping)
- `enrich_max_chars` (default 6000, ≥200) — content characters sent to the model per chunk

Each `KBProjectConfig` SHALL contain:
- `db`: `DBConfig` with `path`, `description`, `embeddings_enabled`
- `scrape` (optional): `ScrapeProjectConfig` with `output_base_dir`, crawl defaults, extraction options, default category/tags, and named `sources`
- `index` (optional): `IndexProjectConfig` with `ignore_patterns` (default `[]`) and `topic_roots` (default `[]`)

Each `ScrapeSourceConfig` source SHALL include `url` and MAY override project
defaults with `url_prefix`, `depth`, `max_pages`, `check_robots_txt`, delay,
user-agent, wait, timeout, iframe, filter, crawl strategy, score, selector,
JavaScript, image, flat-file, category, and tag settings.

`topic_roots` entries accept a full URL or bare path prefix. During indexing, the
first matching root is stripped from each chunk's canonical topic to derive the
stored topic.

Unknown fields in `tools.knowledge` and nested knowledge config models SHALL raise
validation errors. Provider connection fields SHALL not be accepted in the pack
configuration.

#### Scenario: KB project config resolves db path
- **WHEN** `tools.knowledge.kb.rhino.db.path: scratch/rhino-db/rhino.db` is configured
- **THEN** `kb.search(q='...', db='rhino')` opens that path

#### Scenario: KB project config resolves scrape sources
- **WHEN** `tools.knowledge.kb.rhino.scrape.sources` is configured
- **THEN** `kb scrape rhino` crawls the configured sources into `output_base_dir/source_name/`

#### Scenario: topic_roots applied during indexing
- **WHEN** `tools.knowledge.kb.rhino.index.topic_roots` contains a configured documentation URL prefix
- **THEN** chunks from that URL prefix are stored with the prefix stripped from their canonical topic

#### Scenario: ignore_patterns applied during indexing
- **WHEN** `tools.knowledge.kb.rhino.index.ignore_patterns` contains `*.tmp`
- **THEN** files matching `*.tmp` are skipped during `kb index rhino`

#### Scenario: Unified kb: project config
- **WHEN** `tools.knowledge.kb` is configured with a named project
- **THEN** each project entry SHALL accept:
  - `db:` (required) — `path` (required, resolved relative to `.onetool/`), `description`, `embeddings_enabled` (default `true`)
  - `scrape:` (optional) — scrape project config with `output_base_dir` (required, must be absolute), `depth` (default 3), `max_pages` (default 100), `check_robots_txt` (default true), `delay_min` (default 0.5), `delay_max` (default 2.0), `user_agent` (default `""`), `category` (optional, one of `reference`/`rule`/`note`/`mistake`, default null), `tags` (default `[]`), and `sources` (map of source name to source config)
  - `index:` (optional) — `ignore_patterns` (list of gitignore-style patterns, default `[]`), `topic_roots` (list of URL or path prefixes to strip from canonical topics, default `[]`)
- **AND** each source entry SHALL accept `url` (required), `url_prefix` (default `""`), optional overrides for `depth`, `max_pages`, `check_robots_txt`, `delay_min`, `delay_max`, `user_agent`, `category`, and `tags`
- **AND** the `source` column in `chunks` SHALL be populated on INSERT from `chunk.meta["source"]`
- **AND** the output directory for each source SHALL be derived as `output_base_dir / source_name`
- **AND** unknown fields in project or source configs SHALL raise a validation error

#### Scenario: Missing kb key returns empty list from kb.dbs()
- **WHEN** `tools.knowledge` has no `kb` key
- **THEN** `kb.dbs()` returns an empty list and not an error

#### Scenario: Unsupported pack fields raise validation error
- **WHEN** `tools.knowledge.databases`, `tools.knowledge.scrape`, `tools.knowledge.model`, `tools.knowledge.base_url`, `tools.knowledge.dimensions`, `tools.knowledge.max_embedding_tokens`, or `tools.knowledge.enrich_model` is set
- **THEN** a validation error SHALL identify the extra input

#### Scenario: Embeddings use independent configuration
- **WHEN** a knowledge project has `embeddings_enabled: true`
- **THEN** embedding operations SHALL use only the top-level `embeddings` route
- **AND** they SHALL NOT inherit from top-level `llm` or a knowledge generation selection

#### Scenario: Generation selections fall through by scope
- **WHEN** a knowledge call omits model or effort overrides
- **THEN** it SHALL fall through to `tools.knowledge.model` or `tools.knowledge.effort`, then top-level `llm`
- **AND** separate ask, rerank, and enrich generation routes SHALL not exist

#### Scenario: enrich_prompt overrides the built-in instruction
- **WHEN** `tools.knowledge.enrich_prompt` is set to a custom instruction
- **THEN** `kb enrich` uses it as the summarisation instruction while keeping the untrusted-context boundary in the system message

#### Scenario: Enrichment config keys are validated
- **WHEN** `tools.knowledge.enrich_batch_size: 0` or an unknown key such as `tools.knowledge.enrich_foo` is configured
- **THEN** config validation SHALL raise an error

### Requirement: Error handling — missing sqlite-vec
If `sqlite-vec` is not installed, all `knowledge` tools that require vector search SHALL raise a clear error with install instructions.

#### Scenario: ImportError with instructions
- **WHEN** `kb.search(mode='semantic', ...)` is called and `sqlite-vec` is not installed
- **THEN** an error is returned: `"sqlite-vec is required for vector search. Install with: pip install sqlite-vec"`

---

### Requirement: Scrape config — wait_for and page_timeout fields
`ScrapeSourceConfig` SHALL accept optional `wait_for` and `page_timeout` fields that override project defaults per source. `ScrapeProjectConfig` SHALL define project-level defaults for both.

#### Scenario: Per-source wait_for overrides project default
- **WHEN** a source has `wait_for: "css:.topic-body"` and the project has `wait_for: ""`
- **THEN** `resolve_source()` SHALL produce `ResolvedSourceConfig.wait_for = "css:.topic-body"`

#### Scenario: Source inherits project wait_for when not set
- **WHEN** a source has `wait_for: null` (not set) and the project has `wait_for: "css:.content"`
- **THEN** `resolve_source()` SHALL produce `ResolvedSourceConfig.wait_for = "css:.content"`

#### Scenario: per-source page_timeout overrides project default
- **WHEN** a source has `page_timeout: 60000` and the project has `page_timeout: 30000`
- **THEN** `resolve_source()` SHALL produce `ResolvedSourceConfig.page_timeout = 60000`

---

### Requirement: Scrape config — cache and process_iframes fields
`ScrapeProjectConfig` SHALL accept `cache` (default `False`) and `process_iframes` (default `False`) as project-level-only fields. These SHALL be copied directly to `ResolvedSourceConfig` with no per-source override.

#### Scenario: cache enables crawl4ai disk cache
- **WHEN** `cache: true` is set in a project config
- **THEN** the scraper SHALL use `CacheMode.ENABLED`, writing fetched pages to the crawl4ai cache directory

#### Scenario: process_iframes extracts iframe content
- **WHEN** `process_iframes: true` is set in a project config
- **THEN** the scraper SHALL pass `process_iframes=True` to `CrawlerRunConfig`, extracting text from embedded iframes

#### Scenario: Both fields default to False
- **WHEN** neither `cache` nor `process_iframes` is specified in the project config
- **THEN** `ResolvedSourceConfig.cache = False` and `ResolvedSourceConfig.process_iframes = False`

---

### Requirement: Sidecar enrichment — metadata written by scraper, read by chunker
`_write_page()` SHALL write `url`, `source`, and `crawled_at` to `.meta.yaml` on every page. When the crawl4ai result exposes `metadata`, `title`, `description`, and `keywords` SHALL also be written when non-empty. When `category` is non-null or `tags` is non-empty, they SHALL also be written. `depth` and `url_base_path` SHALL NOT be written to the sidecar — depth is an indexing-time concern computed from the canonical topic after `topic_roots` stripping.

`_load_sidecar()` SHALL read the following keys: `url`, `source`, `crawled_at`, `title`, `description`, `keywords`, `category`, `tags`. It SHALL silently ignore any `depth` or `url_base_path` keys that may exist in older sidecars.

In `chunk_file()`:
- Topic is always derived from `canonicalize(str(rel_path))` — the file's relative path within the indexed directory. Sidecar `url` is stored as metadata only, not used for topic derivation.
- Sidecar `keywords` SHALL pre-populate `chunk.tags` (deduplicating against frontmatter tags)
- Sidecar `tags` SHALL be merged into `chunk.tags` before keywords (deduplicating)
- Sidecar `category` SHALL override `chunk.category` (default `"reference"`)
- Sidecar `title` SHALL be stored in `chunk.meta`
- Depth tag (`depth:<N>`) and `chunk.meta["depth"]` are set by the indexer after `topic_roots` stripping, not by the chunker

#### Scenario: Sidecar does not contain depth or url_base_path
- **WHEN** `_write_page()` writes a page
- **THEN** the `.meta.yaml` sidecar SHALL NOT contain `depth` or `url_base_path`

#### Scenario: Topic derived from file path
- **WHEN** a `.md` file is indexed at relative path `app/v1/guide/en-us/commands/move.md`
- **THEN** `chunk_file()` SHALL produce chunks with `topic = "app/v1/guide/en-us/commands/move"` before topic_roots stripping

#### Scenario: Sidecar keywords become chunk tags
- **WHEN** a `.meta.yaml` sidecar contains `keywords: [move, translate]`
- **THEN** `chunk_file()` SHALL return chunks with `tags` containing `"move"` and `"translate"`

#### Scenario: Sidecar category applied to chunk
- **WHEN** a `.meta.yaml` sidecar contains `category: rule`
- **THEN** `chunk_file()` SHALL return chunks with `category == "rule"`

#### Scenario: Sidecar tags merged into chunk tags
- **WHEN** a `.meta.yaml` sidecar contains `tags: [config-tag]`
- **THEN** `chunk_file()` SHALL return chunks with `tags` containing `"config-tag"`

---

### Requirement: canonicalize() — canonical topic form
All topic derivation during indexing SHALL go through a `canonicalize(path, source_dir="")` function that converts a file path to a normalised slash-separated form with no extension.

Three source formats map to the same canonical form:
- Hierarchical path: `app/v1/guide/en-us/commands/move.md` → `app/v1/guide/en-us/commands/move`
- `::` flat file: `app::v1::guide::en-us::commands::move.md` → `app/v1/guide/en-us/commands/move`
- Either with `source_dir` prefix stripped: `canonicalize("app/v1/help/commands/move.md", "app/v1/help")` → `commands/move`

#### Scenario: Hierarchical path normalised
- **WHEN** `canonicalize("a/b/c.html")` is called
- **THEN** `"a/b/c"` is returned

#### Scenario: `::` flat file normalised
- **WHEN** `canonicalize("app::v1::commands::move.md")` is called
- **THEN** `"app/v1/commands/move"` is returned

#### Scenario: source_dir prefix stripped
- **WHEN** `canonicalize("app/v1/help/commands/move.md", source_dir="app/v1/help")` is called
- **THEN** `"commands/move"` is returned

#### Scenario: Flat and hierarchical produce same canonical form
- **WHEN** `canonicalize("guide::intro.md")` and `canonicalize("guide/intro.md")` are called
- **THEN** both return `"guide/intro"`

---

### Requirement: topic_roots — strip URL/path prefixes from canonical topics
During indexing, `topic_roots` entries in `IndexProjectConfig` SHALL be stripped from each chunk's canonical topic before storage. The first matching root wins. Roots may be full URLs or bare path prefixes; URL roots are canonicalised before matching. Depth tag and `meta["depth"]` are computed from the stripped topic.

#### Scenario: URL root stripped
- **WHEN** `topic_roots: ["https://docs.example.test/app/v1/guide/en-us/"]` is configured
- **AND** the canonical topic is `app/v1/guide/en-us/commands/move`
- **THEN** the stored topic SHALL be `commands/move`

#### Scenario: No match uses canonical form as-is
- **WHEN** no `topic_roots` entry matches the canonical topic
- **THEN** the canonical form is used unchanged

#### Scenario: depth tag computed from stripped topic
- **WHEN** a canonical topic `app/v1/guide/en-us/commands/move` is stripped to `commands/move`
- **THEN** `depth:2` tag and `meta["depth"] = 2` SHALL be set on the chunk

---

### Requirement: source_path and anchor deduplication
The `chunks` table SHALL deduplicate on `(source_path, anchor)` — not on `topic`. `source_path` is the canonical file path (same as canonical topic before `topic_roots` stripping). `anchor` is the heading slug within the file (`""` for page-level preamble). `topic` is a non-unique human-readable label with a plain (non-unique) index for indexed chunks; manual writes (`source_path IS NULL`) additionally get a partial UNIQUE index on `topic` to close the `kb.write()` check-then-insert race.

#### Scenario: Re-index unchanged chunk is skipped
- **WHEN** a chunk with the same `(source_path, anchor)` is re-indexed and content hash is unchanged
- **THEN** the chunk SHALL be skipped without updating the DB

#### Scenario: Duplicate (source_path, anchor) is an update, not an insert
- **WHEN** a chunk with the same `(source_path, anchor)` is indexed a second time
- **THEN** the existing row is updated (if content changed) or skipped (if unchanged) — no duplicate row is created

#### Scenario: New chunk inserted
- **WHEN** no row exists for a given `(source_path, anchor)` pair
- **THEN** a new chunk row with a generated UUID is inserted

#### Scenario: Same topic from two source files is allowed
- **WHEN** two files produce chunks with the same `topic` value but different `source_path`
- **THEN** both rows are stored without constraint violation

#### Scenario: topic index is non-unique for indexed chunks
- **WHEN** the `chunks` table is created
- **THEN** `idx_chunks_topic` SHALL be a plain index (not `UNIQUE`)
- **AND** `idx_chunks_topic_manual` SHALL be a partial `UNIQUE` index on `topic` restricted to rows `WHERE source_path IS NULL` (manual `kb.write()` entries)

---

### Requirement: Scrape output — hierarchical paths and flat-file option
`url_to_slug()` SHALL always produce hierarchical segment/segment output (no flat underscore slugs). The `flat_files` option in `ScrapeProjectConfig` and `ScrapeSourceConfig` controls output file naming only: when `false` (default), files are written in subdirectories; when `true`, files are written flat using `::` as separator.

`url_to_slug()` is used only for file naming. Topic derivation uses `canonicalize()` on the relative file path. Both hierarchical and `::` flat files produce the same canonical topic.

#### Scenario: url_to_slug produces hierarchical output
- **WHEN** `url_to_slug("https://docs.example.test/guide/intro.html")` is called
- **THEN** `"guide/intro"` is returned (not `"guide_intro"`)

#### Scenario: flat_files=True writes :: separator
- **WHEN** `_write_page(..., flat_files=True)` is called for a URL with path `/guide/intro`
- **THEN** the file is written to `output_dir/guide::intro.md` (no subdirectory)

#### Scenario: flat and hierarchical canonical topics are identical
- **WHEN** `canonicalize("guide::intro.md")` is called
- **THEN** it returns `"guide/intro"`, identical to `canonicalize("guide/intro.md")`

---

### Requirement: probe_source depth parameter
`probe_source()` SHALL accept a `depth: int` parameter (default 2) that is passed through to the underlying crawl strategy. The call site in `kb scrape --dry-run` SHALL pass `resolved.depth` from the source config.

#### Scenario: depth passed to probe
- **WHEN** `probe_source(url=..., depth=3, ...)` is called
- **THEN** the crawl strategy uses `max_depth=3`

#### Scenario: probe call site passes configured depth
- **WHEN** `kb scrape <project> --dry-run` is run
- **THEN** each source's probe SHALL use the configured depth (not a hardcoded default)

---

### Requirement: Run reports written after every scrape
After each source completes (run or resume), `run_scrape()` SHALL write `._run_report.json` to `output_dir`. The report SHALL always overwrite the previous file for that source.

#### Scenario: Run report written on completion
- **WHEN** `kb scrape <project>` completes a source
- **THEN** `output_dir/._run_report.json` SHALL contain `source_name`, `start_time`, `end_time`, `elapsed_s`, `resumed`, `written`, `failed`, `skipped`, `warnings`, `config_snapshot`, and `pages` (per-page records)

#### Scenario: Per-page record contains url, slug, status, content_len, elapsed_s, error
- **WHEN** a page is processed during scraping
- **THEN** its `PageRecord` entry SHALL have `status` of `"ok"`, `"empty"`, or `"failed"`; `content_len` of 0 for non-ok pages; and `error` populated only for failed pages

#### Scenario: Config threshold warnings in run report
- **WHEN** `max_pages > 500`, `depth > 4`, `url_prefix == ""`, or `delay_min < 0.5`
- **THEN** the `warnings` array in `._run_report.json` SHALL contain the corresponding warning string

#### Scenario: resumed flag set correctly
- **WHEN** `kb scrape <project> --resume` is run and `.state.json` existed at run start
- **THEN** `._run_report.json.resumed = true`

#### Scenario: Console prints report path after source
- **WHEN** a source scrape completes
- **THEN** the console SHALL print `  Report: <path>` on the line after the per-source count summary
- **AND** for a resumed run, the summary SHALL include `[resumed]`

#### Scenario: Run report overwrites on re-run
- **WHEN** `kb scrape` is run again on a source that already has `._run_report.json`
- **THEN** the old report SHALL be replaced with the new run's data

---

### Requirement: PruningContentFilter applied globally to scrape runs
All scrape runs (real and probe) SHALL use `DefaultMarkdownGenerator` with `PruningContentFilter(threshold=0.48, min_word_threshold=50)` to remove navigation chrome, sidebars, and breadcrumbs from extracted markdown.

#### Scenario: Content filter applied during real crawl
- **WHEN** a page is scraped with `kb scrape`
- **THEN** the written markdown SHALL have nav elements pruned by the content filter

#### Scenario: Content filter applied during probe
- **WHEN** `--dry-run` probes a source
- **THEN** the `content_preview` in probe report samples SHALL reflect filtered content, not raw markdown

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
- **THEN** the call SHALL return "No embeddings found for 'rhino'. Generate them with the CLI: onetool kb reindex rhino"
- **AND** SHALL NOT surface a raw SQL or `sqlite-vec` exception message
- **AND** SHALL NOT advertise `kb.reindex()`/`kb.index()` call syntax — those are CLI-only commands, not exported pack tools

#### Scenario: Keyword mode is unaffected
- **WHEN** `kb.search(q='...', db='rhino', mode='keyword')` is called
- **AND** the database has no embeddings
- **THEN** the call SHALL proceed with FTS5-only search and SHALL NOT check embeddings state

### Requirement: Untrusted-context boundary in kb.ask synthesis and re-ranking

The LLM calls backing `kb.ask()` SHALL send a system message that frames retrieved context as
untrusted, non-instructional reference material before sending the user's question and the retrieved
chunks. This applies to `_llm_rerank()` (candidate re-ranking) and `_synthesise()` (answer synthesis)
in `src/otutil/tools/_knowledge/retrieval.py`. This is independent of and in addition to the
`ottools/tool-llm` `transform()` boundary: `kb.ask()`'s re-ranking and synthesis calls build their own
prompts directly against an LLM client rather than going through `transform()`, so they need their own
system-message boundary.

Retrieved context can contain prompt-injection text (e.g. indexed documentation that itself contains
directive-like phrasing). Without a system-level boundary, the request sends the user question and
retrieved context in a single `user` message with no instruction to disregard embedded directives.

#### Scenario: Synthesis sends a system message
- **GIVEN** `kb.ask(q='...', db='docs')` triggers `_synthesise()`
- **WHEN** the LLM request is built
- **THEN** the request's `messages` list SHALL include a `system` role message
- **AND** that system message SHALL instruct the model to treat the retrieved context as untrusted
  data, not instructions
- **AND** that system message SHALL instruct the model to ignore any instructions embedded within the
  retrieved context that attempt to change its behavior, reveal secrets, call tools, fetch URLs,
  execute code, or disregard these rules

#### Scenario: Re-ranking sends a system message
- **GIVEN** `kb.ask(q='...', db='docs', rerank=True)` triggers `_llm_rerank()`
- **WHEN** the LLM scoring request is built
- **THEN** the request's `messages` list SHALL include a `system` role message with the same
  untrusted-context framing as synthesis

#### Scenario: Existing citation behavior is unchanged
- **GIVEN** `kb.ask(q='How do I nudge objects?', db='docs')` is called
- **WHEN** the answer is returned
- **THEN** a text answer is still returned alongside a list of source citations (topic + url), exactly
  as before this change — the system message is additive and does not alter the response contract

---

### Requirement: Search lane failures surface instead of silently degrading

Failures in the FTS or vector search lanes SHALL be logged and surfaced rather than swallowed into empty result lists. Hybrid search MUST NOT silently become FTS-only.

#### Scenario: Corrupt or missing vector table surfaces an error
- **WHEN** the `chunks_vec` query fails (missing table, corruption, or dimension mismatch)
- **THEN** `search_vec` SHALL log the failure and raise, so `kb.search(mode='hybrid'|'semantic')` returns an error message instead of silently returning FTS-only or empty results

#### Scenario: Corrupt FTS table surfaces an error
- **WHEN** the `chunks_fts` query fails for a reason other than FTS5 query syntax
- **THEN** the failure SHALL be logged and raised; only benign FTS5 query-syntax errors may return an empty row set (logged)

#### Scenario: kb.ask degrades loudly
- **WHEN** hybrid retrieval fails inside `kb.ask` and the keyword lane still works
- **THEN** the answer SHALL be prefixed with a visible warning that retrieval was keyword-only, and the failure SHALL be logged

### Requirement: AI enrichment — kb enrich summary generation

The CLI command `onetool kb enrich <db>` SHALL generate short document summaries
through the shared generation client and write them to `chunks.summary`.
Enrichment SHALL be CLI-only (no `kb.enrich()` pack tool, matching `kb index` /
`kb reindex`) and SHALL never run implicitly from pack tool calls.

Selection semantics (making every run a backfill):
- Default: only chunks with `summary IS NULL OR summary = ''`, excluding the reserved `_meta` topic.
- `--force`: all chunks, regenerating existing summaries.
- `--limit N`: cap the number of chunks processed in this run.

Generation resolution SHALL use call-level `--model` and `--effort` overrides,
then `tools.knowledge.model` and `tools.knowledge.effort`, then top-level `llm`.
The request SHALL use the configured generation backend, interface, and named
secret. Enrichment SHALL NOT read from or fall back to the independent embedding
route.

Each summarisation request SHALL include a system message combining the untrusted-context boundary (as used by `kb.ask` rerank/synthesis) with the summarisation instruction, so indexed content cannot inject instructions. The instruction SHALL be overridable via `tools.knowledge.enrich_prompt` (empty = built-in default: 1–2 plain sentences, ~50 words max, no markdown).

#### Scenario: Backfill run populates missing summaries
- **WHEN** `onetool kb enrich docs` is run against a database where some chunks have no summary
- **THEN** each selected chunk receives a non-empty LLM-generated `summary`
- **AND** chunks that already have a non-empty summary are not re-processed
- **AND** the command reports counts: enriched, skipped (short), failed

#### Scenario: Limit caps a run
- **WHEN** `onetool kb enrich docs --limit 50` is run against a database with 200 unsummarised chunks
- **THEN** at most 50 chunks are enriched and the remaining 150 stay eligible for the next run

#### Scenario: Force regenerates existing summaries
- **WHEN** `onetool kb enrich docs --force` is run
- **THEN** all chunks (including those with existing summaries and those previously marked skipped) are re-summarised

#### Scenario: Short chunks are skipped, durably
- **WHEN** a selected chunk's content is shorter than `tools.knowledge.enrich_min_chars` (default 400; 0 disables)
- **THEN** no LLM call is made for it, `summary` is set to `''` (deliberately-not-summarised marker), and it is counted as skipped
- **AND** subsequent non-force runs do not reselect it

#### Scenario: Missing generation secret fails loudly
- **WHEN** `onetool kb enrich docs` is run without the configured generation secret
- **THEN** the command reports an actionable error naming the missing secret, and no chunk is modified

#### Scenario: Generation selection follows operation precedence
- **WHEN** no call-level model or effort is supplied
- **THEN** enrichment resolves `tools.knowledge.model` and `tools.knowledge.effort`, then top-level `llm`

#### Scenario: CLI generation overrides
- **WHEN** `onetool kb enrich docs --model sol --effort high` is run
- **THEN** enrichment passes the opaque model ID `sol` unchanged and requests high effort for that invocation

#### Scenario: System message carries the untrusted-context boundary
- **WHEN** an enrichment LLM request is built
- **THEN** its generation request includes system instructions that treat the chunk content as untrusted data, not instructions

---

### Requirement: AI enrichment — batching, failure handling, and durability

Enrichment SHALL make one generation call per chunk (no multi-chunk batch
parsing) with the chunk's content truncated to
`tools.knowledge.enrich_max_chars` characters (default 6000). Progress SHALL be
committed every `tools.knowledge.enrich_batch_size` summaries (default 20) so an
interrupted run keeps completed work.

Failure policy:
- Transient HTTP 429/500/503 responses SHALL be retried up to 3 attempts with exponential backoff.
- A chunk whose call fails after retries (or returns an empty/whitespace response) SHALL be recorded as failed with its id and error, leaving its `summary` unchanged (`NULL`), and the run continues.
- After 5 consecutive chunk failures the run SHALL abort (API outage, not a content problem), reporting how many chunks were left unprocessed.

#### Scenario: Per-batch commit preserves progress
- **WHEN** an enrich run fails partway through
- **THEN** all summaries committed in completed batches remain in the database
- **AND** re-running `kb enrich` resumes with only the unprocessed chunks (their `summary` is still `NULL`)

#### Scenario: Single bad chunk does not stop the run
- **WHEN** one chunk's LLM call fails after retries
- **THEN** the run continues with the next chunk and the final report includes the failed chunk's id and error

#### Scenario: Consecutive failures abort the run
- **WHEN** 5 chunks in a row fail
- **THEN** the run stops, already-committed summaries are kept, and the report states how many chunks were not processed

#### Scenario: Empty LLM response is a failure, not a skip
- **WHEN** the model returns an empty or whitespace-only summary for a chunk
- **THEN** the chunk is counted as failed and its `summary` remains `NULL` (it is retried on the next run)

#### Scenario: Long content is truncated in the prompt
- **WHEN** a chunk's content exceeds `enrich_max_chars`
- **THEN** only the first `enrich_max_chars` characters are sent to the model, and the full stored content is unmodified

---

### Requirement: Index-time enrichment opt-in

`onetool kb index <project>` SHALL accept an `--enrich` flag. When set, after the embedding and link-graph phases complete, enrichment SHALL run over exactly the chunks inserted or updated by that index run (not the whole database). Without the flag, indexing SHALL NOT make any enrichment LLM calls (current behaviour preserved).

#### Scenario: --enrich summarises only this run's chunks
- **WHEN** `onetool kb index docs --enrich` indexes 10 new/changed chunks into a database that also contains 90 older unsummarised chunks
- **THEN** enrichment runs for the 10 chunks from this run only

#### Scenario: Default index run makes no LLM enrichment calls
- **WHEN** `onetool kb index docs` is run without `--enrich`
- **THEN** no chat-completion calls are made and `summary` values are untouched

---

### Requirement: Summary invalidation on content change

Whenever a chunk's `content` is rewritten, its `summary` SHALL be cleared to `NULL` in the same statement, so stale summaries never describe old content and the chunk becomes eligible for the next enrich run. This applies to the indexer's update path (changed file re-indexed with `overwrite='update'`), `kb.update()`, and `kb.append()`. New chunks (`kb.write()`, indexer inserts) start with `summary = NULL`.

#### Scenario: Re-index of changed file clears summary
- **WHEN** a chunk with an existing summary is re-indexed with changed content
- **THEN** its `summary` becomes `NULL` and the FTS index no longer matches the old summary text

#### Scenario: kb.update clears summary
- **WHEN** `kb.update(topic='...', content='new content', db='docs')` replaces the content of a summarised chunk
- **THEN** the chunk's `summary` is `NULL` after the update

#### Scenario: kb.append clears summary
- **WHEN** `kb.append(topic='...', content='...', db='docs')` extends a summarised chunk
- **THEN** the chunk's `summary` is `NULL` after the append

#### Scenario: Enrichment does not bump updated_at
- **WHEN** `kb enrich` writes a summary to a chunk
- **THEN** the chunk's `updated_at` timestamp is unchanged (enrichment is derived metadata, not a content edit)

---

### Requirement: Summaries participate in search

Populated summaries SHALL be searchable and visible:
- FTS lane: the `chunks_fts` table indexes `summary` (existing schema/triggers), so `keyword` and `hybrid` searches SHALL match chunks by summary terms once summaries are written.
- Result display: `kb.search()` result lines SHALL show the chunk's summary when it is non-empty, in place of the truncated content extract; chunks without a summary keep the current extract behaviour.
- The vector lane is unchanged: summaries are not embedded and existing embeddings are not invalidated by enrichment.
- `kb.ask()` synthesis continues to use raw chunk content (summaries are lossy).
- `kb.stats()` AI-enrichment coverage (existing output) SHALL reflect enriched counts.

#### Scenario: FTS matches summary-only terms
- **WHEN** a chunk's summary contains a term that appears nowhere in its content, and `kb.search(query=<that term>, db='docs', mode='keyword')` is called
- **THEN** the chunk is returned

#### Scenario: Search results display the summary
- **WHEN** `kb.search(query='...', db='docs')` returns a chunk with a non-empty summary
- **THEN** the result line shows the summary text instead of the raw content extract

#### Scenario: Unsummarised chunks keep extract display
- **WHEN** a returned chunk has `summary` NULL or `''`
- **THEN** the result line shows the truncated content extract exactly as before this change

#### Scenario: Enrichment does not touch vectors
- **WHEN** `kb enrich` completes over a database with full embedding coverage
- **THEN** `chunks_vec` row count and contents are unchanged

#### Scenario: Stats reflects enrichment coverage
- **WHEN** `kb.stats(db='docs')` is called after enriching 40 of 100 chunks
- **THEN** the AI-enrichments line reports summaries 40/100 (40%)

### Requirement: Canonical embedding vector serialization

All embedding vectors written by the knowledge pack (chunk vectors in the `vec0`
table and query vectors passed to sqlite-vec) SHALL be serialized as explicit
little-endian float32 (`struct` format `<{n}f`).

Existing databases indexed by earlier versions on little-endian platforms SHALL remain readable without reindexing, because native and little-endian float32 encodings are byte-identical there. For a database written on a big-endian host (unsupported), `kb reindex` SHALL regenerate all vectors in canonical form.

#### Scenario: Stored vectors are little-endian
- **WHEN** a chunk embedding is written during `kb index`, `kb.add`, or `kb.update`
- **THEN** the stored blob SHALL equal `struct.pack(f"<{n}f", *vector)`

#### Scenario: Pre-existing little-endian stores need no migration
- **WHEN** a database indexed before this change (on a little-endian platform) is searched after upgrading
- **THEN** semantic search SHALL return correct results without any reindex step

#### Scenario: Reindex regenerates canonical vectors
- **WHEN** `kb reindex` runs against any database
- **THEN** all regenerated vectors SHALL be stored in the canonical little-endian encoding

### Requirement: Knowledge generation routing and controls

Knowledge enrichment, reranking, and answer synthesis SHALL use the shared
generation client and the same pack-level generation selection. Network-backed knowledge operations SHALL accept
optional model and effort overrides at their public call boundary where the caller
controls generation.

#### Scenario: Ask uses one pack selection
- **WHEN** `kb.ask()` performs reranking and synthesis
- **THEN** both stages SHALL resolve call overrides, then `tools.knowledge.model` and `tools.knowledge.effort`, then top-level `llm`

#### Scenario: Ask model and effort override
- **WHEN** `kb.ask()` is called with `model="sol"` and `effort="high"`
- **THEN** both reranking and synthesis SHALL resolve `sol` and request high effort
- **AND** those per-call values SHALL override the pack selection for that call

#### Scenario: Enrichment uses the configured generation route
- **WHEN** `kb enrich` generates a summary
- **THEN** it SHALL use the configured backend, interface, and named credential

#### Scenario: Embedding route is not reused for generation
- **WHEN** embeddings and knowledge generation are both configured
- **THEN** reranking, synthesis, and enrichment SHALL NOT use the embedding endpoint or credential
