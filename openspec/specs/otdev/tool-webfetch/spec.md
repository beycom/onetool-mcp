# tool-webfetch Specification

## Purpose

Provides web content extraction using trafilatura. Fetches web pages and extracts main content while filtering out navigation, ads, and boilerplate.
## Requirements
### Requirement: Single URL Fetch

The `webfetch.fetch()` function SHALL fetch and extract content from a single URL.

#### Scenario: Default markdown output
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return the main content in markdown format
- **AND** it SHALL exclude navigation, ads, and boilerplate

#### Scenario: Plain text output
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, output_format="text")` is called
- **THEN** it SHALL return plain text without formatting

#### Scenario: JSON output
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, output_format="json")` is called
- **THEN** it SHALL return JSON with text, metadata, and structure

#### Scenario: HTML output
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, output_format="html")` is called
- **THEN** it SHALL return normalised HTML with tags preserved

### Requirement: Content Length Control

The `webfetch.fetch()` function SHALL support output length limiting.

#### Scenario: Truncate long content
- **GIVEN** a URL with long content
- **WHEN** `webfetch.fetch(url=url, max_length=1000)` is called
- **THEN** it SHALL truncate the output to the specified length
- **AND** it SHALL append a truncation indicator "\n\n[Content truncated...]"

#### Scenario: Default length
- **GIVEN** a URL
- **WHEN** `webfetch.fetch(url=url)` is called without max_length
- **THEN** it SHALL use default max_length of 50000

### Requirement: Extraction Options

The `webfetch.fetch()` function SHALL support extraction configuration.

#### Scenario: Include links
- **GIVEN** a URL with hyperlinks
- **WHEN** `webfetch.fetch(url=url, include_links=True)` is called
- **THEN** it SHALL include hyperlinks in the output

#### Scenario: Include images
- **GIVEN** a URL with images
- **WHEN** `webfetch.fetch(url=url, include_images=True)` is called
- **THEN** it SHALL include image references in the output

#### Scenario: Include tables
- **GIVEN** a URL with tables
- **WHEN** `webfetch.fetch(url=url, include_tables=True)` is called (default)
- **THEN** it SHALL include table content in the output

#### Scenario: Include comments
- **GIVEN** a URL with comments section
- **WHEN** `webfetch.fetch(url=url, include_comments=True)` is called
- **THEN** it SHALL include comment content in the output

#### Scenario: Include formatting
- **GIVEN** a URL with structured content (headers, lists)
- **WHEN** `webfetch.fetch(url=url, include_formatting=True)` is called (default)
- **THEN** it SHALL preserve structural elements in output
- **AND** headers and lists SHALL be converted to markdown

#### Scenario: Exclude formatting
- **GIVEN** a URL with structured content
- **WHEN** `webfetch.fetch(url=url, include_formatting=False)` is called
- **THEN** it SHALL return plain text without structural elements

#### Scenario: Fast mode
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, fast=True)` is called
- **THEN** it SHALL skip fallback extraction algorithms
- **AND** it SHALL return results faster

#### Scenario: Favor precision
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, favor_precision=True)` is called
- **THEN** it SHALL prefer less text but correct extraction
- **AND** it SHALL exclude uncertain content

#### Scenario: Favor recall
- **GIVEN** a valid URL
- **WHEN** `webfetch.fetch(url=url, favor_recall=True)` is called
- **THEN** it SHALL prefer more text even when unsure
- **AND** it SHALL include borderline content

#### Scenario: Language filter
- **GIVEN** a URL with mixed-language content
- **WHEN** `webfetch.fetch(url=url, target_language="en")` is called
- **THEN** it SHALL filter content by ISO 639-1 language code
- **AND** it SHALL return None if language doesn't match

#### Scenario: Include metadata
- **GIVEN** `output_format="json"` and `include_metadata=True`
- **WHEN** `webfetch.fetch(url=url, output_format="json", include_metadata=True)` is called
- **THEN** it SHALL return a JSON object with `content` and `metadata` fields
- **AND** `metadata` SHALL include `final_url` and `content_type`
- **AND** when present, extracted article fields (`title`, `author`, `date`) SHALL be included in `metadata`

#### Scenario: Loopback fetch failure guidance
- **GIVEN** a loopback URL such as `http://127.0.0.1:18888/...` or `http://localhost:...`
- **WHEN** fetching fails
- **THEN** the error message SHALL explicitly identify loopback context
- **AND** it SHALL include actionable guidance about loopback restrictions in some runtimes

### Requirement: Batch URL Fetch

The `webfetch.fetch_batch()` function SHALL fetch multiple URLs concurrently.

#### Scenario: Simple batch
- **GIVEN** a list of URLs
- **WHEN** `webfetch.fetch_batch(urls=urls)` is called
- **THEN** it SHALL fetch all URLs concurrently
- **AND** it SHALL return concatenated results with section separators

#### Scenario: Labeled batch
- **GIVEN** a list of (url, label) tuples
- **WHEN** `webfetch.fetch_batch(urls=urls)` is called
- **THEN** each section SHALL be labeled with the provided label

#### Scenario: Partial failure
- **GIVEN** a list of URLs where some are unreachable
- **WHEN** `webfetch.fetch_batch(urls=urls)` is called
- **THEN** it SHALL return results for successful fetches
- **AND** it SHALL include error messages for failed fetches

#### Scenario: Concurrent workers
- **GIVEN** a list of URLs
- **WHEN** `webfetch.fetch_batch(urls=urls, max_workers=10)` is called
- **THEN** it SHALL use up to 10 concurrent workers
- **AND** default max_workers is 5

#### Scenario: Parameter parity with fetch
- **GIVEN** a batch fetch request
- **WHEN** `webfetch.fetch_batch()` is called with any extraction option
- **THEN** it SHALL support all `fetch()` parameters:
  - `include_links`, `include_images`, `include_tables`
  - `include_comments`, `include_formatting`
  - `favor_precision`, `favor_recall`
  - `fast`, `target_language`, `use_cache`
- **AND** it SHALL pass all parameters to each individual fetch call

#### Scenario: Conflicting batch options
- **GIVEN** `favor_precision=True` and `favor_recall=True`
- **WHEN** `webfetch.fetch_batch(urls=urls, favor_precision=True, favor_recall=True)` is called
- **THEN** it SHALL return an error string explaining the conflict

### Requirement: Input Validation

The `webfetch.fetch()` function SHALL validate inputs before processing.

#### Scenario: Empty URL
- **GIVEN** an empty or whitespace-only URL
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return an error string containing "URL cannot be empty"

#### Scenario: Malformed URL
- **GIVEN** a URL without scheme or netloc (e.g., "example.com")
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return an error string containing "Invalid URL format: {url}"

#### Scenario: Conflicting extraction options
- **GIVEN** both `favor_precision=True` and `favor_recall=True`
- **WHEN** `webfetch.fetch(url=url, favor_precision=True, favor_recall=True)` is called
- **THEN** it SHALL return an error string explaining the conflict

### Requirement: Error Handling

The `webfetch.fetch()` function SHALL handle errors gracefully.

#### Scenario: Network failure
- **GIVEN** a URL that cannot be fetched
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return an error message
- **AND** it SHALL NOT raise an exception

#### Scenario: Timeout
- **GIVEN** a slow URL
- **WHEN** `webfetch.fetch(url=url, timeout=5)` is called
- **AND** the request exceeds 5 seconds
- **THEN** it SHALL return a timeout error message with the timeout duration

#### Scenario: Connection failure
- **GIVEN** a URL with connection issues
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return a connection error message with details

#### Scenario: No content extracted
- **GIVEN** a URL where trafilatura cannot extract content
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return "Error: No content could be extracted from: {url}"

### Requirement: Non-HTML Content Handling

The `webfetch.fetch()` function SHALL detect content type and return non-HTML content directly.

#### Scenario: Plain text files
- **GIVEN** a URL returning `Content-Type: text/plain`
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return the raw content without HTML extraction
- **AND** it SHALL NOT call trafilatura extraction

#### Scenario: JSON files
- **GIVEN** a URL returning `Content-Type: application/json`
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return the raw JSON content
- **AND** it SHALL NOT call trafilatura extraction

#### Scenario: XML files
- **GIVEN** a URL returning `Content-Type: application/xml` or `text/xml`
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return the raw XML content
- **AND** it SHALL NOT call trafilatura extraction

#### Scenario: CSV files
- **GIVEN** a URL returning `Content-Type: text/csv`
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL return the raw CSV content
- **AND** it SHALL NOT call trafilatura extraction

#### Scenario: HTML content type detection
- **GIVEN** a URL returning `Content-Type: text/html` or `application/xhtml+xml`
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL proceed with trafilatura extraction as normal

#### Scenario: Missing content type
- **GIVEN** a URL with no Content-Type header
- **WHEN** `webfetch.fetch(url=url)` is called
- **THEN** it SHALL assume HTML and proceed with extraction

#### Scenario: Non-HTML content truncation
- **GIVEN** a non-HTML URL with content exceeding max_length
- **WHEN** `webfetch.fetch(url=url, max_length=N)` is called
- **THEN** it SHALL truncate the raw content to N characters
- **AND** it SHALL append "\n\n[Content truncated...]"

#### Scenario: JSON error format
- **GIVEN** `output_format="json"` and an error occurs
- **WHEN** `webfetch.fetch(url=url, output_format="json")` is called
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
- **WHEN** `webfetch.fetch(url=url, output_format="json")` is called
- **THEN** it SHALL pass with_metadata=True to trafilatura

### Requirement: Web Fetch Logging

The tool SHALL emit structured runtime logs for all fetch operations.

#### Scenario: URL download logging
- **GIVEN** a URL download is requested
- **WHEN** the download completes
- **THEN** it SHALL log:
  - `span: "webfetch.download"`
  - `url`: Target URL
  - `timeout`: Request timeout
  - `success`: Whether download succeeded
  - `responseLen`: Response size (if successful)
  - `contentType`: Content-Type header value

#### Scenario: Fetch operation logging
- **GIVEN** a fetch operation is requested
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "webfetch.fetch"`
  - `url`: Target URL
  - `output_format`: Requested output format
  - `contentLen`: Extracted content length (if successful)
  - `cached`: Whether cache was used
