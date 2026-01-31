# tool-context7 Specification

## Purpose

Provides library search and documentation retrieval via the Context7 API. Enables semantic documentation lookup for software libraries with support for flexible input formats. Requires `CONTEXT7_API_KEY` secret.
## Requirements
### Requirement: Library Search

The `search()` function SHALL search for libraries by name.

#### Scenario: Basic search
- **GIVEN** a library name query
- **WHEN** `search(query="next.js")` is called
- **THEN** it SHALL return matching libraries from Context7

#### Scenario: Missing API key
- **GIVEN** `CONTEXT7_API_KEY` secret is not set
- **WHEN** `search(query="react")` is called
- **THEN** it SHALL return "[Context7 API key not configured]"

### Requirement: Documentation Retrieval

The `doc()` function SHALL fetch documentation for a library.

#### Scenario: Basic documentation fetch
- **GIVEN** a library key and topic
- **WHEN** `doc(library_key="vercel/next.js", topic="routing")` is called
- **THEN** it SHALL return documentation for that topic

#### Scenario: General documentation (no topic)
- **GIVEN** only a library key
- **WHEN** `doc(library_key="vercel/next.js")` is called
- **THEN** it SHALL return general documentation for the library
- **AND** topic defaults to empty string

#### Scenario: Info mode (default)
- **GIVEN** mode="info" (default)
- **WHEN** `doc(library_key="react", topic="hooks", mode="info")` is called
- **THEN** it SHALL return conceptual guides and narrative documentation

#### Scenario: Code mode
- **GIVEN** mode="code"
- **WHEN** `doc(library_key="react", topic="hooks", mode="code")` is called
- **THEN** it SHALL return API references and code examples

#### Scenario: No content suggestion
- **GIVEN** a library with no content for requested mode
- **WHEN** `doc(library_key="lib", mode="code")` returns no content
- **THEN** it SHALL suggest trying the other mode: "Try mode='info'."

#### Scenario: Pagination
- **GIVEN** a topic with multiple pages
- **WHEN** `doc(library_key="lib", topic="t", page=2)` is called
- **THEN** it SHALL return the second page of results
- **AND** page SHALL be clamped to range 1-10

#### Scenario: Result limit
- **GIVEN** limit parameter
- **WHEN** `doc(library_key="lib", topic="t", limit=5)` is called
- **THEN** it SHALL return up to 5 results per page
- **AND** limit SHALL be clamped to range 1-10

### Requirement: Library Key Normalization

The `doc()` function SHALL normalize various library key formats.

#### Scenario: Full format
- **GIVEN** library_key="vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL use "vercel/next.js" as the key

#### Scenario: With leading slash
- **GIVEN** library_key="/vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL normalize to "vercel/next.js"

#### Scenario: With version suffix
- **GIVEN** library_key="/vercel/next.js/v16.0.3"
- **WHEN** `doc()` is called
- **THEN** it SHALL extract "vercel/next.js" (without version)

#### Scenario: GitHub URL
- **GIVEN** library_key="https://github.com/vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL extract "vercel/next.js"

#### Scenario: Shorthand name
- **GIVEN** library_key="next.js" (no org)
- **WHEN** `doc()` is called
- **THEN** it SHALL search Context7 to resolve the full key

#### Scenario: Stray quotes
- **GIVEN** library_key='"vercel/next.js"'
- **WHEN** `doc()` is called
- **THEN** it SHALL strip quotes and use "vercel/next.js"

#### Scenario: Double slashes
- **GIVEN** library_key="vercel//next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL normalize to "vercel/next.js"

### Requirement: Topic Normalization

The `doc()` function SHALL normalize topic strings.

#### Scenario: Stray quotes
- **GIVEN** topic='"PPR"'
- **WHEN** `doc()` is called
- **THEN** it SHALL strip quotes and use "PPR"

#### Scenario: Placeholder syntax
- **GIVEN** topic="<relevant topic>"
- **WHEN** `doc()` is called
- **THEN** it SHALL treat as empty topic for general docs

#### Scenario: Path-like topic
- **GIVEN** topic="app/partial-pre-rendering/index"
- **WHEN** `doc()` is called
- **THEN** it SHALL convert to "partial pre-rendering"

#### Scenario: Kebab-case
- **GIVEN** topic="partial-pre-rendering"
- **WHEN** `doc()` is called
- **THEN** it SHALL convert to "partial pre rendering"

### Requirement: Error Handling

Context7 functions SHALL handle errors gracefully.

#### Scenario: HTTP error
- **GIVEN** an API error response
- **WHEN** any Context7 function is called
- **THEN** it SHALL return error message with status code

#### Scenario: Request timeout
- **GIVEN** a slow API response
- **WHEN** request exceeds 30 seconds
- **THEN** it SHALL return a timeout error message

### Requirement: Context7 Logging

The tool SHALL log all documentation operations using LogSpan.

#### Scenario: Library search logging
- **GIVEN** a library search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "context7.search"`
  - `query`: Search query
  - `success`: Whether request succeeded
  - `resultLen`: Length of result string

#### Scenario: Documentation fetch logging
- **GIVEN** documentation is requested
- **WHEN** the fetch completes
- **THEN** it SHALL log:
  - `span: "context7.doc"`
  - `library_key`: Original library key
  - `topic`: Requested topic
  - `mode`: Documentation mode (info/code)
  - `resolvedKey`: Resolved org/repo key
  - `success`: Whether request succeeded
  - `resultLen`: Length of result string

