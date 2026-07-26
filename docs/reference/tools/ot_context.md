# OT Context

`ot_context` (`ctx`) provides TTL-expiring, BM25-indexed storage and targeted retrieval for large tool outputs.

## Highlights

- Large-output storage with TTL expiry and stable handles
- BM25, regex, fuzzy, structured-data, and section-based retrieval
- Background indexing with large content spilling to disk automatically
- Optional batched generation questions through `ot_context.ask()`

## Functions

| Function | Description |
|----------|-------------|
| `ot_context.write(content, ...)` | Store content, return handle + optional preview |
| `ot_context.append(handle, content)` | Append content and re-index |
| `ot_context.read(handle, ...)` | Paginated raw content, metadata, or TOC |
| `ot_context.toc(handle)` | Numbered section index with vocabulary hints |
| `ot_context.query(handle, expr)` | Evaluate JMESPath expression against JSON/YAML handles |
| `ot_context.grep(handle, pattern, ...)` | Regex or fuzzy line search |
| `ot_context.slice(handle, select)` | Extract by section number, heading, or line range |
| `ot_context.ask(handle, q, ...)` | Multi-question LLM query over stored content |
| `ot_context.list(...)` | All active handles with summary |
| `ot_context.inspect(handle)` | Detailed metadata for one handle |
| `ot_context.stats()` | Session storage metrics |
| `ot_context.delete(handle)` | Remove one handle |
| `ot_context.purge(...)` | Bulk-delete handles and compact DB |

## Key Parameters

### `ot_context.write()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | str | Content to store |
| `source` | str | Optional label (e.g. "brave", "api") for filtering |
| `verbose` | bool | Include a short preview in the returned payload |

Returns a dict with `handle`, `size_bytes`, `total_lines`, `status`, and `abstract` (populated asynchronously). Pass `verbose=True` to also include `preview` (first 5 non-empty lines).

### `ot_context.read()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from `ot_context.write()` |
| `offset` | int | 1-indexed starting line (default 1) |
| `limit` | int | Max lines to return (default 100) |
| `tail` | int | Return last N lines; overrides offset/limit |
| `mode` | str | `"toc"` → section index; `"meta"` → metadata only |

### `ot_context.query()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from `ot_context.write()` |
| `expr` | str | JMESPath expression (for example `items[0].name`) |

Returns `{handle, expr, result}` on success, or an error payload when format/expr is invalid.

### `ot_context.grep()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from `ot_context.write()` |
| `pattern` | str | Regex pattern (or plain text if `fuzzy=True`) |
| `context` | int | Lines before/after each match (default 0) |
| `fuzzy` | bool | Use SequenceMatcher instead of regex |

### `ot_context.slice()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from `ot_context.write()` |
| `select` | int or str | Section number (int), line range `"N:M"`, or heading substring |

### `ot_context.purge()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `delete_all` | bool | Bypass the age filter — delete all matching handles regardless of age |
| `minutes` | int | Delete handles older than N minutes (default 15) |
| `source` | str | Delete handles matching source substring |
| `status` | str | Delete handles with this status |

With no arguments, deletes handles older than 15 minutes, then compacts the DB.

## Requires

- No secrets or external binaries for storage and retrieval
- An effective generation route and its named secret for `ot_context.ask()`

## Configuration

### Required

None for storage and retrieval. `ot_context.ask()` requires an effective
generation route and its named secret.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_context.llm` | generation selection \| null | `null` | Pack generation overrides for `ot_context.ask()` |
| `tools.ot_context.ttl` | int | `3600` | Handle TTL in seconds. `0` = no expiry. |
| `tools.ot_context.max_line_chars` | int | `500` | Lines longer than this are truncated with a `[+N chars]` suffix. |
| `tools.ot_context.ask_max_bytes` | int | `204800` | Content is truncated before `ot_context.ask()` (bytes). `0` = no limit. |

```yaml
tools:
  ot_context:
    llm:
      model: luna
    ttl: 3600
    max_line_chars: 500
    ask_max_bytes: 204800
```

### Defaults

- If `tools.ot_context` is omitted, handles expire after 3600 seconds and long
  lines are truncated at 500 characters.

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

# LLM questions (requires an effective generation route)
ctx.ask(h["handle"], q="What are the API endpoints?")
ctx.ask(
    h["handle"],
    q=["What errors are possible?", "What is the rate limit?"],
    model="sol",
    effort="medium",
)

# Maintenance
ctx.list()                                  # all active handles
ctx.stats()                                 # storage metrics
ctx.purge()                                 # delete expired handles + compact
ctx.purge(delete_all=True)                  # wipe everything
ctx.purge(status="failed")                  # remove failed indexing handles
ctx.purge(minutes=60)                       # remove handles older than 1 hour
ctx.delete(h["handle"])              # remove one handle
```
