# Brave Search

Web, news, image, and video search via Brave Search API.

Short alias: `br`

## Highlights

- Four search types: web, news, image, video
- Batch search returns structured `results[]` + `meta`
- Batch retry controls with transient backoff (`retries`, `retry_delay_ms`)
- Query validation (400 char / 50 word limits)

## Functions

| Function | Description |
|----------|-------------|
| `brave.search(query, ...)` | General web search |
| `brave.news(query, ...)` | News articles (sorted by recency, most recent first) |
| `brave.image(query, ...)` | Image search |
| `brave.video(query, ...)` | Video search |
| `brave.search_batch(queries, ...)` | Multiple searches concurrently |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (max 400 chars, 50 words) |
| `max_results` | int | Results per query (1-20; all functions; default 10, 2 for search_batch) |
| `freshness` | str | "pd" (day), "pw" (week), "pm" (month), "py" (year), or "YYYY-MM-DDtoYYYY-MM-DD" date range |
| `safesearch` | str | "off", "moderate", "strict" |
| `output_format` | str | "full" (default), "text_only", or "sources_only" |
| `retries` | int | Batch mode only. Retry count for transient failures (non-negative, default: 0) |
| `retry_delay_ms` | int | Batch mode only. Base backoff delay in milliseconds (0-10000, default: 250) |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[util]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `secret` | `BRAVE_API_KEY` | Authenticate Brave Search API requests | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- `BRAVE_API_KEY` must be set in `secrets.yaml`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.brave.timeout` | float | `180.0` | Request timeout in seconds. Range: `1.0-300.0`. |

```yaml
tools:
  brave:
    timeout: 180.0
```

### Defaults

- If `tools.brave` is omitted, Brave uses the built-in timeout shown above.

## Examples

```python
# Web search
brave.search(query="python async tutorial", max_results=10)

# News with freshness filter
brave.news(query="AI announcements", freshness="pw")

# Text only output
brave.search(query="python async tutorial", output_format="text_only")

# Batch search
brave.search_batch(queries=["react hooks", "vue composition api"])

# Batch search with retry controls
brave.search_batch(
    queries=["q1", "q2"],
    retries=1,
    retry_delay_ms=200,
)
```

`search_batch()` now returns a structured envelope:
- `results[i].label`, `results[i].query`, `results[i].status`, `results[i].data`, `results[i].error`
- `results[i].attempts`, `results[i].retried`, `results[i].final_failure`
- `meta.query_count`, `meta.success_count`, `meta.error_count`, `meta.partial_success`
