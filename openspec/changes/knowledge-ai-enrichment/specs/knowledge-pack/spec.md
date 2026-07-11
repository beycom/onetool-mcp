# Delta: knowledge-pack — AI enrichment (summary generation)

## ADDED Requirements

### Requirement: AI enrichment — kb enrich summary generation

The CLI command `onetool kb enrich <db>` SHALL generate short document summaries via an OpenAI-compatible chat LLM and write them to `chunks.summary`. Enrichment SHALL be CLI-only (no `kb.enrich()` pack tool, matching `kb index` / `kb reindex`) and SHALL never run implicitly from pack tool calls.

Selection semantics (making every run a backfill):
- Default: only chunks with `summary IS NULL OR summary = ''`, excluding the reserved `_meta` topic.
- `--force`: all chunks, regenerating existing summaries.
- `--limit N`: cap the number of chunks processed in this run.

Model and client resolution SHALL follow the existing knowledge-pack LLM conventions: model = `tools.knowledge.enrich_model`, falling back to top-level `llm.model`; API key = `OPENAI_API_KEY` from secrets; base URL = `tools.knowledge.base_url`, falling back to `llm.base_url`.

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

#### Scenario: Missing API key fails loudly
- **WHEN** `onetool kb enrich docs` is run without `OPENAI_API_KEY` configured
- **THEN** the command exits with an actionable error naming the missing secret, and no chunk is modified

#### Scenario: Model falls back to top-level llm config
- **WHEN** `tools.knowledge.enrich_model` is not set
- **THEN** enrichment uses `llm.model` from the top-level `llm:` config block

#### Scenario: System message carries the untrusted-context boundary
- **WHEN** an enrichment LLM request is built
- **THEN** its `messages` list includes a `system` role message instructing the model to treat the chunk content as untrusted data, not instructions

---

### Requirement: AI enrichment — batching, failure handling, and durability

Enrichment SHALL make one chat-completion call per chunk (no multi-chunk batch parsing) with the chunk's content truncated to `tools.knowledge.enrich_max_chars` characters (default 6000). Progress SHALL be committed every `tools.knowledge.enrich_batch_size` summaries (default 20) so an interrupted run keeps completed work.

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

## MODIFIED Requirements

### Requirement: Config schema — tools.knowledge
The `onetool.yaml` `tools.knowledge` block SHALL support: `kb` (map of project name → `KBProjectConfig`), `model` (embedding model), `base_url`, `enrich_model`, `enrich_prompt`, `enrich_batch_size`, `enrich_min_chars`, `enrich_max_chars`, `min_chunk_chars`, `dimensions`, `search_limit`, `search_extract`.

Enrichment keys:
- `enrich_model` (default `""`) — chat model for `kb.ask` rerank/synthesis and `kb enrich` summarisation; empty falls back to top-level `llm.model`
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
- **THEN** the synthesis model for `kb.ask()` and the summarisation model for `kb enrich` are inherited from `llm.model` in the top-level `llm:` config block

#### Scenario: enrich_prompt overrides the built-in instruction
- **WHEN** `tools.knowledge.enrich_prompt` is set to a custom instruction
- **THEN** `kb enrich` uses it as the summarisation instruction while keeping the untrusted-context boundary in the system message

#### Scenario: Enrichment config keys are validated
- **WHEN** `tools.knowledge.enrich_batch_size: 0` (below minimum) or an unknown key such as `tools.knowledge.enrich_foo` is configured
- **THEN** config validation raises an error
