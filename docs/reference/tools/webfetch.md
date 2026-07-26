# Webfetch

Extracts main content from web pages, filtering navigation, ads, and boilerplate.

Short alias: `wf`

## Highlights

- Clean content extraction filtering navigation and ads
- Multiple output formats (markdown, text, json)
- Batch processing with concurrent execution
- Non-HTML content (plain text, JSON, XML, CSV) returned directly without extraction

## Functions

| Function | Description |
|----------|-------------|
| `webfetch.fetch(url, ...)` | Fetch and extract content from a URL |
| `webfetch.fetch_batch(urls, ...)` | Fetch multiple URLs concurrently |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | URL to fetch content from |
| `output_format` | str | "markdown" (default), "text", "json", "html" |
| `include_links` | bool | Include links in output |
| `include_images` | bool | Include image references |
| `include_tables` | bool | Include tables in output (default: True) |
| `include_comments` | bool | Include comments section |
| `include_formatting` | bool | Preserve headers/lists (default: True) |
| `include_metadata` | bool | Include HTTP and extracted article metadata in JSON output |
| `favor_precision` | bool | Prefer accuracy over completeness |
| `favor_recall` | bool | Prefer completeness over accuracy |
| `fast` | bool | Skip fallback extraction for speed |
| `target_language` | str | Filter by ISO 639-1 language code |
| `max_length` | int | Truncate extracted output to this many characters; this is not the download-size limit |
| `timeout` | float | Request timeout in seconds (defaults to config) |
| `use_cache` | bool | Use cached pages (default: True) |

Note: `favor_precision` and `favor_recall` are mutually exclusive.

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[dev]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `lib` | `trafilatura` (import `trafilatura`, OneTool `[dev]`) | Download and extract useful content from web pages | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- No required `tools.webfetch` settings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.webfetch.timeout` | float | `30.0` | Request timeout in seconds. Range: `1.0-120.0`. |
| `tools.webfetch.max_length` | int | `50000` | Max extracted content length in characters. Range: `1000-500000`. |
| `tools.webfetch.max_download_bytes` | int | `20000000` | Reject larger responses before extraction. Minimum: `100000`. |
| `tools.webfetch.block_private_urls` | bool | `false` | Best-effort refusal of private, loopback, link-local, and reserved destinations. |

```yaml
tools:
  webfetch:
    timeout: 30.0
    max_length: 50000
    max_download_bytes: 20000000
    block_private_urls: false
```

### Defaults

- If `tools.webfetch` is omitted, web fetch uses all four defaults shown above.
- `max_download_bytes` is enforced before extraction; `max_length` truncates the
  extracted result afterward.

## Examples

```python
# Fetch single URL
webfetch.fetch(url="https://docs.python.org/3/library/json.html")

# Fetch with markdown output
webfetch.fetch(url="https://docs.python.org/3/tutorial/", output_format="markdown")

# Fast mode without fallback
webfetch.fetch(url="https://fastapi.tiangolo.com/tutorial/", fast=True)

# JSON output with metadata
webfetch.fetch(
    url="https://docs.astral.sh/uv/getting-started/",
    output_format="json",
    include_metadata=True
)

# Precision mode for cleaner extraction
webfetch.fetch(url="https://pydantic-docs.helpmanual.io/concepts/models/", favor_precision=True)

# Batch fetch multiple URLs
webfetch.fetch_batch(urls=[
    "https://docs.python.org/3/library/asyncio.html",
    "https://fastapi.tiangolo.com/tutorial/first-steps/"
])

# Batch with all options
webfetch.fetch_batch(
    urls=["https://docs.python.org/3/library/typing.html", "https://docs.pydantic.dev/latest/"],
    include_links=True,
    favor_precision=True,
    fast=True
)

# Fetch plain text or JSON files (returned directly without extraction)
webfetch.fetch(url="https://pypi.org/pypi/requests/json")
webfetch.fetch(url="https://docs.python.org/robots.txt")
```

When `include_metadata=True` with `output_format="json"`, metadata includes:
- transport fields: `final_url`, `content_type`
- extracted fields when available: `title`, `author`, `date`

Loopback note:
- `http://127.0.0.1/...`, `http://localhost/...`, and `http://[::1]/...` may be blocked in some runtimes.
- Failures now return an explicit loopback-oriented message with alternatives.

## Based on

This tool is based on [trafilatura](https://github.com/adbar/trafilatura)
by Adrien Barbaresi, licensed under Apache 2.0.
