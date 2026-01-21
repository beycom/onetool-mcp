# Context7

**Up-to-date docs for any library. Flexible key formats.**

Library documentation search and retrieval with extensive key normalization.

## Highlights

- Flexible library key formats (org/repo, shorthand names, GitHub URLs)
- Topic normalization for path-like topics and kebab-case
- Auto-resolution of shorthand names via search
- Mode suggestions when no content found

## Functions

| Function | Description |
|----------|-------------|
| `context7.search(query)` | Search for libraries by name |
| `context7.doc(library_key, ...)` | Fetch documentation for a library |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `library_key` | str | Library identifier - "vercel/next.js", "next.js", or GitHub URL |
| `topic` | str | Focus area (optional, default: general docs) |
| `mode` | str | "info" (default) for guides, "code" for API references |
| `page` | int | Pagination (1-10) |

## Requires

- `OT_CONTEXT7_API_KEY` environment variable

## Examples

```python
# Search for libraries
context7.search(query="react state management")

# Fetch docs with flexible key format
context7.doc(library_key="vercel/next.js", topic="routing")
context7.doc(library_key="next.js", mode="code")

# Use GitHub URL
context7.doc(library_key="https://github.com/vercel/next.js")
```

## Source

[Context7 API](https://context7.com/)

## Based on

[context7](https://github.com/upstash/context7) by Upstash (MIT)
