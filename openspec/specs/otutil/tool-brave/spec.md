# tool-brave Specification

## Purpose

Provides web search, news search, image search, video search, and batch search via the Brave Search API. Requires `BRAVE_API_KEY` secret in secrets.yaml.
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
- **AND** count MUST be in range 1-20; values outside this range SHALL return an error

#### Scenario: Pagination
- **GIVEN** a search query and offset parameter
- **WHEN** `brave.search(query=query, offset=1)` is called
- **THEN** it SHALL return results starting from the second page
- **AND** offset MUST be in range 0-9; values outside this range SHALL return an error

#### Scenario: Freshness filter
- **GIVEN** a search query and freshness parameter
- **WHEN** `brave.search(query=query, freshness="pd")` is called
- **THEN** it SHALL return results from the past day
- **AND** valid enum values are "pd" (day), "pw" (week), "pm" (month), "py" (year)
- **AND** a date range string "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30") is also accepted
- **AND** invalid freshness values SHALL return an error message

#### Scenario: Text-only output format
- **GIVEN** a search query
- **WHEN** `brave.search(query=query, output_format="text_only")` is called
- **THEN** it SHALL return plain text search content without source list formatting
- **AND** valid `output_format` values for web search are "full", "text_only", "sources_only"

#### Scenario: Safe search
- **GIVEN** a search query and safesearch parameter
- **WHEN** `brave.search(query=query, safesearch="strict")` is called
- **THEN** it SHALL filter adult content strictly
- **AND** valid values are "off", "moderate" (default), "strict"
- **AND** invalid safesearch values SHALL return an error message

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
- **AND** valid enum values are "pd" (day), "pw" (week), "pm" (month), "py" (year)
- **AND** a date range string "YYYY-MM-DDtoYYYY-MM-DD" is also accepted
- **AND** invalid freshness values SHALL return an error message

#### Scenario: News sort order
- **GIVEN** news results with page_age fields
- **WHEN** `brave.news(query=query)` returns results
- **THEN** results SHALL be sorted by publication date, most recent first
- **AND** results without page_age SHALL appear last

### Requirement: Image Search

The `brave.image()` function SHALL search for images.

#### Scenario: Image search
- **GIVEN** an image query
- **WHEN** `brave.image(query=query)` is called
- **THEN** it SHALL return image results with titles, sizes, sources, and URLs
- **AND** each result SHALL include a direct image URL (`Image:`) from `properties.url` when available
- **AND** results with a blank title SHALL display "No title"

#### Scenario: Image safe search
- **GIVEN** an image query
- **WHEN** `brave.image(query=query, safesearch="off")` is called
- **THEN** it SHALL disable content filtering
- **AND** valid values are "off", "strict" (default); "moderate" is not supported for image search
- **AND** invalid safesearch values SHALL return an error message

### Requirement: Video Search

The `brave.video()` function SHALL search for videos.

#### Scenario: Video search
- **GIVEN** a video query
- **WHEN** `brave.video(query=query)` is called
- **THEN** it SHALL return video results with titles, channels, durations, and URLs

#### Scenario: Video freshness filter
- **GIVEN** a video query and freshness parameter
- **WHEN** `brave.video(query=query, freshness="pw")` is called
- **THEN** it SHALL filter results to the past week
- **AND** valid enum values are "pd" (day), "pw" (week), "pm" (month), "py" (year)
- **AND** a date range string "YYYY-MM-DDtoYYYY-MM-DD" is also accepted
- **AND** invalid freshness values SHALL return an error message

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

#### Scenario: Empty batch
- **GIVEN** an empty queries list
- **WHEN** `brave.search_batch(queries=[])` is called
- **THEN** it SHALL return "Error: No queries provided"

#### Scenario: Empty tuple label
- **GIVEN** a (query, label) tuple where label is an empty string
- **WHEN** `brave.search_batch(queries=[("query text", "")])` is called
- **THEN** the section header SHALL use the query text as the label

#### Scenario: Batch safesearch and freshness
- **GIVEN** `safesearch` or `freshness` parameters
- **WHEN** `brave.search_batch(queries=["q"], safesearch="strict", freshness="pw")` is called
- **THEN** it SHALL forward those parameters to each individual `search()` call
- **AND** invalid `freshness` values SHALL return an error message
- **AND** invalid `safesearch` values SHALL return an error message
- **AND** invalid `count` values SHALL return an error message

#### Scenario: Batch text-only output format
- **GIVEN** a list of queries
- **WHEN** `brave.search_batch(queries=["q1", "q2"], output_format="text_only")` is called
- **THEN** it SHALL forward `output_format="text_only"` to each `brave.search()` call

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

#### Scenario: Empty query
- **GIVEN** an empty string or whitespace-only query
- **WHEN** any search function is called
- **THEN** it SHALL return "Error: Query cannot be empty"

#### Scenario: Invalid country code
- **GIVEN** a country parameter that is not a 2-letter uppercase code
- **WHEN** any search function with a `country` parameter is called
- **THEN** it SHALL return an error message indicating the country is invalid

#### Scenario: Invalid count
- **GIVEN** a count value outside 1-20
- **WHEN** any search function is called
- **THEN** it SHALL return "Error: count must be between 1 and 20 (got {value})"

#### Scenario: Invalid offset
- **GIVEN** an offset value outside 0-9
- **WHEN** any search function with an `offset` parameter is called
- **THEN** it SHALL return "Error: offset must be between 0 and 9 (got {value})"

### Requirement: API Key Configuration

All Brave Search functions SHALL require API key configuration.

#### Scenario: Missing API key
- **GIVEN** `BRAVE_API_KEY` secret is not configured in secrets.yaml
- **WHEN** any Brave search function is called
- **THEN** it SHALL return "Error: BRAVE_API_KEY secret not configured"

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
  - `query_count`: Number of queries
  - `count`: Requested result count per search
  - `outputLen`: Length of combined output string

#### Scenario: API request logging
- **GIVEN** any Brave API request is made
- **WHEN** the request completes
- **THEN** it SHALL log:
  - `span: "brave.request"`
  - `endpoint`: API endpoint
  - `status`: HTTP status code
