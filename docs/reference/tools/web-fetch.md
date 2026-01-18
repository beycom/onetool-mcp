# Web Fetch

**Clean content from any URL. No noise.**

Extracts main content from web pages, filtering navigation, ads, and boilerplate.

| Function | Description |
|----------|-------------|
| `web.fetch(url, ...)` | Fetch and extract content from a URL |
| `web.fetch_batch(urls, ...)` | Fetch multiple URLs concurrently |

**Key Parameters:**
- `output_format`: "markdown" (default), "text", "json"
- `include_links`, `include_images`, `include_tables`: Content inclusion
- `include_formatting`: Preserve headers/lists (default: True)
- `fast`: Skip fallback extraction for speed

**Based on:** [trafilatura](https://github.com/adbar/trafilatura)

**Differences from upstream:**
- Simplified API with sensible defaults
- Batch processing with ThreadPoolExecutor
- Output truncation with `max_length` parameter

**Comparison:** No standard MCP exists for web fetch; this is a trafilatura-based implementation with batch support and format options.

**License:** Apache 2.0 ([LICENSE](../licenses/trafilatura-LICENSE))
