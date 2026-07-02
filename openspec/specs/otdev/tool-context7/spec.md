# tool-context7 Specification

## Purpose

Provides library search and documentation retrieval via the Context7 API. Enables semantic documentation lookup for software libraries. Requires `CONTEXT7_API_KEY` secret.

## Requirements

### Requirement: Library Search

The `search()` function SHALL search for libraries by name using the `/v2/libs/search` endpoint.

#### Scenario: Basic search
- **GIVEN** a user task query and a library name
- **WHEN** `search(query="How do I set up JWT auth?", library_name="express")` is called
- **THEN** it SHALL return matching libraries from Context7

#### Scenario: Search params
- **GIVEN** `query` and `library_name` are both required
- **WHEN** `search()` is called
- **THEN** it SHALL send both `query` and `libraryName` as query params to `/v2/libs/search`
- **AND** `query` is used for LLM relevance ranking; `library_name` identifies the library to find

#### Scenario: String output format
- **GIVEN** `output_format='str'` (the default)
- **WHEN** `search()` returns results
- **THEN** it SHALL return a human-readable markdown list with each library's name, ID, and description
- **AND** library IDs SHALL have a leading slash

#### Scenario: Dict output format
- **GIVEN** `output_format='dict'`
- **WHEN** `search()` returns results
- **THEN** it SHALL return a JSON string of the raw API response

#### Scenario: Empty query rejected
- **GIVEN** `query` is an empty string or whitespace-only
- **WHEN** `search(query="", library_name="react")` is called
- **THEN** it SHALL return an error string containing "query is required"
- **AND** it SHALL NOT make any HTTP request to the Context7 API

#### Scenario: No matching libraries warning
- **GIVEN** search results where no library title overlaps with `library_name`
- **WHEN** `search()` returns results in `str` format
- **THEN** it SHALL prepend a warning: "No libraries matching '<library_name>' were found."
- **AND** it SHALL still show the results after the warning

#### Scenario: Missing API key
- **GIVEN** `CONTEXT7_API_KEY` secret is not set
- **WHEN** `search(query="react", library_name="react")` is called
- **THEN** it SHALL return "[Context7 API key not configured]"

### Requirement: Documentation Retrieval

The `doc()` function SHALL fetch documentation using the `/v2/context` endpoint.

#### Scenario: Basic documentation fetch
- **GIVEN** a library ID
- **WHEN** `doc(library_id="/vercel/next.js", query="How do I configure middleware for JWT?")` is called
- **THEN** it SHALL return documentation from `/v2/context` with semantic reranking applied

#### Scenario: Query is required
- **GIVEN** the Context7 API requires a non-empty `query` parameter
- **WHEN** `doc()` is called without a `query` argument
- **THEN** it SHALL raise a `TypeError` (required argument)
- **AND** `query` SHALL always be included in the API request params

#### Scenario: Empty query rejected client-side
- **GIVEN** `query` is an empty string or whitespace-only
- **WHEN** `doc(library_id="...", query="")` is called
- **THEN** it SHALL return an error string containing "query is required"
- **AND** it SHALL NOT make any HTTP request to the Context7 API

#### Scenario: Endpoint and params
- **GIVEN** a resolved library ID and a query
- **WHEN** `doc()` makes the API request
- **THEN** it SHALL use `GET /v2/context?libraryId=<id>&type=txt&query=<q>`
- **AND** `libraryId` is passed as a query param (not in the URL path)
- **AND** `type=txt` SHALL always be included to request plain-text LLM-readable output

#### Scenario: Version-specific docs
- **GIVEN** a versioned library ID
- **WHEN** `doc(library_id="/vercel/next.js/v14.3.0-canary.87", query="app router")` is called
- **THEN** it SHALL pass the full versioned ID as `libraryId`
- **AND** version is embedded in the `libraryId` value, not a separate param

#### Scenario: No content
- **GIVEN** the API returns empty content
- **WHEN** `doc()` receives "No content available" or equivalent
- **THEN** it SHALL return a user-friendly message suggesting a different query

### Requirement: Library ID Normalization

The `doc()` function SHALL normalize various library ID formats.

#### Scenario: Context7 format (leading slash)
- **GIVEN** library_id="/vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL use "/vercel/next.js" as the `libraryId` param

#### Scenario: Without leading slash
- **GIVEN** library_id="vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL normalize to "/vercel/next.js"

#### Scenario: With version suffix
- **GIVEN** library_id="/vercel/next.js/v14.3.0-canary.87"
- **WHEN** `doc()` is called
- **THEN** it SHALL preserve the full versioned ID (not strip version)

#### Scenario: GitHub URL
- **GIVEN** library_id="https://github.com/vercel/next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL extract "/vercel/next.js"

#### Scenario: Shorthand name
- **GIVEN** library_id="next.js" (no org)
- **WHEN** `doc()` is called
- **THEN** it SHALL search Context7 to resolve the full ID

#### Scenario: Stray quotes
- **GIVEN** library_id='"vercel/next.js"'
- **WHEN** `doc()` is called
- **THEN** it SHALL strip quotes and normalize to "/vercel/next.js"

#### Scenario: Double slashes
- **GIVEN** library_id="vercel//next.js"
- **WHEN** `doc()` is called
- **THEN** it SHALL normalize to "/vercel/next.js"

### Requirement: Transparent Fuzzy Resolution

When `doc()` resolves a shorthand library ID via search, it SHALL surface the substitution.

#### Scenario: Resolution note
- **GIVEN** library_id="nextjs" (no org) is resolved via search to "/vercel/next.js"
- **WHEN** `doc()` returns documentation
- **THEN** the output SHALL begin with "[Resolved 'nextjs' → '/vercel/next.js']"

#### Scenario: No note for direct IDs
- **GIVEN** library_id="/vercel/next.js" is used directly without search
- **WHEN** `doc()` returns documentation
- **THEN** the output SHALL NOT contain a resolution note

### Requirement: Library Selection Quality

`_pick_best_library()` SHALL weight official and trusted libraries more strongly and SHALL reject results with no meaningful name overlap.

#### Scenario: VIP and verified boost
- **GIVEN** search results containing a personal fork and an official library
- **WHEN** both have similar title match
- **THEN** the VIP/verified official library SHALL score higher due to boosted weights:
  - VIP: +60 points
  - Verified: +40 points
  - Trust score: +trustScore × 5

#### Scenario: No title overlap — reject match
- **GIVEN** a search query that produces results with no title overlap with the query
- **WHEN** `_pick_best_library()` is called
- **THEN** it SHALL return `None` rather than silently returning an unrelated library
- **AND** `doc()` SHALL surface the "library not found" error instead of wrong docs

### Requirement: Error Handling

Context7 functions SHALL handle errors gracefully.

#### Scenario: HTTP redirects followed
- **GIVEN** the Context7 API returns a 301 redirect for a library ID
- **WHEN** any Context7 function makes a request
- **THEN** it SHALL follow the redirect transparently and return the final response

#### Scenario: HTTP 404 on doc fetch
- **GIVEN** a valid-looking library ID that does not exist in Context7
- **WHEN** `doc()` receives a 404 response from the context endpoint
- **THEN** it SHALL return a user-friendly message: "Library '<id>' was not found in Context7."
- **AND** it SHALL suggest using `context7.search()` to find the correct ID

#### Scenario: Other HTTP errors
- **GIVEN** an API error response (non-404)
- **WHEN** any Context7 function is called
- **THEN** it SHALL return error message with status code

#### Scenario: Request timeout
- **GIVEN** a slow API response
- **WHEN** request exceeds configured timeout
- **THEN** it SHALL return a timeout error message

### Requirement: Context7 Logging

The tool SHALL emit structured runtime logs for documentation operations.

#### Scenario: Library search logging
- **GIVEN** a library search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "context7.search"`
  - `query`: Search query
  - `library_name`: Library name param
  - `success`: Whether request succeeded
  - `resultLen`: Length of result string

#### Scenario: Documentation fetch logging
- **GIVEN** documentation is requested
- **WHEN** the fetch completes
- **THEN** it SHALL log:
  - `span: "context7.doc"`
  - `library_id`: Original library ID
  - `query`: Semantic query string
  - `resolvedId`: Resolved library ID
  - `success`: Whether request succeeded
  - `resultLen`: Length of result string
