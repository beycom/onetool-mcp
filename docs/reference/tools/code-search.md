# Code Search

**Find code by meaning. Not just text.**

Semantic code search using ChunkHound indexes and DuckDB.

| Function | Description |
|----------|-------------|
| `code.search(query, ...)` | Search code by meaning |
| `code.status(project)`    | Check index status |

**Key Parameters:**
- `query`: Natural language query (e.g., "authentication logic")
- `project`: Project name from config or path
- `language`: Filter by language (e.g., "python")
- `limit`: Max results (default: 10)

**Requires:**
- `OT_OPENAI_API_KEY` for embeddings
- Project indexed with `chunkhound index <project>`

**Based on:** [ChunkHound](https://github.com/chunkhound/chunkhound) DuckDB schema

**Implementation notes:**
- Queries existing ChunkHound DuckDB databases
- Uses `array_cosine_similarity()` for vector search via vss extension
- Filters by provider/model for embedding compatibility
- Resolves file paths via files table join

**Comparison:** Custom implementation; no upstream MCP exists. Uses ChunkHound indexes + DuckDB queries with provider/model filtering.

**License:** MIT ([LICENSE](../../../licenses/chunkhound-LICENSE))
