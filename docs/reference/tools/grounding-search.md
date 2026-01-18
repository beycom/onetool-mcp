# Grounding Search

**Google-backed answers. Real-time data. Source citations.**

Web search with Google's grounding capabilities via Gemini API. Provides current information with source citations.

| Function | Description |
|----------|-------------|
| `ground.search(query, ...)` | General grounded web search |
| `ground.dev(query, ...)` | Developer resources (GitHub, Stack Overflow, docs) |
| `ground.docs(query, ...)` | Official documentation lookup |
| `ground.reddit(query, ...)` | Reddit discussions and community insights |

**Key Parameters:**
- `query`: Search query
- `context`: Additional context to refine search (search only)
- `focus`: "general", "code", "documentation", "troubleshooting" (search only)
- `language`, `framework`: Filter for dev search
- `technology`: Filter for docs search
- `subreddit`: Filter for reddit search

**Requires:** `OT_GEMINI_API_KEY` environment variable

**Based on:** [Gemini API Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)

**Implementation notes:**
- Uses `google-genai` SDK with `GoogleSearch` tool
- Returns content with `## Sources` section containing numbered citations
- Deduplicates source URLs automatically

**Comparison:** Original implementation using Gemini's grounding feature. Not available via OpenRouter.

**License:** MIT
