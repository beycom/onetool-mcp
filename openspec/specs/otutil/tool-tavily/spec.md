# tool-tavily Specification

## Purpose

Provides AI-powered web search, URL content extraction, and deep research via the Tavily API. Optimized for LLM applications. Requires `TAVILY_API_KEY` secret in secrets.yaml.

## Requirements

### Requirement: Web Search

The `tavily.search()` function SHALL search the web using the Tavily AI search API.

#### Scenario: Basic search
- **GIVEN** a search query
- **WHEN** `tavily.search(query=query)` is called
- **THEN** it SHALL return an AI-synthesised answer followed by numbered results with titles, URLs, and content snippets, plus a Sources section

#### Scenario: Output format — full (default)
- **WHEN** `tavily.search(query=query, output_format="full")` is called
- **THEN** it SHALL return the AI answer, numbered results, a `## Sources` section, and credit usage note

#### Scenario: Output format — text only
- **WHEN** `tavily.search(query=query, output_format="text_only")` is called
- **THEN** it SHALL return only the AI-synthesised answer text

#### Scenario: Output format — sources only
- **WHEN** `tavily.search(query=query, output_format="sources_only")` is called
- **THEN** it SHALL return only a numbered deduplicated list of source URLs with titles

#### Scenario: Invalid output format
- **WHEN** `tavily.search(query=query, output_format="xml")` is called
- **THEN** it SHALL return an error indicating valid values are "full", "text_only", "sources_only"

#### Scenario: Score filtering
- **WHEN** `tavily.search(query=query, min_score=0.5)` is called
- **THEN** it SHALL exclude results with Tavily relevance score below 0.5

#### Scenario: Result count control
- **GIVEN** a search query and max_results parameter
- **WHEN** `tavily.search(query=query, max_results=5)` is called
- **THEN** it SHALL return up to 5 results
- **AND** max_results MUST be in range 1-20; values outside this range SHALL return an error

#### Scenario: Search depth
- **WHEN** `tavily.search(query=query, search_depth="advanced")` is called
- **THEN** it SHALL use advanced search for more thorough results
- **AND** valid values are "basic" (1 credit, default) and "advanced" (2 credits)
- **AND** invalid search_depth values SHALL return an error message

#### Scenario: Topic selection
- **WHEN** `tavily.search(query=query, topic="news")` is called
- **THEN** it SHALL return results optimized for that topic
- **AND** valid values are "general" (default), "news", "finance"
- **AND** invalid topic values SHALL return an error message

#### Scenario: Time range filter
- **WHEN** `tavily.search(query=query, time_range="week")` is called
- **THEN** it SHALL return results from the past week
- **AND** valid values are "day", "week", "month", "year"
- **AND** invalid time_range values SHALL return an error message

#### Scenario: Days filter for news
- **WHEN** `tavily.search(query=query, topic="news", days=7)` is called
- **THEN** it SHALL return news from the past 7 days
- **AND** days MUST be in range 1-30; values outside this range SHALL return an error

#### Scenario: Domain filters
- **WHEN** `tavily.search(query=query, include_domains=["bbc.com"], exclude_domains=["spam.com"])` is called
- **THEN** results SHALL only include domains from include_domains
- **AND** results SHALL exclude domains from exclude_domains

#### Scenario: Missing API key
- **GIVEN** no TAVILY_API_KEY is configured
- **WHEN** any Tavily function is called
- **THEN** it SHALL return an error message mentioning TAVILY_API_KEY

### Requirement: Batch Search

The `tavily.search_batch()` function SHALL execute multiple searches concurrently.

#### Scenario: String queries
- **WHEN** `tavily.search_batch(queries=["query1", "query2"])` is called
- **THEN** it SHALL return combined results labelled by query, with `=== Label ===` section headers

#### Scenario: Tuple queries with custom labels
- **WHEN** `tavily.search_batch(queries=[("long query", "Short Label")])` is called
- **THEN** results SHALL use the custom label

#### Scenario: Empty label fallback
- **WHEN** `tavily.search_batch(queries=[("query", "")])` is called
- **THEN** the section header SHALL use the query text as the label

#### Scenario: Empty queries list
- **WHEN** `tavily.search_batch(queries=[])` is called
- **THEN** it SHALL return an error message

#### Scenario: Parallel execution
- **GIVEN** multiple queries
- **WHEN** `tavily.search_batch(queries=[...])` is called
- **THEN** queries SHALL be executed in parallel using threads

#### Scenario: Shared parameters forwarded
- **WHEN** `tavily.search_batch(queries=queries, output_format="sources_only", min_score=0.5)` is called
- **THEN** it SHALL forward those parameters to each individual `tavily.search()` call

#### Scenario: Batch retry guardrails
- **WHEN** `tavily.search_batch()` is called with retry controls
- **THEN** `retries` MUST be an integer in range 0-3
- **AND** `retry_delay_ms` MUST be in range 0-10000
- **AND** values outside these ranges SHALL return an error before batch work starts

### Requirement: URL Content Extraction

The `tavily.extract()` function SHALL extract raw textual content from URLs.

#### Scenario: Single URL extraction
- **WHEN** `tavily.extract(urls=["https://docs.python.org/3/"])` is called
- **THEN** it SHALL return the raw content of that URL

#### Scenario: Multiple URL extraction
- **WHEN** `tavily.extract(urls=[...])` is called
- **THEN** it SHALL return content for each URL

#### Scenario: Extraction depth
- **WHEN** `tavily.extract(urls=urls, extract_depth="advanced")` is called
- **THEN** it SHALL perform deeper extraction
- **AND** valid values are "basic" (default) and "advanced"

#### Scenario: Failed extractions
- **GIVEN** a URL that cannot be extracted
- **WHEN** `tavily.extract(urls=["https://bad.url"])` is called
- **THEN** the output SHALL include a "Failed (N):" section listing failed URLs and their errors

#### Scenario: Empty URLs list
- **WHEN** `tavily.extract(urls=[])` is called
- **THEN** it SHALL return an error message

### Requirement: Batch Extraction

The `tavily.extract_batch()` function SHALL extract content from multiple URL sets concurrently.

#### Scenario: Concurrent extraction
- **WHEN** `tavily.extract_batch(url_sets=[["url1", "url2"], ["url3"]])` is called
- **THEN** it SHALL execute extractions for each URL set in parallel and return combined labelled results

#### Scenario: Labeled extraction sets
- **WHEN** `tavily.extract_batch(url_sets=[(["url1"], "Docs"), (["url2"], "Blog")])` is called
- **THEN** each section SHALL use the provided label

#### Scenario: Empty url_sets validation
- **WHEN** `tavily.extract_batch(url_sets=[])` is called
- **THEN** it SHALL return an error message

#### Scenario: Empty inner URL list
- **WHEN** a URL set contains an empty list
- **THEN** it SHALL return an error message before executing any requests

### Requirement: Deep Research

The `tavily.research()` function SHALL perform comprehensive multi-source research via synchronous polling.

#### Scenario: Basic research
- **WHEN** `tavily.research(input="How does FastAPI compare to Flask?")` is called
- **THEN** it SHALL return a detailed research report synthesised from multiple sources

#### Scenario: Model selection
- **WHEN** `tavily.research(input=task, model="pro")` is called
- **THEN** it SHALL use the "pro" model for broader, deeper research
- **AND** valid values are "mini" (5 credits), "pro" (20 credits), "auto" (default)
- **AND** invalid model values SHALL return an error

#### Scenario: Configurable timeout
- **WHEN** `tavily.research(input=task, timeout_seconds=600)` is called
- **THEN** it SHALL wait up to 600 seconds before returning a timeout error
- **AND** `timeout_seconds` MUST be in range 10-1800

#### Scenario: Timeout exceeded
- **GIVEN** the research task does not complete within the timeout
- **THEN** it SHALL return `"Error: research timed out after {N} seconds"`

#### Scenario: Polling respects remaining deadline
- **WHEN** Tavily research polling waits and sends status GET requests
- **THEN** each sleep SHALL be clamped to the remaining timeout budget
- **AND** each polling GET request SHALL pass a timeout based on the remaining budget

#### Scenario: Empty input validation
- **WHEN** `tavily.research(input="")` is called
- **THEN** it SHALL return `"Error: input cannot be empty"`

## Validation Rules

| Parameter | Valid Values | Error on |
|-----------|-------------|----------|
| `query` | Non-empty string | Empty string or whitespace-only |
| `max_results` | 1-20 | Outside range |
| `search_depth` | "basic", "advanced" | Any other value |
| `topic` | "general", "news", "finance" | Any other value |
| `output_format` | "full", "text_only", "sources_only" | Any other value |
| `min_score` | float or None | — |
| `time_range` | None, "day", "week", "month", "year" | Any other non-None value |
| `days` | 1-30 | Outside range |
| `urls` | Non-empty list | Empty list |
| `format` | "markdown", "text" | Any other value |
| `extract_depth` | "basic", "advanced" | Any other value |
| `model` | "mini", "pro", "auto" | Any other value |
| `timeout_seconds` | 10-1800 | Outside range |

## Logging

HTTP requests SHALL be logged with `LogSpan(span="tavily.request", ...)`.
Search operations SHALL be logged with `LogSpan(span="tavily.search", query, depth, resultCount, credits)`.
Batch search/extract operations SHALL be logged with `LogSpan(span="tavily.batch", ...)`.
URL extractions SHALL be logged with `LogSpan(span="tavily.extract", ...)`.
Research tasks SHALL be logged with `LogSpan(span="tavily.research", model, elapsed)`.
