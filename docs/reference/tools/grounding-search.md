# Grounding Search

**Google-backed answers. Real-time data. Source citations.**

Web search with Google's grounding capabilities via Gemini API. Provides current information with source citations.

## Highlights

- Real-time web search with Google grounding
- Automatic source citations with numbered references
- Specialized searches for dev resources, docs, and Reddit
- URL deduplication in results

## Functions

| Function | Description |
|----------|-------------|
| `ground.search(query, ...)` | General grounded web search |
| `ground.search_batch(queries, ...)` | Multiple searches concurrently |
| `ground.dev(query, ...)` | Developer resources (GitHub, Stack Overflow, docs) |
| `ground.docs(query, ...)` | Official documentation lookup |
| `ground.reddit(query, ...)` | Reddit discussions and community insights |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query |
| `context` | str | Additional context to refine search (search only) |
| `focus` | str | "general", "code", "documentation", "troubleshooting" (search only) |
| `model` | str | Gemini model to use, e.g., "gemini-2.5-pro" (search only) |
| `language` | str | Filter for dev search |
| `framework` | str | Filter for dev search |
| `technology` | str | Filter for docs search |
| `subreddit` | str | Filter for reddit search |

## Requires

- `GEMINI_API_KEY` in secrets.yaml

## Examples

```python
# General search with context
ground.search(query="kubernetes pod restart policy", focus="code")

# Use a specific model
ground.search(query="latest AI news", model="gemini-3.0-flash")

# Batch search (multiple queries concurrently)
ground.search_batch(queries=["fastapi", "django", "flask"], focus="code")

# Developer resources search
ground.dev(query="async/await best practices", language="python")

# Documentation lookup
ground.docs(query="connection pooling", technology="postgresql")

# Reddit discussions
ground.reddit(query="best IDE for Python", subreddit="learnpython")
```

## Source

[Gemini API Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
