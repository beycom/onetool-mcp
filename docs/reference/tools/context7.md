# Context7

**Up-to-date docs for any library. Flexible key formats.**

Library documentation search and retrieval.

| Function | Description |
|----------|-------------|
| `search(query)` | Search for libraries by name |
| `doc(library_key, ...)` | Fetch documentation for a library |

**Key Parameters:**
- `library_key`: Flexible format - "vercel/next.js", "next.js", GitHub URL
- `topic`: Focus area (optional, default: general docs)
- `mode`: "info" (default) for guides, "code" for API references
- `page`: Pagination (1-10)

**Requires:** `OT_CONTEXT7_API_KEY` environment variable

**Based on:** [context7](https://github.com/upstash/context7)

**Differences from upstream:**
- Extensive library key normalization (handles URLs, versions, quotes)
- Topic normalization (path-like topics, kebab-case)
- Auto-resolution of shorthand names via search
- Helpful "no content" message suggesting alternate mode

**Comparison:** Original MCP requires strict key format. OneTool adds library key normalization (URLs, versions), topic normalization, and mode suggestions.

**License:** MIT ([LICENSE](../../../licenses/context7-LICENSE))
