# ChunkHound MCP

Code search for large codebases — regex always available, semantic search and architecture analysis when an embedding provider is configured.

**Source:** [chunkhound/chunkhound](https://github.com/chunkhound/chunkhound)

## Enabling

The server is included in `servers.yaml` with `enabled: false`. To activate it permanently:

```yaml
chunkhound:
  enabled: true
```

Or enable for the current session only:

```python
ot_servers.enable(name="chunkhound")
```

## Server Config

```yaml
chunkhound:
  type: stdio
  command: chunkhound
  args:
    - "mcp"
  timeout: 30
  inherit_env: true  # Required: passes CHUNKHOUND_EMBEDDING__API_KEY
  enabled: true
```

### Setup

1. Install ChunkHound:
   ```bash
   pip install chunkhound
   ```

2. Create `.chunkhound.json` in the project root:
   ```json
   {
     "database": {"type": "duckdb", "path": ".chunkhound/db"},
     "embedding": {
       "provider": "openai",
       "base_url": "https://openrouter.ai/api/v1",
       "model": "text-embedding-3-small"
     },
     "llm": {"provider": "claude-code-cli"}
   }
   ```

3. Set your embedding API key (never put it in `.chunkhound.json`):
   ```bash
   export CHUNKHOUND_EMBEDDING__API_KEY=<your-key>
   ```

4. Index the project — run once from the project root, re-run only after significant changes:
   ```bash
   chunkhound index
   ```

!!! note
    `inherit_env: true` is required so the server inherits `CHUNKHOUND_EMBEDDING__API_KEY` at runtime.

### Embedding Providers

| Provider | `base_url` |
|----------|------------|
| OpenRouter (recommended) | `https://openrouter.ai/api/v1` |
| OpenAI direct | `https://api.openai.com/v1` |
| Ollama (local) | `http://localhost:11434/v1` |

## Tools

| Tool | Requires | Description |
|------|----------|-------------|
| `search_regex` | index | Fast regex search — always available after indexing |
| `search_semantic` | index + embedding key | Finds conceptually related code without knowing exact names |
| `code_research` | index + embedding + llm | Multi-hop architecture analysis |

## Usage Patterns

- **Exact pattern known**: use `search_regex` — faster, no API key required
- **Symbol name unknown**: use `search_semantic` with a description (e.g., `"function that parses JWT tokens"`)
- **Architecture questions**: use `code_research` (requires embedding + llm config)
- **Scope results**: pass `path="src/"` to any tool to limit search to a directory

## Examples

### 1. Find all function definitions matching a name pattern

Quickly locate every function or method named after a concept — no IDE needed.

```python
chunkhound.search_regex(pattern=r"def (create|make|build)_\w+", page_size=20)
```

### 2. Find all usages of a specific import

See every file that imports a module — useful before refactoring or deprecating a dependency.

```python
chunkhound.search_regex(pattern=r"from ot\.config import", page_size=50)
```

### 3. Search by concept rather than name

Find authentication-related code when you don't know the exact function name.

```python
chunkhound.search_semantic(query="validate API token and check permissions", page_size=5)
# Returns semantically similar code chunks — no exact keyword match needed
```

### 4. Find all TODO and FIXME comments

Surface technical debt across the entire codebase in one call.

```python
chunkhound.search_regex(pattern=r"#\s*(TODO|FIXME|HACK|XXX)", page_size=50)
```

### 5. Scope search to a specific directory

Search only inside `src/` to exclude tests and docs from results.

```python
chunkhound.search_regex(pattern=r"raise \w+Error", path="src/", page_size=20)
```

### 6. Find error handling patterns

Locate every `try/except` block to audit error handling consistency.

```python
chunkhound.search_regex(pattern=r"except\s+\w*Error", page_size=30)
```

### 7. Find test files for a module

Quickly navigate from source to its tests.

```python
chunkhound.search_regex(pattern=r"import.*LogSpan", path="tests/", page_size=10)
```

### 8. Understand how a feature is implemented

Ask a natural-language question about architecture — ChunkHound traces relationships across files.

```python
chunkhound.search_semantic(
    query="how MCP proxy servers are started and managed",
    page_size=8,
    path="src/"
)
```

## Common Mistakes to Avoid

- Don't enable the server before running `chunkhound index` — it will return empty results or errors
- Don't set API key values inside `.chunkhound.json` — use `CHUNKHOUND_EMBEDDING__API_KEY` env var
- Don't re-index on every session — only re-run after significant code changes
- Don't ignore a `db.wal.corrupt` file — delete it and re-index, or it will hang on every start
