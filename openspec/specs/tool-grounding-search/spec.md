# tool-grounding-search Specification

## Purpose

Provides web search with Google's grounding capabilities via Gemini API. Supports general search, developer resources, documentation lookup, and Reddit discussions. Requires `OT_GEMINI_API_KEY` environment variable.

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

### Requirement: API Key Configuration

All grounding search functions SHALL require API key configuration.

#### Scenario: Missing API key
- **GIVEN** `OT_GEMINI_API_KEY` environment variable is not set
- **WHEN** any grounding search function is called
- **THEN** it SHALL return "Error: OT_GEMINI_API_KEY environment variable not set"

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
