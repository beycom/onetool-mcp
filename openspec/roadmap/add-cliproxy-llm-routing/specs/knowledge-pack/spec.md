## MODIFIED Requirements

### Requirement: Config schema — tools.knowledge
The `onetool.yaml` `tools.knowledge` block SHALL support `kb` (map of project name
to `KBProjectConfig`), `llm` (optional pack-level generation selection), `ask`
(optional ask-operation generation selection), `rerank` (optional rerank-operation
generation selection), `enrich` (optional enrichment generation selection),
`enrich_prompt`, `enrich_batch_size`, `enrich_min_chars`, `enrich_max_chars`,
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
validation errors. Removed top-level keys such as `databases:`, `scrape:`,
embedding `model:`, embedding `base_url:`, and `enrich_model:` SHALL be treated as
unknown fields, with no compatibility migration path.

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

#### Scenario: Unified kb project config
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

#### Scenario: Removed keys raise validation error
- **WHEN** `tools.knowledge.databases`, `tools.knowledge.scrape`, `tools.knowledge.model`, `tools.knowledge.base_url`, or `tools.knowledge.enrich_model` is set
- **THEN** a validation error SHALL identify the extra input

#### Scenario: Embeddings use independent configuration
- **WHEN** a knowledge project has `embeddings_enabled: true`
- **THEN** embedding operations SHALL use only the top-level `embeddings` route
- **AND** they SHALL NOT inherit from top-level `llm` or a knowledge generation selection

#### Scenario: Generation selections fall through by scope
- **WHEN** an ask, rerank, or enrich generation field is omitted at operation scope
- **THEN** it SHALL fall through to `tools.knowledge.llm`, then top-level `llm`

#### Scenario: enrich_prompt overrides the built-in instruction
- **WHEN** `tools.knowledge.enrich_prompt` is set to a custom instruction
- **THEN** `kb enrich` uses it as the summarisation instruction while keeping the untrusted-context boundary in the system message

#### Scenario: Enrichment config keys are validated
- **WHEN** `tools.knowledge.enrich_batch_size: 0` or an unknown key such as `tools.knowledge.enrich_foo` is configured
- **THEN** config validation SHALL raise an error

## ADDED Requirements

### Requirement: Knowledge generation routing and controls

Knowledge enrichment, reranking, and answer synthesis SHALL use their effective
shared generation selections. Network-backed knowledge operations SHALL accept
optional model and effort overrides at their public call boundary where the caller
controls generation.

#### Scenario: Ask uses operation routes
- **WHEN** `kb.ask()` performs reranking and synthesis
- **THEN** each stage SHALL use its configured operation selection or the documented fallback scope

#### Scenario: Ask model and effort override
- **WHEN** `kb.ask()` is called with `model="sol"` and `effort="high"`
- **THEN** the call-controlled generation stages SHALL resolve `sol` and request high effort

#### Scenario: Enrichment uses CLIProxyAPI
- **WHEN** the effective enrichment backend is `cliproxy`
- **THEN** `kb enrich` SHALL use the shared CLIProxyAPI service without requiring a provider API key

#### Scenario: Embedding route is not reused for generation
- **WHEN** embeddings and knowledge generation use different backends
- **THEN** reranking, synthesis, and enrichment SHALL NOT use the embedding endpoint or credential

