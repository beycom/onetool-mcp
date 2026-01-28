# Web Fetch

**Clean content from any URL. No noise.**

Extracts main content from web pages, filtering navigation, ads, and boilerplate.

## Highlights

- Clean content extraction filtering navigation and ads
- Multiple output formats (markdown, text, json)
- Batch processing with concurrent execution
- Output truncation with max_length parameter

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
| `include_tables` | bool | Include tables in output |
| `include_formatting` | bool | Preserve headers/lists (default: True) |
| `fast` | bool | Skip fallback extraction for speed |
| `max_length` | int | Truncate output to this length |

## Examples

```python
# Fetch single URL
web.fetch(url="https://example.com/article")

# Fetch with markdown output
web.fetch(url="https://docs.python.org/3/tutorial/", output_format="markdown")

# Fast mode without fallback
web.fetch(url="https://example.com/page", fast=True)

# Batch fetch multiple URLs
web.fetch_batch(urls=[
    "https://example.com/page1",
    "https://example.com/page2"
])
```

## Source

[trafilatura](https://trafilatura.readthedocs.io/)
