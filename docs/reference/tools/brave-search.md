# Brave Search

**Five search types. Batch support. Query validation.**

Web, news, local, image, and video search via Brave Search API.

| Function | Description |
|----------|-------------|
| `brave.search(query, ...)` | General web search |
| `brave.news(query, ...)` | News articles |
| `brave.local(query, ...)` | Local businesses/places |
| `brave.image(query, ...)` | Image search |
| `brave.video(query, ...)` | Video search |
| `brave.search_batch(queries, ...)` | Multiple searches concurrently |
| `brave.summarize(query, ...)` | AI-generated summary (Pro plan) |

**Key Parameters:**
- `count`: Results per query (1-20)
- `freshness`: "pd" (day), "pw" (week), "pm" (month), "py" (year)
- `safesearch`: "off", "moderate", "strict"

**Requires:** `OT_BRAVE_API_KEY` environment variable

**Based on:** [brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server)

**Differences from upstream:**
- Query validation (400 char / 50 word limits)
- Batch search with concurrent execution
- Simplified local search (uses web endpoint with locations filter)

**Comparison:** Original MCP has no validation and single queries only. OneTool adds query validation (400 char/50 word), batch search, and all search types unified.

**License:** MIT ([LICENSE](../licenses/brave-search-mcp-server-LICENSE))
