# tool-web-fetch Specification

## Purpose

Provides web content extraction using trafilatura. Fetches web pages and extracts main content while filtering out navigation, ads, and boilerplate.
## Requirements
### Requirement: Single URL Fetch

The `web.fetch()` function SHALL fetch and extract content from a single URL.

#### Scenario: Default markdown output
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL return the main content in markdown format
- **AND** it SHALL exclude navigation, ads, and boilerplate

#### Scenario: Plain text output
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url, output_format="text")` is called
- **THEN** it SHALL return plain text without formatting

#### Scenario: JSON output
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url, output_format="json")` is called
- **THEN** it SHALL return JSON with text, metadata, and structure

### Requirement: Content Length Control

The `web.fetch()` function SHALL support output length limiting.

#### Scenario: Truncate long content
- **GIVEN** a URL with long content
- **WHEN** `web.fetch(url=url, max_length=1000)` is called
- **THEN** it SHALL truncate the output to the specified length
- **AND** it SHALL append a truncation indicator "[Content truncated...]"

#### Scenario: Default length
- **GIVEN** a URL
- **WHEN** `web.fetch(url=url)` is called without max_length
- **THEN** it SHALL use default max_length of 50000

### Requirement: Extraction Options

The `web.fetch()` function SHALL support extraction configuration.

#### Scenario: Include links
- **GIVEN** a URL with hyperlinks
- **WHEN** `web.fetch(url=url, include_links=True)` is called
- **THEN** it SHALL include hyperlinks in the output

#### Scenario: Include images
- **GIVEN** a URL with images
- **WHEN** `web.fetch(url=url, include_images=True)` is called
- **THEN** it SHALL include image references in the output

#### Scenario: Include tables
- **GIVEN** a URL with tables
- **WHEN** `web.fetch(url=url, include_tables=True)` is called (default)
- **THEN** it SHALL include table content in the output

#### Scenario: Include comments
- **GIVEN** a URL with comments section
- **WHEN** `web.fetch(url=url, include_comments=True)` is called
- **THEN** it SHALL include comment content in the output

#### Scenario: Include formatting
- **GIVEN** a URL with structured content (headers, lists)
- **WHEN** `web.fetch(url=url, include_formatting=True)` is called (default)
- **THEN** it SHALL preserve structural elements in output
- **AND** headers and lists SHALL be converted to markdown

#### Scenario: Exclude formatting
- **GIVEN** a URL with structured content
- **WHEN** `web.fetch(url=url, include_formatting=False)` is called
- **THEN** it SHALL return plain text without structural elements

#### Scenario: Fast mode
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url, fast=True)` is called
- **THEN** it SHALL skip fallback extraction algorithms
- **AND** it SHALL return results faster

#### Scenario: Favor precision
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url, favor_precision=True)` is called
- **THEN** it SHALL prefer less text but correct extraction
- **AND** it SHALL exclude uncertain content

#### Scenario: Favor recall
- **GIVEN** a valid URL
- **WHEN** `web.fetch(url=url, favor_recall=True)` is called
- **THEN** it SHALL prefer more text even when unsure
- **AND** it SHALL include borderline content

#### Scenario: Language filter
- **GIVEN** a URL with mixed-language content
- **WHEN** `web.fetch(url=url, target_language="en")` is called
- **THEN** it SHALL filter content by ISO 639-1 language code
- **AND** it SHALL return None if language doesn't match

#### Scenario: Include metadata
- **GIVEN** `output_format="json"` and `include_metadata=True`
- **WHEN** `web.fetch(url=url, output_format="json", include_metadata=True)` is called
- **THEN** it SHALL return a JSON object with `content` and `metadata` fields
- **AND** `metadata` SHALL include `final_url` and `content_type`

### Requirement: Batch URL Fetch

The `web.fetch_batch()` function SHALL fetch multiple URLs concurrently.

#### Scenario: Simple batch
- **GIVEN** a list of URLs
- **WHEN** `web.fetch_batch(urls=urls)` is called
- **THEN** it SHALL fetch all URLs concurrently
- **AND** it SHALL return concatenated results with section separators

#### Scenario: Labeled batch
- **GIVEN** a list of (url, label) tuples
- **WHEN** `web.fetch_batch(urls=urls)` is called
- **THEN** each section SHALL be labeled with the provided label

#### Scenario: Partial failure
- **GIVEN** a list of URLs where some are unreachable
- **WHEN** `web.fetch_batch(urls=urls)` is called
- **THEN** it SHALL return results for successful fetches
- **AND** it SHALL include error messages for failed fetches

#### Scenario: Concurrent workers
- **GIVEN** a list of URLs
- **WHEN** `web.fetch_batch(urls=urls, max_workers=10)` is called
- **THEN** it SHALL use up to 10 concurrent workers
- **AND** default max_workers is 5

#### Scenario: Parameter parity with fetch
- **GIVEN** a batch fetch request
- **WHEN** `web.fetch_batch()` is called with any extraction option
- **THEN** it SHALL support all `fetch()` parameters:
  - `include_links`, `include_images`, `include_tables`
  - `include_comments`, `include_formatting`
  - `favor_precision`, `favor_recall`
  - `fast`, `target_language`, `use_cache`
- **AND** it SHALL pass all parameters to each individual fetch call

#### Scenario: Conflicting batch options
- **GIVEN** `favor_precision=True` and `favor_recall=True`
- **WHEN** `web.fetch_batch(urls=urls, favor_precision=True, favor_recall=True)` is called
- **THEN** it SHALL raise `ValueError` explaining the conflict

### Requirement: Input Validation

The `web.fetch()` function SHALL validate inputs before processing.

#### Scenario: Empty URL
- **GIVEN** an empty or whitespace-only URL
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL raise `ValueError` with message "URL cannot be empty"

#### Scenario: Malformed URL
- **GIVEN** a URL without scheme or netloc (e.g., "example.com")
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL raise `ValueError` with message "Invalid URL format: {url}"

#### Scenario: Conflicting extraction options
- **GIVEN** both `favor_precision=True` and `favor_recall=True`
- **WHEN** `web.fetch(url=url, favor_precision=True, favor_recall=True)` is called
- **THEN** it SHALL raise `ValueError` explaining the conflict

### Requirement: Error Handling

The `web.fetch()` function SHALL handle errors gracefully.

#### Scenario: Network failure
- **GIVEN** a URL that cannot be fetched
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL return an error message
- **AND** it SHALL NOT raise an exception

#### Scenario: Timeout
- **GIVEN** a slow URL
- **WHEN** `web.fetch(url=url, timeout=5)` is called
- **AND** the request exceeds 5 seconds
- **THEN** it SHALL return a timeout error message with the timeout duration

#### Scenario: Connection failure
- **GIVEN** a URL with connection issues
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL return a connection error message with details

#### Scenario: No content extracted
- **GIVEN** a URL where trafilatura cannot extract content
- **WHEN** `web.fetch(url=url)` is called
- **THEN** it SHALL return "Error: No content could be extracted from: {url}"

#### Scenario: JSON error format
- **GIVEN** `output_format="json"` and an error occurs
- **WHEN** `web.fetch(url=url, output_format="json")` is called
- **THEN** it SHALL return a JSON object with `error`, `url`, and `message` fields

### Requirement: trafilatura Integration

The functions SHALL use trafilatura library for extraction.

#### Scenario: URL passed to extract
- **GIVEN** a valid URL
- **WHEN** extraction occurs
- **THEN** the URL SHALL be passed to trafilatura.extract() for relative link resolution

#### Scenario: Config timeout
- **GIVEN** a timeout parameter
- **WHEN** fetching a URL
- **THEN** trafilatura config SHALL be created with DOWNLOAD_TIMEOUT set

#### Scenario: Metadata for JSON
- **GIVEN** output_format="json"
- **WHEN** `web.fetch(url=url, output_format="json")` is called
- **THEN** it SHALL pass with_metadata=True to trafilatura

### Requirement: Web Fetch Logging

The tool SHALL log all fetch operations using LogSpan.

#### Scenario: URL fetch logging
- **GIVEN** a URL fetch is requested
- **WHEN** the fetch completes
- **THEN** it SHALL log:
  - `span: "web.fetch"`
  - `url`: Target URL
  - `status`: HTTP status code
  - `contentLength`: Response size

#### Scenario: Content parsing logging
- **GIVEN** fetched content is parsed
- **WHEN** parsing completes
- **THEN** it SHALL log:
  - `span: "web.parse"`
  - `url`: Source URL
  - `textLength`: Extracted text length

