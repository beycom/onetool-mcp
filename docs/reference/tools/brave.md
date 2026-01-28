# Brave Search

**Five search types. Batch support. Query validation.**

Web, news, local, image, and video search via Brave Search API.

## Highlights

- Five search types: web, news, local, image, video
- Batch search with concurrent execution
- Query validation (400 char / 50 word limits)
- AI-generated summaries (Pro plan)

## Functions

| Function | Description |
|----------|-------------|
| `brave.search(query, ...)` | General web search |
| `brave.news(query, ...)` | News articles |
| `brave.local(query, ...)` | Local businesses/places |
| `brave.image(query, ...)` | Image search |
| `brave.video(query, ...)` | Video search |
| `brave.search_batch(queries, ...)` | Multiple searches concurrently |
| `brave.summarize(query, ...)` | AI-generated summary (Pro plan) |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (max 400 chars, 50 words) |
| `count` | int | Results per query (1-20) |
| `freshness` | str | "pd" (day), "pw" (week), "pm" (month), "py" (year) |
| `safesearch` | str | "off", "moderate", "strict" |

## Requires

- `BRAVE_API_KEY` in secrets.yaml

## Examples

```python
# Web search
brave.search(query="python async tutorial", count=10)

# News with freshness filter
brave.news(query="AI announcements", freshness="pw")

# Local search
brave.local(query="coffee shops near Times Square")

# Batch search
brave.search_batch(queries=["react hooks", "vue composition api"])

# AI summary (Pro plan)
brave.summarize(query="latest developments in quantum computing")
```

## Source

[Brave Search API](https://api.search.brave.com/app/documentation)
