## MODIFIED Requirements

### Requirement: Web Search

The `brave.search()` function SHALL search the web using Brave Search API. Its result-count parameter SHALL be named `max_results` (not `count`), matching `tavily.search()`'s parameter name for the same concept.

#### Scenario: Basic search
- **GIVEN** a search query
- **WHEN** `brave.search(query=query)` is called
- **THEN** it SHALL return formatted search results with titles, URLs, and descriptions

#### Scenario: Result count control
- **GIVEN** a search query and max_results parameter
- **WHEN** `brave.search(query=query, max_results=5)` is called
- **THEN** it SHALL return up to 5 results
- **AND** max_results MUST be in range 1-20; values outside this range SHALL return an error

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

#### Scenario: max= prefix resolves to max_results
- **GIVEN** a search query
- **WHEN** `brave.search(query=query, max=5)` is called (using the short `max=` keyword instead of the full `max_results=`)
- **THEN** it SHALL succeed identically to `brave.search(query=query, max_results=5)`, because `max` is a prefix of the `max_results` parameter name and is resolved by the run-tool's keyword-argument prefix matching

#### Scenario: count= is no longer accepted
- **GIVEN** a search query
- **WHEN** `brave.search(query=query, count=5)` is called
- **THEN** it SHALL fail with a keyword-argument error, because `count` is no longer a parameter of `brave.search()` and is not a prefix of `max_results`

### Requirement: Query Validation

All Brave Search functions SHALL validate query parameters. The result-count parameter SHALL be named `max_results` on every function — `brave.search()`, `brave.news()`, `brave.image()`, `brave.video()`, and `brave.search_batch()` — matching `tavily.search()`'s parameter name for the same concept. (The Brave API's own outgoing query-string field remains `count`; that is Brave's external contract, not part of this tool surface.)

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

#### Scenario: Invalid max_results
- **GIVEN** a max_results value outside 1-20
- **WHEN** any of `brave.search()`, `brave.news()`, `brave.image()`, `brave.video()`, or `brave.search_batch()` is called
- **THEN** it SHALL return "Error: max_results must be between 1 and 20 (got {value})"

#### Scenario: count= is no longer accepted anywhere
- **GIVEN** any brave function
- **WHEN** it is called with `count=5`
- **THEN** it SHALL fail with a keyword-argument error, because `count` is no longer a parameter of any brave function and is not a prefix of `max_results`

#### Scenario: Invalid offset
- **GIVEN** an offset value outside 0-9
- **WHEN** any search function with an `offset` parameter is called
- **THEN** it SHALL return "Error: offset must be between 0 and 9 (got {value})"

### Requirement: Batch Search

The `brave.search_batch()` function SHALL execute multiple searches concurrently. Its per-query result-count parameter SHALL be named `max_results` (not `count`), default 2, forwarded to each individual `search()` call.

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
- **AND** invalid `max_results` values SHALL return an error message

#### Scenario: Batch text-only output format
- **GIVEN** a list of queries
- **WHEN** `brave.search_batch(queries=["q1", "q2"], output_format="text_only")` is called
- **THEN** it SHALL forward `output_format="text_only"` to each `brave.search()` call

#### Scenario: Batch retry guardrails
- **WHEN** `brave.search_batch()` is called with retry controls
- **THEN** `retries` MUST be an integer in range 0-3
- **AND** `retry_delay_ms` MUST be in range 0-10000
- **AND** values outside these ranges SHALL return an error before batch work starts
