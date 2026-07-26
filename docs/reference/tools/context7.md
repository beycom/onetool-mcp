# Context7

Library documentation search and retrieval. Uses Context7 v2 API with semantic reranking.

Short alias: `c7`

## Highlights

- Flexible library ID formats (org/repo, shorthand names, GitHub URLs)
- Semantic reranking — query drives relevance, not just keyword match
- Smart auto-resolution of shorthand names via scored library search
- Version-aware ID support (e.g. `/vercel/next.js/v14`)

## Functions

| Function | Description |
|----------|-------------|
| `context7.search(query, library_name, ...)` | Search for libraries by name |
| `context7.doc(library_id, query)` | Fetch semantically-reranked docs for a library |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Your task or question — used for LLM relevance ranking (e.g. "How do I set up JWT auth?") |
| `library_name` | str | The library to find in `search()` (e.g. `"express"`, `"react"`, `"fastapi"`) |
| `library_id` | str | Library identifier for `doc()` — flexible formats accepted (see below) |
| `output_format` | str | `"str"` (default) for formatted string, `"dict"` for raw API JSON |

**Accepted `library_id` formats:**

| Format | Example |
|--------|---------|
| Context7 path | `/vercel/next.js` |
| With version | `/vercel/next.js/v14.3.0-canary.87` |
| Without leading slash | `vercel/next.js` |
| Shorthand | `next.js`, `nextjs`, `react` |
| GitHub URL | `https://github.com/vercel/next.js` |

When a shorthand is given, Context7 resolves it via a search call. A note is prepended to the result if resolution occurred: `[Resolved 'nextjs' → '/vercel/next.js']`.

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[dev]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `secret` | `CONTEXT7_API_KEY` | Authenticate Context7 documentation API requests | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- `CONTEXT7_API_KEY` must be set in `secrets.yaml`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.context7.timeout` | float | `30.0` | Request timeout in seconds. Range: `1.0-120.0`. |

```yaml
tools:
  context7:
    timeout: 30.0
```

### Defaults

- If `tools.context7` is omitted, Context7 uses the built-in timeout shown above.

## Examples

```python
# Search for libraries matching a name
context7.search(query="How do I set up JWT auth?", library_name="express")
context7.search(query="react hooks tutorial", library_name="react")

# Raw dict output for programmatic use
context7.search(query="fastapi", library_name="fastapi", output_format="dict")

# Fetch docs with semantic reranking
context7.doc(library_id="/vercel/next.js", query="How do I configure middleware for JWT?")
context7.doc(library_id="react", query="useEffect cleanup")

# Use GitHub URL
context7.doc(library_id="https://github.com/vercel/next.js", query="app router setup")

# Version-specific docs
context7.doc(library_id="/vercel/next.js/v14", query="app router migration")
```

## Typical Workflow

```python
# 1. Find the library ID
context7.search(query="django rest framework", library_name="djangorestframework")

# 2. Fetch docs using the ID from search results
context7.doc(library_id="/encode/django-rest-framework", query="serializer validation")
```
