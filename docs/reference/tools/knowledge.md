# Knowledge

Portable SQLite knowledge bases with hybrid FTS5+vector search and AI synthesis. Short alias: `kb`.

## Highlights

- Hybrid FTS5+vector search via `knowledge.search()` — keyword, semantic, or combined (hybrid) modes
- AI synthesis via `knowledge.ask()` — retrieves relevant chunks then synthesises a concise answer with source citations
- Personal annotations via `knowledge.write()` — store rules, notes, and mistakes alongside indexed content
- Link-graph traversal via `knowledge.related()` — follow markdown hyperlinks between topics

## Functions

| Function | Description |
|----------|-------------|
| `knowledge.write(topic, content, db, ...)` | Write a personal annotation to the knowledge database |
| `knowledge.read(topic, db, ...)` | Read a single entry by topic |
| `knowledge.update(topic, db, ...)` | Update an existing entry |
| `knowledge.append(topic, db, ...)` | Append content to an existing entry |
| `knowledge.delete(topic, db, ...)` | Delete an entry by topic |
| `knowledge.search(query, db, ...)` | Hybrid FTS5+vector search (mode: hybrid/semantic/keyword) |
| `knowledge.ask(query, db, ...)` | Retrieve relevant chunks and synthesise an AI answer |
| `knowledge.grep(pattern, db, ...)` | Regex/text search across all content |
| `knowledge.related(topic, db, ...)` | Find entries linked from or to a given topic |
| `knowledge.list(db, ...)` | List entries (returns meta only, no content) |
| `knowledge.toc(db, ...)` | Display table of contents for a database or topic prefix |
| `knowledge.slice(topic, db, ...)` | Extract a section from a large entry |
| `knowledge.stats(db)` | Chunk counts, embedding coverage, and file size |
| `knowledge.info(db)` | Database metadata, path, and version |
| `knowledge.dbs()` | List all configured knowledge databases |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search or question text |
| `db` | str | Database name (as configured under `tools.knowledge.kb`) |
| `topic` | str | Entry topic path (e.g. `python/tips/generators`) |
| `mode` | str | Search mode: `"hybrid"` (default), `"semantic"` (vector-only), `"keyword"` (FTS5-only) |
| `k` | int | Max results (default: `config.search_limit`) |
| `category` | str | Entry category filter — one of: `reference`, `rule`, `note`, `mistake` |
| `source` | str | Filter by `meta.source` prefix |
| `direction` | str | For `knowledge.related()`: `"out"` (links from topic), `"in"` (links to topic), `"both"` |
| `depth` | int | For `knowledge.related()`: traversal depth (default: 1) |

## Requires

- `OPENAI_API_KEY` in `secrets.yaml` (for embeddings and AI synthesis)
- `onetool-mcp[util]` extra (provides `sqlite-vec` and `python-frontmatter`)

## Configuration

### Required

- `OPENAI_API_KEY` must be set in `secrets.yaml` for embeddings and `knowledge.ask()`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.knowledge.model` | string | `""` | OpenAI embedding model. Falls back to `llm.embedding_model`; built-in default: `text-embedding-3-small`. |
| `tools.knowledge.base_url` | string | `""` | OpenAI-compatible API base URL. Empty = inherit from top-level `llm.base_url`. |
| `tools.knowledge.dimensions` | int | `1536` | Embedding dimensions. Must match the model and remain unchanged for an existing database. |
| `tools.knowledge.max_embedding_tokens` | int | `8191` | Max tokens per embedding input. |
| `tools.knowledge.embedding_batch_size` | int | `200` | Texts per embeddings API call. Range: `1-2048`. |
| `tools.knowledge.search_limit` | int | `10` | Default max search results. Range: `1-100`. |
| `tools.knowledge.search_extract` | int | `300` | Character limit for content extract in search results (`0` = full). |
| `tools.knowledge.enrich_model` | string | `""` | LLM model for `knowledge.ask()` synthesis and `kb enrich` summaries. Empty = falls back to top-level `llm.model`. |
| `tools.knowledge.enrich_prompt` | string | `""` | Custom summarisation instruction for `kb enrich`. Empty = built-in default. |
| `tools.knowledge.enrich_batch_size` | int | `20` | Summaries written per database commit during `kb enrich`. Range: `1-500`. |
| `tools.knowledge.enrich_min_chars` | int | `400` | Chunks with content shorter than this are skipped by `kb enrich` (`summary=''`). `0` disables skipping. |
| `tools.knowledge.enrich_max_chars` | int | `6000` | Chunk content is truncated to this many characters in the enrichment prompt. Min: `200`. |
| `tools.knowledge.min_chunk_chars` | int | `200` | Minimum body characters per chunk. Chunks below threshold are merged. `0` disables. |

Project registry (under `tools.knowledge.kb`):

The dimension is fixed when each database's vector table is created. Changing
`tools.knowledge.dimensions` does not migrate an existing database; if changed
accidentally, restore that database's original model and dimension setting.

```yaml
tools:
  knowledge:
    model: text-embedding-3-small
    base_url: ""
    dimensions: 1536
    search_limit: 10
    search_extract: 300
    enrich_model: ""
    min_chunk_chars: 200
    kb:
      docs:
        db:
          path: kb/docs.db
          description: Scraped documentation
          embeddings_enabled: true
        scrape:
          output_base_dir: /path/to/scraped/docs
          sources:
            python:
              url: https://docs.python.org/3/
              url_prefix: /3/
```

### Defaults

- If `tools.knowledge.base_url` is empty, it inherits from the top-level `llm.base_url`.
- If `tools.knowledge.model` is empty, it inherits from `llm.embedding_model`.
- If `tools.knowledge.enrich_model` is empty, it falls back to `llm.model`.

## Examples

```python
# Search a knowledge base (hybrid FTS5+vector)
knowledge.search(query='context managers', db='docs')

# Keyword-only search with more results
knowledge.search(query='yield generator', db='docs', mode='keyword', k=20)

# AI synthesis — retrieves relevant chunks then answers
knowledge.ask(query='How do I configure authentication?', db='docs')

# Write a personal annotation
knowledge.write(topic='python/tips/loops', content='Use enumerate() for index access', db='docs', category='rule')

# Grep for a pattern across all content
knowledge.grep(pattern='def __init__', db='docs')

# Follow related topics via link graph
knowledge.related(topic='python/asyncio/tasks', db='docs', direction='out', depth=2)

# List all configured databases
knowledge.dbs()

# Check database stats
knowledge.stats(db='docs')

# Read a specific entry
knowledge.read(topic='python/tips/loops', db='docs')
```

## CLI

The `onetool kb` command group handles offline knowledge base operations (scraping, indexing, and maintenance). All subcommands auto-detect `onetool.yaml` from the current directory.

### Global options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to `onetool.yaml` (auto-detected from `./onetool.yaml` or `.onetool/onetool.yaml`) |
| `-s, --secrets PATH` | Path to secrets file (auto-detected alongside config if omitted) |

### onetool kb scrape

Crawl all sources in a scrape project. Requires the `onetool-mcp[scrape]` extra and `playwright install chromium`.

```bash
onetool kb scrape <project> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--only TEXT` | Comma-separated source names to run (runs all if omitted) |
| `--resume` | Resume each source from `.state.json` if present |
| `--max-pages INT` | Hard limit on pages written per source (overrides config) |
| `--flat-files / --no-flat-files` | Write flat `::` -separated files instead of subdirectories |
| `--debug` | Write per-page debug artifacts (`cleaned.html`, `raw.html`, `screenshot.png`, `meta.json`) to `._debug/<slug>/` |

```bash
onetool kb scrape docs
onetool kb scrape docs --only python,stdlib --max-pages 200
onetool kb scrape docs --resume
```

### onetool kb index

Index a project's scraped content into the knowledge database.

```bash
onetool kb index <project> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--path PATH` | Directory to index (overrides project's `output_base_dir`) |
| `--overwrite TEXT` | `skip` (default) or `update` |
| `--enrich` | Generate LLM summaries for the chunks indexed this run |

```bash
onetool kb index docs
onetool kb index docs --overwrite update
onetool kb index docs --path /tmp/scraped
onetool kb index docs --overwrite update --enrich
```

### onetool kb enrich

Generate short LLM summaries for chunks missing them (backfill). Summaries are shown in `knowledge.search()` results and matched by keyword search. Requires `OPENAI_API_KEY`. Content changes (re-index, `kb.update`, `kb.append`) clear the affected summaries so the next run regenerates them.

```bash
onetool kb enrich <db> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--limit INT` | Max chunks to enrich this run (incremental backfill) |
| `--force` | Re-summarise all chunks, not just those missing summaries |

```bash
onetool kb enrich docs
onetool kb enrich docs --limit 100
onetool kb enrich docs --force
```

### onetool kb reindex

Backfill missing embeddings for all chunks in an existing database.
This does not rebuild the vector table or repair a model/dimension mismatch.

```bash
onetool kb reindex <db>
```

```bash
onetool kb reindex docs
```

### onetool kb stats

Print chunk counts, embedding coverage, and file size.

```bash
onetool kb stats <db>
```

### onetool kb info

Print database metadata, path, and version.

```bash
onetool kb info <db>
```

### onetool kb export

Export all chunks (or a filtered subset) to a JSON file.

```bash
onetool kb export <db> --output <path> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output JSON file path (required) |
| `--category TEXT` | Filter by category |
| `--topic TEXT` | Filter by topic prefix |

```bash
onetool kb export docs --output docs-dump.json
onetool kb export docs --output rules.json --category rule
```
