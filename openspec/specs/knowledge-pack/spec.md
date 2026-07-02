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

---

### Requirement: kb.search — Hybrid retrieval
`kb.search()` SHALL retrieve chunks using a hybrid FTS5 BM25 + sqlite-vec KNN pipeline fused with RRF (k=60). The `mode` parameter SHALL select `hybrid` (default), `semantic` (vector-only), or `keyword` (FTS5-only).

#### Scenario: Hybrid mode returns fused results
- **WHEN** `kb.search(q='nudge keys', db='docs', mode='hybrid', k=5)` is called
- **THEN** up to 5 chunks are returned ranked by RRF-fused BM25 and cosine scores

#### Scenario: Metadata filters narrow results
- **WHEN** `kb.search(q='...', db='docs', source='docs.example.test', k=10)` is called
- **THEN** only chunks whose `meta.source` starts with `'docs.example.test'` are returned

#### Scenario: category filter applies
- **WHEN** `kb.search(q='...', db='docs', category='rule')` is called
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

---

### Requirement: kb.ask — Retrieval-augmented synthesis
`kb.ask()` SHALL retrieve relevant chunks via `kb.search`, optionally re-rank them, optionally expand context with 1-hop graph neighbours, then synthesise an answer via `ot_llm` with source citations.

#### Scenario: Answer is returned with citations
- **WHEN** `kb.ask(q='How do I nudge objects?', db='docs')` is called
- **THEN** a text answer is returned alongside a list of source citations (topic + url)

#### Scenario: Re-ranking is applied by default
- **WHEN** `kb.ask(q='...', db='docs', rerank=True)` is called
- **THEN** candidate chunks are re-ordered by relevance via a single batched LLM scoring call before synthesis

#### Scenario: Graph expansion adds neighbours
- **WHEN** `kb.ask(q='...', db='docs', expand=True)` is called
- **THEN** 1-hop outbound neighbours of top-k chunks are included as supplementary context (deduplicated)

---

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

---

### Requirement: Query embedding cache
Repeated query embeddings within a session SHALL be served from a short-lived in-memory cache.

#### Scenario: Cache hit avoids API call
- **WHEN** `kb.search` or `kb.ask` issues the same query within 15 minutes
- **THEN** the embedding API is called only once; subsequent calls hit the cache

#### Scenario: Cache keyed on query + model + dimensions
- **WHEN** two queries differ in text, model, or dimensions
- **THEN** each generates a distinct API call

---

### Requirement: Config schema — tools.knowledge
The `onetool.yaml` `tools.knowledge` block SHALL support: `kb` (map of project name → `KBProjectConfig`), `model` (embedding model), `base_url`, `enrich_model`, `enrich_prompt`, `min_chunk_chars`, `dimensions`, `search_limit`, `search_extract`.

Each `KBProjectConfig` SHALL contain:
- `db`: `DBConfig` with `path`, `description`, `embeddings_enabled`
- `scrape` (optional): `ScrapeProjectConfig` with `output_base_dir`, crawl defaults, extraction options, default category/tags, and named `sources`
- `index` (optional): `IndexProjectConfig` with `ignore_patterns` (default `[]`) and `topic_roots` (default `[]`)

Each `ScrapeSourceConfig` source SHALL include `url` and MAY override project
defaults with `url_prefix`, `depth`, `max_pages`, `check_robots_txt`, delay,
user-agent, wait, timeout, iframe, filter, crawl strategy, score, selector,
JavaScript, image, flat-file, category, and tag settings.

`topic_roots` entries accept a full URL or bare path prefix. During indexing, the first matching root is stripped from each chunk's canonical topic to derive the stored topic.

Unknown fields in `tools.knowledge` and nested knowledge config models SHALL raise validation errors. Removed top-level keys such as `databases:` and `scrape:` SHALL be treated as unknown fields, with no compatibility migration path.

#### Scenario: KB project config resolves db path
- **WHEN** `tools.knowledge.kb.rhino.db.path: scratch/rhino-db/rhino.db` is configured
- **THEN** `kb.search(q='...', db='rhino')` opens that path

#### Scenario: KB project config resolves scrape sources
- **WHEN** `tools.knowledge.kb.rhino.scrape.sources` is configured
- **THEN** `kb scrape rhino` crawls the configured sources into `output_base_dir/source_name/`

#### Scenario: topic_roots applied during indexing
- **WHEN** `tools.knowledge.kb.rhino.index.topic_roots` contains `https://docs.mcneel.com/rhino/8mac/help/en-us/`
- **THEN** chunks from that URL prefix are stored with the prefix stripped from their canonical topic

#### Scenario: ignore_patterns applied during indexing
- **WHEN** `tools.knowledge.kb.rhino.index.ignore_patterns` contains `*.tmp`
- **THEN** files matching `*.tmp` are skipped during `kb index rhino`

#### Scenario: Unified kb: project config
- **WHEN** `tools.knowledge.kb` is configured with a named project
- **THEN** each project entry SHALL accept:
  - `db:` (required) — `path` (required, resolved relative to `.onetool/`), `description`, `embeddings_enabled` (default `true`)
  - `scrape:` (optional) — scrape project config with `output_base_dir` (required, must be absolute), `depth` (default 3), `max_pages` (default 100), `check_robots_txt` (default true), `delay_min` (default 0.5), `delay_max` (default 2.0), `user_agent` (default ""), `category` (optional, one of `reference`/`rule`/`note`/`mistake`, default null), `tags` (default `[]`), and `sources` (map of source name → source config)
  - `index:` (optional) — `ignore_patterns` (list of gitignore-style patterns, default `[]`), `topic_roots` (list of URL or path prefixes to strip from canonical topics, default `[]`)
- **AND** each source entry SHALL accept: `url` (required), `url_prefix` (default ""), optional overrides for `depth`, `max_pages`, `check_robots_txt`, `delay_min`, `delay_max`, `user_agent` (all default to `null` = inherit from project), optional `category` (null = inherit from project) and `tags` (null = inherit from project; source tags are merged with project tags, deduplicating)
- **AND** the `source` column in `chunks` SHALL be populated on INSERT from `chunk.meta["source"]` (set by the sidecar loader)
- **AND** the output directory for each source SHALL be derived as `output_base_dir / source_name`
- **AND** unknown fields in project or source configs SHALL raise a validation error

#### Scenario: Missing kb key returns empty list from kb.dbs()
- **WHEN** `tools.knowledge` has no `kb` key
- **THEN** `kb.dbs()` returns an empty list (not an error)

#### Scenario: Removed databases/scrape keys raise validation error
- **WHEN** `tools.knowledge.databases` or `tools.knowledge.scrape` is set at the top level
- **THEN** a validation error is raised for extra inputs

#### Scenario: model and base_url fall back to top-level llm config
- **WHEN** `tools.knowledge.model` is not set
- **THEN** the embedding model is inherited from `llm.embedding_model` in the top-level `llm:` config block
- **WHEN** `tools.knowledge.base_url` is not set
- **THEN** the API base URL is inherited from `llm.base_url` in the top-level `llm:` config block
- **WHEN** `tools.knowledge.enrich_model` is not set
- **THEN** the synthesis model for `kb.ask()` is inherited from `llm.model` in the top-level `llm:` config block

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
The `chunks` table SHALL deduplicate on `(source_path, anchor)` — not on `topic`. `source_path` is the canonical file path (same as canonical topic before `topic_roots` stripping). `anchor` is the heading slug within the file (`""` for page-level preamble). `topic` is a non-unique human-readable label with a plain (non-unique) index.

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

#### Scenario: topic index is non-unique
- **WHEN** the `chunks` table is created
- **THEN** `idx_chunks_topic` SHALL be a plain index (not `UNIQUE`)

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
