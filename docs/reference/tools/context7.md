# Context7

**Up-to-date docs for any library. Flexible key formats.**

Library documentation search and retrieval with extensive key normalization.

## Highlights

- Flexible library key formats (org/repo, shorthand names, GitHub URLs)
- Topic normalization for path-like topics and kebab-case
- Auto-resolution of shorthand names via search with smart scoring
- Mode and doc_type validation with helpful error messages
- Version-specific documentation support

## Functions

| Function | Description |
|----------|-------------|
| `context7.search(query, format)` | Search for libraries by name |
| `context7.doc(library_key, ...)` | Fetch documentation for a library |

## Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (e.g., "react", "fastapi") |
| `output_format` | str | "str" (default) for string, "dict" for raw API response |

## Doc Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `library_key` | str | Library identifier - "vercel/next.js", "next.js", or GitHub URL |
| `topic` | str | Focus area (optional, default: general docs) |
| `mode` | str | "info" (default) for guides, "code" for API references |
| `page` | int | Pagination (1-10) |
| `doc_type` | str | "txt" (default) or "json" |
| `version` | str | Optional version suffix (e.g., "v14", "14.0.0") |

## Requires

- `CONTEXT7_API_KEY` in secrets.yaml

## Examples

```python
# Search for libraries
context7.search(query="react state management")

# Get raw dict response for programmatic use
context7.search(query="flask", output_format="dict")

# Fetch docs with flexible key format
context7.doc(library_key="vercel/next.js", topic="routing")
context7.doc(library_key="next.js", mode="code")

# Use GitHub URL
context7.doc(library_key="https://github.com/vercel/next.js")

# Get version-specific documentation
context7.doc(library_key="vercel/next.js", topic="app router", version="v14")
```

## Source

[Context7 API](https://context7.com/)

## Based on

[context7](https://github.com/upstash/context7) by Upstash (MIT)
