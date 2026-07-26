# OT Context

TTL-expiring, BM25-indexed storage for large tool outputs. Replace context-window saturation with targeted retrieval.

## Highlights

- Handles large outputs (API responses, logs, docs) without saturating the context window
- `ctx.query()` for structured JSON/YAML extraction using JMESPath
- ~1ms write latency — indexing runs in a background daemon thread
- TTL-expiring handles (default 3600s); no-expiry with `ttl=0`
- Large content (>256KB) spills to disk automatically; handle stays the same
- Regex and fuzzy grep with context lines
- Section slicing by number, heading, or line range
- Optional semantic embeddings via ot_llm (when configured)
- `ctx.ask()` sends one or more questions about stored content to an LLM in a single batched call
- Pure stdlib — no external dependencies

## Functions

| Function | Description |
|----------|-------------|
| `ctx.write(content, source, verbose)` | Store content, return handle + optional preview |
| `ctx.append(handle, content)` | Append content and re-index |
| `ctx.read(handle, offset, limit, tail, mode)` | Paginated raw content, metadata, or TOC |
| `ctx.toc(handle)` | Numbered section index with vocabulary hints |
| `ctx.query(handle, expr)` | Evaluate JMESPath expression against JSON/YAML handles |
| `ctx.grep(handle, pattern, context, fuzzy)` | Regex or fuzzy line search |
| `ctx.slice(handle, select)` | Extract by section number, heading, or line range |
| `ctx.ask(handle, q, model)` | Multi-question LLM query over stored content (optional) |
| `ctx.list(source, status)` | All active handles with summary |
| `ctx.inspect(handle)` | Detailed metadata for one handle |
| `ctx.stats()` | Session storage metrics |
| `ctx.delete(handle)` | Remove one handle |
| `ctx.purge(delete_all, minutes, source, status)` | Bulk-delete handles and compact DB |

## Key Parameters

### `ctx.write()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | str | Content to store |
| `source` | str | Optional label (e.g. "brave", "api") for filtering |
| `verbose` | bool | Include a short preview in the returned payload |

Returns a dict with `handle`, `size_bytes`, `total_lines`, `status`, and `abstract` (populated asynchronously). Pass `verbose=True` to also include `preview` (first 5 non-empty lines).

### `ctx.read()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `offset` | int | 1-indexed starting line (default 1) |
| `limit` | int | Max lines to return (default 100) |
| `tail` | int | Return last N lines; overrides offset/limit |
| `mode` | str | `"toc"` → section index; `"meta"` → metadata only |

### `ctx.query()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `expr` | str | JMESPath expression (for example `items[0].name`) |

Returns `{handle, expr, result}` on success, or an error payload when format/expr is invalid.

### `ctx.grep()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `pattern` | str | Regex pattern (or plain text if `fuzzy=True`) |
| `context` | int | Lines before/after each match (default 0) |
| `fuzzy` | bool | Use SequenceMatcher instead of regex |

### `ctx.slice()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `select` | int or str | Section number (int), line range `"N:M"`, or heading substring |

### `ctx.purge()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `delete_all` | bool | Bypass the age filter — delete all matching handles regardless of age |
| `minutes` | int | Delete handles older than N minutes (default 15) |
| `source` | str | Delete handles matching source substring |
| `status` | str | Delete handles with this status |

With no arguments, deletes handles older than 15 minutes, then compacts the DB.

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `core`.

No additional runtime requirements are declared.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

None — no secrets required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ctx.ttl` | int | `3600` | Handle TTL in seconds. `0` = no expiry. |
| `tools.ctx.max_line_chars` | int | `500` | Lines longer than this are truncated with a `[+N chars]` suffix. |
| `tools.ctx.ask_max_bytes` | int | `204800` | Content is truncated to this size before sending to `ctx.ask` (bytes). `0` = no limit. |

```yaml
tools:
  ctx:
    ttl: 3600
    max_line_chars: 500
    ask_max_bytes: 204800
```

### Defaults

- If `tools.ctx` is omitted, handles expire after 3600 seconds and long lines are truncated at 500 characters.

## Examples

```python
# Store API response and search it
h = ctx.write(big_json_output, source="api")
ctx.query(h["handle"], expr="items[?status == 'active'].name")

# Read a log file page-by-page
h = ctx.write(log_content, source="logs")
ctx.read(h["handle"], offset=1, limit=50)
ctx.read(h["handle"], offset=51, limit=50)

# Get the last 20 lines
ctx.read(h["handle"], tail=20)

# TOC navigation
ctx.toc(h["handle"])
ctx.slice(h["handle"], select="Installation")  # by heading
ctx.slice(h["handle"], select=3)               # by section number
ctx.slice(h["handle"], select="10:25")         # by line range

# Grep with context
ctx.grep(h["handle"], pattern=r"ERROR|WARN", context=2)

# LLM questions (requires ot_llm pack)
ctx.ask(h["handle"], q="What are the API endpoints?")
ctx.ask(h["handle"], q=["What errors are possible?", "What is the rate limit?"])

# Maintenance
ctx.list()                                  # all active handles
ctx.stats()                                 # storage metrics
ctx.purge()                                 # delete expired handles + compact
ctx.purge(delete_all=True)                  # wipe everything
ctx.purge(status="failed")                  # remove failed indexing handles
ctx.purge(minutes=60)                       # remove handles older than 1 hour
ctx.delete(h["handle"])              # remove one handle
```
