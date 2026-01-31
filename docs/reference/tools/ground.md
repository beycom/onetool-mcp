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
| `query` | str | Search query (required, cannot be empty) |
| `context` | str | Additional context to refine search (search/batch only) |
| `focus` | str | "general", "code", "documentation", "troubleshooting" (search/batch only) |
| `model` | str | Gemini model to use, e.g., "gemini-2.5-pro" (search/batch) |
| `timeout` | float | Request timeout in seconds (default: 30.0) |
| `max_sources` | int | Maximum number of sources to include (default: unlimited) |
| `output_format` | str | "full" (default), "text_only", or "sources_only" |
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

# Get only sources (no text content)
ground.search(query="Python tutorials", output_format="sources_only")

# Limit sources and set timeout
ground.search(query="machine learning", max_sources=5, timeout=60.0)

# Batch search (multiple queries concurrently)
ground.search_batch(queries=["fastapi", "django", "flask"], focus="code")

# Batch with model and timeout
ground.search_batch(queries=["AI news", "ML trends"], model="gemini-3.0-flash", timeout=60.0)

# Developer resources search
ground.dev(query="async/await best practices", language="python")

# Documentation lookup
ground.docs(query="connection pooling", technology="postgresql")

# Reddit discussions
ground.reddit(query="best IDE for Python", subreddit="learnpython")
```

## Source

[Gemini API Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
