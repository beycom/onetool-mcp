# Web Fetch

**Clean content from any URL. No noise.**

Extracts main content from web pages, filtering navigation, ads, and boilerplate.

## Highlights

- Clean content extraction filtering navigation and ads
- Multiple output formats (markdown, text, json)
- Batch processing with concurrent execution
- Output truncation with max_length parameter
- URL validation with helpful error messages
- JSON-structured errors when using json output format
- Optional HTTP response metadata

## Functions

| Function | Description |
|----------|-------------|
| `web.fetch(url, ...)` | Fetch and extract content from a URL |
| `web.fetch_batch(urls, ...)` | Fetch multiple URLs concurrently |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | URL to fetch content from |
| `output_format` | str | "markdown" (default), "text", "json" |
| `include_links` | bool | Include links in output |
| `include_images` | bool | Include image references |
| `include_tables` | bool | Include tables in output (default: True) |
| `include_comments` | bool | Include comments section |
| `include_formatting` | bool | Preserve headers/lists (default: True) |
| `include_metadata` | bool | Include HTTP metadata in JSON output |
| `favor_precision` | bool | Prefer accuracy over completeness |
| `favor_recall` | bool | Prefer completeness over accuracy |
| `fast` | bool | Skip fallback extraction for speed |
| `target_language` | str | Filter by ISO 639-1 language code |
| `max_length` | int | Truncate output to this length |
| `use_cache` | bool | Use cached pages (default: True) |

Note: `favor_precision` and `favor_recall` are mutually exclusive.

## Examples

```python
# Fetch single URL
web.fetch(url="https://example.com/article")

# Fetch with markdown output
web.fetch(url="https://docs.python.org/3/tutorial/", output_format="markdown")

# Fast mode without fallback
web.fetch(url="https://example.com/page", fast=True)

# JSON output with metadata
web.fetch(
    url="https://example.com/article",
    output_format="json",
    include_metadata=True
)

# Precision mode for cleaner extraction
web.fetch(url="https://example.com/page", favor_precision=True)

# Batch fetch multiple URLs
web.fetch_batch(urls=[
    "https://example.com/page1",
    "https://example.com/page2"
])

# Batch with all options
web.fetch_batch(
    urls=["https://example.com/page1", "https://example.com/page2"],
    include_links=True,
    favor_precision=True,
    fast=True
)
```

## Source

[trafilatura](https://trafilatura.readthedocs.io/)
