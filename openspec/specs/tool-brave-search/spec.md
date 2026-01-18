# tool-brave-search Specification

## Purpose

Provides web search, news search, local search, image search, video search, and AI summarization via the Brave Search API. Requires `OT_BRAVE_API_KEY` environment variable.
## Requirements
### Requirement: Web Search

The `brave.search()` function SHALL search the web using Brave Search API.

#### Scenario: Basic search
- **GIVEN** a search query
- **WHEN** `brave.search(query=query)` is called
- **THEN** it SHALL return formatted search results with titles, URLs, and descriptions

#### Scenario: Result count control
- **GIVEN** a search query and count parameter
- **WHEN** `brave.search(query=query, count=5)` is called
- **THEN** it SHALL return up to 5 results
- **AND** count SHALL be clamped to range 1-20

#### Scenario: Pagination
- **GIVEN** a search query and offset parameter
- **WHEN** `brave.search(query=query, offset=1)` is called
- **THEN** it SHALL return results starting from the second page
- **AND** offset SHALL be clamped to range 0-9

#### Scenario: Freshness filter
- **GIVEN** a search query and freshness parameter
- **WHEN** `brave.search(query=query, freshness="pd")` is called
- **THEN** it SHALL return results from the past day
- **AND** valid values are "pd" (day), "pw" (week), "pm" (month), "py" (year)

#### Scenario: Safe search
- **GIVEN** a search query and safesearch parameter
- **WHEN** `brave.search(query=query, safesearch="strict")` is called
- **THEN** it SHALL filter adult content strictly
- **AND** valid values are "off", "moderate" (default), "strict"

### Requirement: News Search

The `brave.news()` function SHALL search news articles.

#### Scenario: News search
- **GIVEN** a news query
- **WHEN** `brave.news(query=query)` is called
- **THEN** it SHALL return news results with titles, sources, and ages
- **AND** it SHALL mark breaking news with "[BREAKING]" prefix

#### Scenario: News freshness
- **GIVEN** a news query
- **WHEN** `brave.news(query=query, freshness="pd")` is called
- **THEN** it SHALL return news from the past day
- **AND** valid values are "pd", "pw", "pm"

### Requirement: Local Search

The `brave.local()` function SHALL search for local businesses and places.

#### Scenario: Local business search
- **GIVEN** a local query like "pizza near Central Park"
- **WHEN** `brave.local(query=query)` is called
- **THEN** it SHALL return location results if available
- **AND** results SHALL include addresses, ratings, and phone numbers

#### Scenario: Fallback to web
- **GIVEN** a query with no local results
- **WHEN** `brave.local(query=query)` is called
- **THEN** it SHALL fall back to web search results

### Requirement: Image Search

The `brave.image()` function SHALL search for images.

#### Scenario: Image search
- **GIVEN** an image query
- **WHEN** `brave.image(query=query)` is called
- **THEN** it SHALL return image results with URLs, sizes, and sources

#### Scenario: Image safe search
- **GIVEN** an image query
- **WHEN** `brave.image(query=query, safesearch="off")` is called
- **THEN** it SHALL disable content filtering
- **AND** default is "strict"

### Requirement: Video Search

The `brave.video()` function SHALL search for videos.

#### Scenario: Video search
- **GIVEN** a video query
- **WHEN** `brave.video(query=query)` is called
- **THEN** it SHALL return video results with titles, channels, durations, and URLs

#### Scenario: Video descriptions
- **GIVEN** a video with long description
- **WHEN** results are formatted
- **THEN** descriptions SHALL be truncated to 150 characters

### Requirement: Batch Search

The `brave.search_batch()` function SHALL execute multiple searches concurrently.

#### Scenario: Simple batch
- **GIVEN** a list of query strings
- **WHEN** `brave.search_batch(queries=["q1", "q2"])` is called
- **THEN** it SHALL execute searches in parallel
- **AND** it SHALL return combined results with labels

#### Scenario: Labeled batch
- **GIVEN** a list of (query, label) tuples
- **WHEN** `brave.search_batch(queries=[("gold price", "Gold")])` is called
- **THEN** each section SHALL use the provided label

### Requirement: AI Summarizer

The `brave.summarize()` function SHALL provide AI-generated summaries.

#### Scenario: Summary generation
- **GIVEN** a search query
- **WHEN** `brave.summarize(query=query)` is called
- **THEN** it SHALL return an AI-generated summary of search results
- **AND** it requires a Brave Search Pro plan

#### Scenario: No summary available
- **GIVEN** a query with no summary
- **WHEN** `brave.summarize(query=query)` is called
- **THEN** it SHALL return "No summary available for this query."

### Requirement: Query Validation

All Brave Search functions SHALL validate query parameters.

#### Scenario: Query too long
- **GIVEN** a query exceeding 400 characters
- **WHEN** any search function is called
- **THEN** it SHALL return "Error: Query exceeds 400 character limit ({length} chars)"

#### Scenario: Too many words
- **GIVEN** a query exceeding 50 words
- **WHEN** any search function is called
- **THEN** it SHALL return "Error: Query exceeds 50 word limit ({count} words)"

### Requirement: API Key Configuration

All Brave Search functions SHALL require API key configuration.

#### Scenario: Missing API key
- **GIVEN** `OT_BRAVE_API_KEY` environment variable is not set
- **WHEN** any Brave search function is called
- **THEN** it SHALL return "Error: OT_BRAVE_API_KEY environment variable not set"

### Requirement: Brave Search Logging

The tool SHALL log all API operations using LogSpan.

#### Scenario: Web search logging
- **GIVEN** a web search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "brave.search.web"`
  - `query`: Search query
  - `count`: Requested result count
  - `resultCount`: Actual results returned

#### Scenario: Batch search logging
- **GIVEN** a batch search is requested
- **WHEN** the batch completes
- **THEN** it SHALL log:
  - `span: "brave.batch"`
  - `queryCount`: Number of queries
  - `successCount`: Successful searches
  - `failCount`: Failed searches

#### Scenario: API request logging
- **GIVEN** any Brave API request is made
- **WHEN** the request completes
- **THEN** it SHALL log:
  - `span: "brave.request"`
  - `endpoint`: API endpoint
  - `status`: HTTP status code

