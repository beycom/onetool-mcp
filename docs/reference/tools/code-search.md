# Code Search

**Find code by meaning. Not just text.**

Semantic code search using ChunkHound indexes and DuckDB.

## Highlights

- Natural language queries for code search
- Vector search via DuckDB vss extension
- Filter by language or project
- Provider/model filtering for embedding compatibility

## Functions

| Function | Description |
|----------|-------------|
| `code.search(query, ...)` | Search code by meaning |
| `code.status(project)` | Check index status |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Natural language query (e.g., "authentication logic") |
| `project` | str | Project name from config or path |
| `language` | str | Filter by language (e.g., "python") |
| `limit` | int | Max results (default: 10) |

## Requires

- `OT_OPENAI_API_KEY` for embeddings
- Project indexed with `chunkhound index <project>`

## Examples

```python
# Search by meaning
code.search(query="authentication logic", project="myapp")

# Filter by language
code.search(query="database connection", project="myapp", language="python")

# Check index status
code.status(project="myapp")
```

## Source

[ChunkHound](https://github.com/chunkhound/chunkhound) | [DuckDB](https://duckdb.org/)
