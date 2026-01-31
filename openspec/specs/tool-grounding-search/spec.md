# tool-grounding-search Specification

## Purpose

Provides web search with Google's grounding capabilities via Gemini API. Supports general search, developer resources, documentation lookup, and Reddit discussions. Requires `GEMINI_API_KEY` in secrets.yaml.

## Requirements

### Requirement: Grounded Web Search

The `ground.search()` function SHALL perform grounded web searches using Google Gemini.

#### Scenario: Basic search
- **GIVEN** a search query
- **WHEN** `ground.search(query=query)` is called
- **THEN** it SHALL return search results with content and source citations

#### Scenario: Contextual search
- **GIVEN** a search query and context
- **WHEN** `ground.search(query=query, context="Python async programming")` is called
- **THEN** it SHALL include context in the search prompt

#### Scenario: Focus modes
- **GIVEN** a search query and focus parameter
- **WHEN** `ground.search(query=query, focus="code")` is called
- **THEN** it SHALL tailor results based on focus
- **AND** valid focus values are "general" (default), "code", "documentation", "troubleshooting"

#### Scenario: Custom model
- **GIVEN** a search query and model parameter
- **WHEN** `ground.search(query=query, model="gemini-3.0-flash")` is called
- **THEN** it SHALL use the specified Gemini model for grounding
- **AND** if model is None, it SHALL use the configured default model

#### Scenario: Empty query validation
- **GIVEN** an empty or whitespace-only query
- **WHEN** `ground.search(query="")` or `ground.search(query="   ")` is called
- **THEN** it SHALL raise ValueError with message "query cannot be empty"

#### Scenario: Timeout parameter
- **GIVEN** a search query and timeout parameter
- **WHEN** `ground.search(query=query, timeout=60.0)` is called
- **THEN** it SHALL use the specified timeout for the API request
- **AND** if timeout is not specified, it SHALL default to 30.0 seconds

#### Scenario: Max sources parameter
- **GIVEN** a search query and max_sources parameter
- **WHEN** `ground.search(query=query, max_sources=5)` is called
- **THEN** it SHALL limit source citations to the specified number
- **AND** if max_sources is None, it SHALL include all sources

#### Scenario: Output format parameter
- **GIVEN** a search query and output_format parameter
- **WHEN** `ground.search(query=query, output_format="text_only")` is called
- **THEN** it SHALL return only the text content without sources
- **AND** when output_format is "sources_only", it SHALL return only source citations
- **AND** when output_format is "full" (default), it SHALL return both text and sources

### Requirement: Developer Resources Search

The `ground.dev()` function SHALL search for developer resources and documentation.

#### Scenario: Basic developer search
- **GIVEN** a technical query
- **WHEN** `ground.dev(query=query)` is called
- **THEN** it SHALL return developer-focused results from GitHub, Stack Overflow, and docs

#### Scenario: Language-specific search
- **GIVEN** a technical query and language
- **WHEN** `ground.dev(query=query, language="Python")` is called
- **THEN** it SHALL prioritize results for that programming language

#### Scenario: Framework-specific search
- **GIVEN** a technical query and framework
- **WHEN** `ground.dev(query=query, framework="FastAPI")` is called
- **THEN** it SHALL prioritize results for that framework

#### Scenario: Empty query validation
- **GIVEN** an empty or whitespace-only query
- **WHEN** `ground.dev(query="")` is called
- **THEN** it SHALL raise ValueError with message "query cannot be empty"

### Requirement: Documentation Search

The `ground.docs()` function SHALL search for official documentation.

#### Scenario: Basic docs search
- **GIVEN** a documentation query
- **WHEN** `ground.docs(query=query)` is called
- **THEN** it SHALL return official documentation and API references

#### Scenario: Technology-specific docs
- **GIVEN** a query and technology name
- **WHEN** `ground.docs(query="hooks", technology="React")` is called
- **THEN** it SHALL search React official documentation

#### Scenario: Empty query validation
- **GIVEN** an empty or whitespace-only query
- **WHEN** `ground.docs(query="")` is called
- **THEN** it SHALL raise ValueError with message "query cannot be empty"

### Requirement: Reddit Search

The `ground.reddit()` function SHALL search Reddit discussions.

#### Scenario: Basic Reddit search
- **GIVEN** a search query
- **WHEN** `ground.reddit(query=query)` is called
- **THEN** it SHALL return indexed Reddit posts and comments

#### Scenario: Subreddit-specific search
- **GIVEN** a query and subreddit name
- **WHEN** `ground.reddit(query=query, subreddit="programming")` is called
- **THEN** it SHALL limit search to that subreddit

#### Scenario: Empty query validation
- **GIVEN** an empty or whitespace-only query
- **WHEN** `ground.reddit(query="")` is called
- **THEN** it SHALL raise ValueError with message "query cannot be empty"

### Requirement: Batch Search

The `ground.search_batch()` function SHALL execute multiple grounded searches concurrently.

#### Scenario: Basic batch search
- **GIVEN** a list of queries
- **WHEN** `ground.search_batch(queries=["query1", "query2"])` is called
- **THEN** it SHALL execute searches in parallel and return combined results

#### Scenario: Empty batch validation
- **GIVEN** an empty queries list
- **WHEN** `ground.search_batch(queries=[])` is called
- **THEN** it SHALL raise ValueError with message "queries list cannot be empty"

#### Scenario: Batch with model parameter
- **GIVEN** a list of queries and model parameter
- **WHEN** `ground.search_batch(queries=queries, model="gemini-3.0-flash")` is called
- **THEN** it SHALL use the specified model for all searches

### Requirement: Source Citations

All grounding search functions SHALL include source citations.

#### Scenario: Source extraction
- **GIVEN** a search query with grounded results
- **WHEN** the search completes
- **THEN** it SHALL append a "Sources" section with numbered markdown links

#### Scenario: Deduplicated sources
- **GIVEN** search results with duplicate URLs
- **WHEN** sources are formatted
- **THEN** it SHALL show each unique URL only once

#### Scenario: Sequential source numbering
- **GIVEN** search results with duplicate URLs
- **WHEN** sources are formatted
- **THEN** it SHALL use sequential numbering without gaps (e.g., 1, 2, 3 not 1, 2, 4)

### Requirement: Error Handling

The tool SHALL provide helpful error messages.

#### Scenario: Quota error
- **GIVEN** an API quota or rate limit error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return "Error: API quota exceeded. Try again later."

#### Scenario: Authentication error
- **GIVEN** an API key or authentication error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return a message mentioning GEMINI_API_KEY and secrets.yaml

#### Scenario: Timeout error
- **GIVEN** a request timeout error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return a message about the timeout and suggest increasing timeout

### Requirement: API Key Configuration

All grounding search functions SHALL require API key configuration.

#### Scenario: Missing API key
- **GIVEN** `GEMINI_API_KEY` is not configured in secrets.yaml
- **WHEN** any grounding search function is called
- **THEN** it SHALL raise ValueError with message "GEMINI_API_KEY not set in secrets.yaml"

### Requirement: Grounding Search Logging

The tool SHALL log all API operations using LogSpan.

#### Scenario: Search logging
- **GIVEN** a search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span`: "ground.search", "ground.dev", "ground.docs", or "ground.reddit"
  - `query`: Search query
  - `hasResults`: Whether results were found
  - `resultLen`: Length of result content

#### Scenario: Error logging
- **GIVEN** an API error occurs
- **WHEN** the error is caught
- **THEN** it SHALL log:
  - `error`: Error message
