# Code Search

**Find code by meaning. Not just text.**

Semantic code search using ChunkHound indexes and DuckDB.

## Highlights

- Natural language queries for code search
- Vector search via DuckDB vss extension
- Filter by language, chunk type, or exclude patterns
- Batch search with multiple queries

## Functions

| Function | Description |
|----------|-------------|
| `code.search(query, ...)` | Search code by meaning |
| `code.search_batch(queries, ...)` | Batch search with multiple queries |
| `code.status(path, db)` | Check index status |

## Key Parameters

### `code.search()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Natural language query (e.g., "authentication logic") |
| `limit` | int | Max results (default: 10) |
| `language` | str | Filter by language (e.g., "python") |
| `chunk_type` | str | Filter by type: "function", "class", "method", "comment" |
| `expand` | int | Context lines to include around each match |
| `exclude` | str | Pipe-separated patterns to exclude (e.g., "test\|mock") |
| `path` | str | Path to project root (default: cwd) |
| `db` | str | Path to database file relative to project root |

### `code.search_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `queries` | str | Pipe-separated queries (e.g., "auth\|login\|session") |
| `limit` | int | Max results per query (default: 10) |
| `language` | str | Filter by language |
| `chunk_type` | str | Filter by type |
| `expand` | int | Context lines around matches |
| `exclude` | str | Patterns to exclude |
| `path` | str | Path to project root |
| `db` | str | Path to database file relative to project root |

## Snippets

| Snippet | Description | Example |
|---------|-------------|---------|
| `$c_search` | Basic semantic search | `$c_search query="auth logic"` |
| `$c_q` | Batch search | `$c_q q="auth\|login\|session"` |
| `$c_type` | Type-filtered search | `$c_type query="validation" type="function"` |

## Configuration

In `onetool.yaml`:

```yaml
tools:
  code:
    base_url: https://openrouter.ai/api/v1
    model: text-embedding-3-small
    db_path: .chunkhound/chunks.db
    dimensions: 1536
    content_limit: 500        # Max chars without expand (100-10000)
    content_limit_expanded: 2000  # Max chars with expand (500-20000)
```

## Requires

**Python packages:**

```bash
pip install duckdb openai
```

**Secrets:**

- `OPENAI_API_KEY` in secrets.yaml (for embeddings)

**Index:**

```bash
just index           # Index current project
just index path=.    # Explicit path
```

## Examples

```python
# Basic semantic search
code.search(query="authentication logic")

# Filter by language and type
code.search(query="database queries", language="python", chunk_type="function")

# Get expanded context (20 lines around match)
code.search(query="error handling", expand=20)

# Exclude test files
code.search(query="validation", exclude="test|mock|fixture")

# Batch search (multiple queries, merged results)
code.search_batch(queries="auth logic|token validation|session handling")

# Batch search excluding tests
code.search_batch(queries="error handling|validation", exclude="test")

# Check index status
code.status()
```

## Source

[ChunkHound](https://github.com/chunkhound/chunkhound) | [DuckDB](https://duckdb.org/)
