# Memory

Persistent memory for AI agents with SQLite storage and optional semantic search.

## Highlights

- Topic-based memory with path hierarchy (`projects/onetool/rules`)
- Semantic (indexed KNN via sqlite-vec), keyword (FTS5 BM25), and hybrid (RRF) search modes
- SHA-256 content dedup prevents duplicate storage
- Automatic secret/PII redaction on write
- History tracking on updates with `mem.history()` / `mem.rollback()`
- Chunk-and-average embeddings for large content (full document semantics preserved)
- In-memory read cache with TTL and LRU eviction (auto-invalidated on writes)
- Importance decay based on age and access patterns
- YAML dump/load
- File-based snapshot/restore with lossless round-trip
- Section navigation: table of contents, section slicing, and staleness detection
- Extensible `meta` column for key-value metadata per memory

## Functions

| Function | Description |
|----------|-------------|
| `mem.write(topic, content, ..., toc)` | Store a memory (with optional section index) |
| `mem.write_batch(topic, glob_pattern, ..., toc)` | Bulk store from files (preserves directory structure) |
| `mem.read(topic, id, mode)` | Read a single memory (mode: content/toc/meta/all) |
| `mem.read_batch(topic, ids, ..., mode)` | Read multiple memories (mode: content/toc/meta/all) |
| `mem.toc(topic, id)` | Display numbered section index with staleness detection |
| `mem.slice(topic, select, id)` | Extract content by section number, heading, line range, or list |
| `mem.search(query, mode, ...)` | Search memories (returns meta + truncated extract) |
| `mem.grep(pattern, mode, ...)` | Regex/text search across memory content |
| `mem.ask(topic, q, ...)` | Q&A over a memory using LLM synthesis |
| `mem.query(topic, expr, ...)` | JMESPath query against a JSON/YAML memory |
| `mem.inspect(topic, ...)` | Low-level structured metadata for a single memory |
| `mem.list(topic, category)` | List memories (returns meta only, no content) |
| `mem.count(topic, category)` | Count memories |
| `mem.delete(topic, id, confirm)` | Delete memories |
| `mem.update(topic, content, id)` | Update a memory (recomputes toc if sections exist) |
| `mem.history(topic, id, limit)` | List prior versions of a memory, newest first |
| `mem.rollback(topic, id, version, history_id)` | Restore a memory to a prior version (undoable) |
| `mem.append(topic, content, id)` | Append to a memory (recomputes toc if sections exist) |
| `mem.context(topic, limit)` | Load hot cache context |
| `mem.update_batch(search_text, replace_text, ...)` | Batch search-and-replace (recomputes toc if sections exist) |
| `mem.decay(dry_run)` | Apply importance decay (never increases relevance) |
| `mem.stats()` | Show statistics |
| `mem.reindex(...)` | Reindex all un-embedded memories |
| `mem.flush()` | Wait for background embeddings to complete |
| `mem.dump(topic, output)` | Dump to YAML |
| `mem.load(file)` | Import YAML dumped by `mem.dump()` |
| `mem.snapshot(output, topic, ext, on_conflict)` | Snapshot memories to directory with index.yaml |
| `mem.restore(input, topic, overwrite)` | Restore memories from snapshot directory |
| `mem.stale(topic)` | Check which file-backed memories are outdated |
| `mem.refresh(topic, dry_run)` | Re-read source files for stale memories |
| `mem.slice_batch(items)` | Extract sections from multiple memories in one call |

## Retrieval Functions

The retrieval functions return different levels of detail:

| Function | Returns | Use when |
|----------|---------|----------|
| `mem.list()` | Meta only (topic, category, relevance, access count, size, tags, id) | Browsing what's stored |
| `mem.search()` | Meta + truncated extract (default 200 chars, configurable via `extract`) | Finding relevant memories |
| `mem.read()` | Full content for a single memory (optionally with meta header via `meta=True`) | Reading one specific memory |
| `mem.read(mode="toc")` | Numbered section index with line ranges | Navigating a large document |
| `mem.read(mode="meta")` | Metadata only (including meta map) | Inspecting memory properties |
| `mem.read_batch()` | Full content for multiple memories with dividers | Reading several memories at once |
| `mem.toc()` | Section index with staleness detection | Checking document structure |
| `mem.slice()` | Extracted sections by number, heading, or line range | Reading specific parts |

## Key Parameters

### `mem.write()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic path using `/` separator |
| `content` | str | Memory content text |
| `category` | str | One of: rule, context, decision, mistake, discovery, note |
| `tags` | list | Optional tags for categorisation |
| `relevance` | int | Importance 1-10, enforced (default: 5) |
| `file` | str | Read content from file instead (max 1MB). Auto-populates `source`, `source_mtime`, `content_type` in meta |
| `toc` | bool | Parse markdown headings and store section index in meta (default: False) |

### `mem.write_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Base topic path (relative file path appended as subtopic) |
| `glob_pattern` | str | Glob pattern to match files (e.g., "docs/**/*.md") |
| `category` | str | Category for all memories (default: note) |
| `tags` | list | Tags applied to all memories |
| `relevance` | int | Relevance score for all memories (default: 5) |
| `toc` | bool | Parse markdown headings per file (default: False) |

### `mem.search()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query text |
| `mode` | str | "semantic" (default), "keyword", or "hybrid" |
| `topic` | str | Topic prefix filter |
| `category` | str | Category filter |
| `limit` | int | Max results (default: config search_limit) |
| `tags` | list | Tag filter (matches any) |
| `extract` | int | Content extract char limit (default: config search_extract, 0 = full) |

### `mem.grep()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `pattern` | str | Text or regex pattern to match |
| `topic` | str | Topic prefix filter |
| `ids` | list | Restrict search to specific memory IDs |
| `category` | str | Category filter |
| `tags` | list | Tag filter (matches any) |
| `limit` | int | Max matches to return |
| `ignore_case` | bool | Case-insensitive match |
| `word` | bool | Match whole words only |
| `regex` | bool | Treat `pattern` as regex |
| `invert` | bool | Return non-matching entries |
| `max_chars` | int | Max characters to scan per memory |

### `mem.read_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic prefix filter |
| `ids` | list | Specific memory IDs to read |
| `category` | str | Category filter |
| `tags` | list | Tag filter (matches any) |
| `meta` | bool | Include metadata headers (default: False) |
| `mode` | str | Output mode: "content" (default), "toc", "meta", "all" |
| `limit` | int | Max results (default: 50) |

At least one filter (`topic`, `ids`, `category`, or `tags`) is required. Note: `ids` cannot be combined with other filters (`topic`, `category`, `tags`).

### `mem.toc()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic of the memory |
| `id` | str | Optional memory ID (overrides topic) |

Returns a numbered section index with line ranges. Warns if the source file has been modified since storage.

### `mem.slice()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic of the memory |
| `select` | int/str/list | Section selector: section number (int), line range (":50", "400:", "151:200"), heading path (str), or mixed list |
| `id` | str | Optional memory ID (overrides topic) |

### `mem.history()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic to find the memory (must match exactly one) |
| `id` | str | Optional memory ID (overrides topic) |
| `limit` | int | Max versions to list (default: 10) |

Versions are numbered v1..vN (v1 = most recent prior version); numbers shift as new history accrues. The bracketed 8-char history-id prefix is the stable selector for `mem.rollback(history_id=...)`.

### `mem.rollback()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic to find the memory (must match exactly one) |
| `id` | str | Optional memory ID (overrides topic) |
| `version` | int | Version number from `mem.history()` (default: 1) |
| `history_id` | str | History-row id (full or unambiguous prefix; overrides version) |

Restores content only (category/tags/relevance are kept). The current content is saved to history first, so a rollback is itself undoable. TOC sections and embeddings are recomputed.

### Concurrent mutations

`update`, `append`, `rollback`, applied `update_batch`, and applied `refresh` compare the exact content predecessor they read before committing. History, content/metadata, and vector state commit atomically; a conflicting operation reports an error without adding history, changing vectors, or enqueueing an asynchronous embedding. Embedding generation remains outside the database lock.

Concurrent appends retry a bounded number of times. Every retry rereads the latest content, rebuilds the append result, and regenerates its embedding, so successful concurrent appends preserve both additions.

### `mem.update_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `search_text` | str | Text to find |
| `replace_text` | str | Replacement text |
| `topic` | str | Optional topic prefix scope |
| `dry_run` | bool | Preview only (default: True) |

### `mem.snapshot()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `output` | str | Output directory path (required) |
| `topic` | str | Topic prefix filter (all memories if omitted) |
| `ext` | str | File extension for content files (default: "") |
| `on_conflict` | str | "skip" (default) or "overwrite" for existing files |

### `mem.restore()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | str | Input directory path containing index.yaml (required) |
| `topic` | str | Override base topic (remaps topic prefix) |
| `overwrite` | bool | Overwrite existing memories with same topic+hash (default: False) |

### `mem.load()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | str | YAML file produced by `mem.dump(output=...)` |

### `mem.stale()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic prefix filter (all memories if omitted) |

Checks file-backed memories for staleness by comparing stored `source_mtime` against the current file modification time. Only checks memories written via `file=`.

### `mem.refresh()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic prefix filter (all memories if omitted) |
| `dry_run` | bool | Preview only (default: True) |

Re-reads source files for stale memories and updates their content. Preserves history.

### `mem.slice_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | list | List of dicts, each with `topic` or `id` (str) and `select` (int, str, or list). Max 20 items. |

Extract sections from multiple memories in a single call.

## Configuration

### Required

- No required `tools.mem` settings.
- `OPENAI_API_KEY` is only required if you enable embeddings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.mem.db_path` | string | `data/mem/default.db` | SQLite database path, relative to the OneTool directory. |
| `tools.mem.model` | string | `""` | Embedding model. Falls back to `llm.embedding_model`; built-in default: `text-embedding-3-small`. |
| `tools.mem.base_url` | string | `""` | OpenAI-compatible embeddings API base URL. Falls back to `llm.base_url`. |
| `tools.mem.dimensions` | int | `1536` | Embedding dimensions. Must match the configured model. |
| `tools.mem.search_limit` | int | `10` | Default max search results. Range: `1-100`. |
| `tools.mem.search_extract` | int | `200` | Default extract length in chars. `0` means full content. |
| `tools.mem.redaction_enabled` | bool | `true` | Enable secret/PII redaction on write. |
| `tools.mem.redaction_patterns` | string[] | `[]` | Extra regex patterns to redact. |
| `tools.mem.tags_whitelist` | string[] | `[]` | Allowed tag prefixes. Empty means unrestricted. |
| `tools.mem.decay_half_life_days` | int | `30` | Importance decay half-life in days. |
| `tools.mem.allowed_file_dirs` | string[] | `[]` | Allowed directories for file-backed memory operations. |
| `tools.mem.exclude_file_patterns` | string[] | `[".git", "node_modules", "__pycache__", ".venv", "venv"]` | Excluded file patterns for file-backed memory operations. |
| `tools.mem.max_embedding_tokens` | int | `8191` | Max tokens per embedding input. |
| `tools.mem.read_cache_max_size` | int | `128` | Read cache size. `0` disables the cache. |
| `tools.mem.read_cache_ttl_seconds` | int | `300` | Read cache TTL. `0` means no expiry. |
| `tools.mem.embeddings_enabled` | bool | `false` | Enable semantic embeddings and vector search. |
| `tools.mem.embeddings_async` | bool | `true` | Generate embeddings asynchronously. |

```yaml
tools:
  mem:
    db_path: data/mem/default.db
    model: text-embedding-3-small
    base_url: https://openrouter.ai/api/v1
    dimensions: 1536
    search_limit: 10
    search_extract: 200
    max_embedding_tokens: 8191
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

### Defaults

- If `tools.mem` is omitted, OneTool uses the built-in storage, redaction, search, cache, and embedding defaults shown above.

## Topic Hierarchy

Topics use `/` as separator for path-based hierarchy:

```
projects/onetool/rules
projects/onetool/decisions
learnings/python
learnings/sqlite
```

Filtering with trailing `/` matches all children: `topic="projects/"` matches everything under projects.

## Categories

| Category | Use |
|----------|-----|
| `rule` | Rules and constraints |
| `context` | Background information |
| `decision` | Architectural decisions |
| `mistake` | Errors and lessons learned |
| `discovery` | New findings |
| `note` | General notes (default) |

## Examples

```python
# Store a rule
mem.write(topic="projects/onetool/rules", content="Use keyword-only args", category="rule")

# Bulk store from files (preserves directory structure)
mem.write_batch(topic="docs", glob_pattern="docs/**/*.md", category="context")

# Search semantically
mem.search(query="authentication patterns")

# Keyword search with topic filter
mem.search(query="database", mode="keyword", topic="projects/")

# Search with longer extract
mem.search(query="rules", extract=500)

# Search with full content (no truncation)
mem.search(query="rules", extract=0)

# Read all memories under a topic
mem.read_batch(topic="projects/onetool/agents/")

# Read specific memories by ID with metadata
mem.read_batch(ids=["abc-123", "def-456"], meta=True)

# Load context for session
mem.context(topic="projects/onetool/", limit=10)

# Dump backup
mem.dump(output="memories.yaml")

# Load dumped backup
mem.load(file="memories.yaml")

# Snapshot to directory (one file per memory + index.yaml)
mem.snapshot(output="backup/consult", topic="consult/")

# Restore from snapshot
mem.restore(input="backup/consult", topic="consult")

# Batch update
mem.update_batch(search_text="old_name", replace_text="new_name", dry_run=False)

# Apply importance decay
mem.decay(dry_run=False)

# Store a spec with table of contents
mem.write(topic="spec", file="spec.md", toc=True)

# View section index
mem.toc(topic="spec")

# Read just section 2
mem.slice(topic="spec", select=2)

# Read by heading name
mem.slice(topic="spec", select="Requirements")

# Read first 50 lines
mem.slice(topic="spec", select=":50")

# Read multiple sections at once
mem.slice(topic="spec", select=[1, "Requirements", "200:300"])

# Read metadata only
mem.read(topic="spec", mode="meta")

# Bulk store specs with toc
mem.write_batch(topic="specs", glob_pattern="specs/**/*.md", toc=True)

# Check for stale file-backed memories
mem.stale(topic="docs/")

# Refresh stale memories from source files
mem.refresh(topic="docs/", dry_run=False)

# Batch slice: extract sections from multiple memories at once
mem.slice_batch(items=[
    {"topic": "spec", "select": 2},
    {"topic": "rules", "select": "Requirements"},
])

```

## Section Navigation

When storing markdown files, use `toc=True` to build a section index. This enables agents to inspect document structure and extract specific sections without consuming full token cost.

**Workflow:**
1. `mem.write(topic="spec", file="spec.md", toc=True)` - store with section index
2. `mem.toc(topic="spec")` - view numbered sections with line ranges
3. `mem.slice(topic="spec", select=2)` - read only the section you need

The `toc()` function checks if the source file has changed since storage and warns about staleness. When `mem.update()` or `mem.append()` modifies a memory that has sections, the section index is automatically recomputed.

**Slice selectors:**
- `int` - section number (1-indexed)
- `":50"` - first 50 lines
- `"400:"` - line 400 to end
- `"151:200"` - line range
- `"-50:"` - last 50 lines
- `"Requirements"` - heading path (case-insensitive substring match)
- `[1, "Requirements", "200:300"]` - mixed list

## Requires

- `OPENAI_API_KEY` in secrets.yaml (only when `embeddings_enabled: true`)
- SQLite (Python stdlib `sqlite3`)
- tiktoken (bundled with OneTool)

## Embedding Large Content

When content exceeds the embedding model's token limit, it is automatically split into chunks, each chunk is embedded, and the vectors are averaged. This preserves semantic coverage of the full document — keyword search (`mode="keyword"`) always searches the complete stored text regardless.

A safety margin of 100 tokens is subtracted from the limit to avoid edge-case overflows.

Configure the token limit via `max_embedding_tokens` in `onetool.yaml`:

```yaml
tools:
  mem:
    max_embedding_tokens: 8191  # default for text-embedding-3-small
```

For unknown models, falls back to the `cl100k_base` tiktoken encoding.

## Read Cache

Repeated reads of the same topic are served from an in-memory cache, avoiding redundant DB queries. The cache is automatically invalidated when content changes (write, update, append, delete). Access counts are still incremented on every read, even cache hits.

```yaml
tools:
  mem:
    read_cache_max_size: 128   # max entries (0 = disabled)
    read_cache_ttl_seconds: 300  # 5 minutes (0 = no expiry)
```

Bulk operations (`update_batch`, `load`) clear the entire cache.

## Embeddings

Embeddings are **opt-in** and disabled by default. Without embeddings, mem works as pure key-value storage with pattern search. No API key is needed.

To enable semantic search:

```yaml
tools:
  mem:
    embeddings_enabled: true    # Enable embedding generation
    embeddings_async: true      # Generate in background (default)
```

When `embeddings_async: true` (default), writes return immediately and embeddings are generated by a background worker thread. Use `mem.flush()` to wait for pending embeddings.

To backfill embeddings for existing memories:

```python
mem.reindex()                                  # Backfill all un-embedded memories
mem.reindex(topic="projects/", dry_run=True)   # Preview scoped backfill
mem.reindex(topic="projects/", dry_run=False)  # Run scoped backfill
```

When embeddings are disabled, `mem.search(mode="semantic")` and `mem.search(mode="hybrid")` return a helpful message. Pattern search always works regardless of embedding state.
