# Tavily Search

AI-powered web search and URL content extraction via Tavily API. Optimized for LLM applications with clean, relevant results.

Short alias: `tav`

## Highlights

- AI-synthesised answer + numbered results + sources in one call
- Three topic modes: general, news, finance
- Batch search returns structured `results[]` + `meta`, with retry metadata
- Batch search and batch extraction with concurrent execution
- Deep research via async polling (`research()`)
- Schema-constrained extraction mode with optional field provenance

## Functions

| Function | Description |
|----------|-------------|
| `tavily.search(query, ...)` | AI-powered web search |
| `tavily.search_batch(queries, ...)` | Multiple searches concurrently |
| `tavily.extract(urls, ...)` | Extract raw content from URLs |
| `tavily.extract_batch(url_sets, ...)` | Extract from multiple URL sets concurrently |
| `tavily.research(input, ...)` | Deep multi-source research with async polling |

## Key Parameters

### search / search_batch

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (required, cannot be empty) |
| `max_results` | int | Results per query (1-20, default: 5 for search, 2 for batch) |
| `search_depth` | str | `"basic"` (1 credit, faster) or `"advanced"` (2 credits, default: `"basic"`) |
| `topic` | str | `"general"`, `"news"`, or `"finance"` (default: `"general"`) |
| `output_format` | str | `"full"` (answer + results + sources), `"text_only"` (answer only), `"sources_only"` (URL list only). Default: `"full"` |
| `min_score` | float | Minimum Tavily relevance score to include (0.0–1.0, default: `None`) |
| `time_range` | str | `"day"`, `"week"`, `"month"`, or `"year"` (default: `None`) |
| `days` | int | For news topic, how many days back to search (1-30, default: 3) |
| `include_domains` | list[str] | Restrict results to these domains |
| `exclude_domains` | list[str] | Exclude results from these domains |
| `retries` | int | Batch mode only. Retry count for transient failures (default: 0) |
| `retry_delay_ms` | int | Batch mode only. Base backoff delay in milliseconds (default: 250) |
| `extract_schema` | dict | Optional schema-constrained extraction mode for search/search_batch |
| `return_provenance` | bool | Include per-field provenance (`source_url`, `snippet`, `confidence`) |

### extract / extract_batch

| Parameter | Type | Description |
|-----------|------|-------------|
| `urls` | list[str] | URLs to extract content from (required, non-empty) |
| `format` | str | `"markdown"` (default) or `"text"` |
| `extract_depth` | str | `"basic"` (1 credit/5 URLs) or `"advanced"` (2 credits/5 URLs, default: `"basic"`) |
| `url_sets` | list | For `extract_batch`: list of URL lists or `(url_list, label)` tuples |

### research

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | str | Research question or task (required, cannot be empty) |
| `model` | str | `"mini"` (5 credits), `"pro"` (20 credits), `"auto"` (default) |
| `timeout_seconds` | int | Max seconds to wait for completion (default: 300) |

## Requires

- `TAVILY_API_KEY` in secrets.yaml

## Configuration

### Required

- `TAVILY_API_KEY` must be set in `secrets.yaml`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.tavily.timeout` | float | `60.0` | Request timeout in seconds. Range: `1.0-300.0`. |

```yaml
tools:
  tavily:
    timeout: 60.0
```

### Defaults

- If `tools.tavily` is omitted, Tavily uses the built-in timeout shown above.

## Examples

```python
# Basic web search — AI answer + results + sources
tavily.search(query="Python asyncio best practices")

# AI answer only
tavily.search(query="what is uv package manager", output_format="text_only")

# Sources list only
tavily.search(query="FastAPI documentation", output_format="sources_only")

# News search, recent results, filter by relevance score
tavily.search(query="latest AI model releases", topic="news",
              time_range="week", min_score=0.7)

# Finance search with domain filter
tavily.search(query="Apple earnings Q1 2025", topic="finance",
              include_domains=["reuters.com", "bloomberg.com"])

# Extract content from a URL
tavily.extract(urls=["https://docs.python.org/3/library/asyncio.html"])

# Extract from multiple URLs (failed URLs listed separately)
tavily.extract(urls=[
    "https://fastapi.tiangolo.com/",
    "https://pydantic-docs.helpmanual.io/",
])

# Batch extraction with labels
tavily.extract_batch(url_sets=[
    (["https://docs.astral.sh/uv/"], "uv Docs"),
    (["https://docs.pydantic.dev/"], "Pydantic Docs"),
])

# Batch search (concurrent execution)
tavily.search_batch(queries=["sqlalchemy 2.0", "pydantic v2", "httpx async"])

# Batch with custom labels and sources only
tavily.search_batch(queries=[
    ("Python 3.13 new features", "Python 3.13"),
    ("uv python package manager", "uv"),
], output_format="sources_only")

# Batch with retry controls
tavily.search_batch(queries=["q1", "q2"], retries=1, retry_delay_ms=200)

# Schema-constrained extraction with provenance
tavily.search(
    query="Find contact details",
    extract_schema={
        "fields": [
            {"name": "name", "type": "string", "required": True},
            {"name": "email", "type": "string", "required": True},
        ]
    },
    return_provenance=True,
)

# Deep research (async polling, may take minutes)
tavily.research(input="How does Rust's borrow checker work?")
tavily.research(input="State of LLM context scaling 2025", model="pro", timeout_seconds=600)
```
