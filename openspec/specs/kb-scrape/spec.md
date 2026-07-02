# kb-scrape Specification

## Purpose

Defines the `onetool kb scrape` pipeline that crawls documentation sites into
Markdown pages and sidecar metadata suitable for later `kb index` ingestion.

---

## Requirements

### Requirement: [scrape] install extra
The package SHALL provide a `[scrape]` optional dependency group that includes `crawl4ai>=0.8.5`. Installing `onetool[scrape]` is the supported way to enable `kb scrape`.

#### Scenario: Missing crawl4ai raises install error
- **WHEN** `onetool kb scrape` is invoked and `crawl4ai` is not importable
- **THEN** the command SHALL exit with a clear message: `"crawl4ai is required. Install with: pip install 'onetool[scrape]'"`

#### Scenario: Missing Playwright browser raises install error
- **WHEN** `crawl4ai` is installed but the Playwright Chromium browser has not been installed
- **THEN** the command SHALL exit with a clear message: `"Playwright browser not found. Run: playwright install chromium"`

---

### Requirement: Crawl Pipeline
The scraping pipeline SHALL crawl a site breadth-first up to a configurable
depth and page limit.

#### Scenario: Pages are crawled and written
- **WHEN** a crawl completes successfully
- **THEN** each successfully crawled page SHALL produce two files written atomically to the output directory:
  - `<slug>.md` — `fit_markdown` content (fallback to `raw_markdown` if `fit_markdown` is empty)
  - `<slug>.meta.yaml` — sidecar with exactly `url`, `source`, and `crawled_at`

#### Scenario: Scrape called inside an active runtime
- **GIVEN** OneTool is already executing inside an event loop
- **WHEN** `onetool kb scrape` runs
- **THEN** crawl work SHALL complete without failing due to the existing event loop

#### Scenario: Crawler cleanup on page-processing failure
- **WHEN** page processing fails after browser crawl resources have been opened
- **THEN** those resources SHALL still be closed before the command exits

#### Scenario: URL slug generation
- **WHEN** a page URL is converted to a filename
- **THEN** the slug SHALL be derived from the URL path with `.html` and `.htm` extensions stripped

#### Scenario: Failed pages are skipped
- **WHEN** Crawl4AI reports `result.success == False` for a page
- **THEN** that page SHALL be skipped (no file written) and counted in the `failed` total

#### Scenario: Empty markdown pages are skipped
- **WHEN** a crawled page yields empty `fit_markdown` and empty `raw_markdown`
- **THEN** that page SHALL be skipped and counted in the `skipped` total

---

### Requirement: Sidecar format
The `.meta.yaml` sidecar written per crawled page SHALL contain exactly the fields consumed by `kb index`.

#### Scenario: Sidecar fields for named source
- **WHEN** a page is crawled from a named source `mysite`
- **THEN** `<slug>.meta.yaml` SHALL contain:
  - `url`: the crawled page URL
  - `source`: the source name (`mysite`)
  - `crawled_at`: ISO 8601 UTC timestamp at write time

#### Scenario: Sidecar fields for ad-hoc URL
- **WHEN** a page is crawled from an ad-hoc URL with no named source
- **THEN** `source` SHALL be the hostname of the entry-point URL (e.g. `docs.example.com`)

---

### Requirement: URL filtering
The pipeline SHALL restrict crawling to the configured domain and optional URL prefix, and SHALL exclude binary file extensions.

#### Scenario: Off-domain links are not followed
- **WHEN** a crawled page contains links to a different domain
- **THEN** those links SHALL NOT be followed

#### Scenario: URL prefix restricts crawl scope
- **WHEN** `url_prefix` is set in source config (e.g. `/en/`)
- **THEN** only URLs beginning with that prefix SHALL be crawled

---

### Requirement: Rate limiting
Each source SHALL honour per-source `delay_min` and `delay_max` settings to throttle requests to the target domain.

#### Scenario: Delay applied between requests
- **WHEN** `delay_min: 1.0` and `delay_max: 3.0` are configured for a source
- **THEN** a random delay in that range SHALL be applied between page requests

---

### Requirement: Resume support
The pipeline SHALL support resuming an interrupted crawl from a `.state.json` file in the output directory.

#### Scenario: Resume skips already-crawled URLs
- **GIVEN** a prior crawl was interrupted and `.state.json` exists in the output directory
- **WHEN** `onetool kb scrape mysite --resume` is run
- **THEN** URLs already present in `.state.json` SHALL be skipped and the crawl SHALL continue from saved state

#### Scenario: State file location tied to output dir
- **WHEN** a crawl runs
- **THEN** `.state.json` SHALL be written to the output directory
- **AND** resume SHALL only work if `--output` (or config `output_dir`) resolves to the same directory

---

### Requirement: Atomic file writes
All output files SHALL be written atomically to prevent partial reads by concurrent processes.

#### Scenario: Atomic write via temp file
- **WHEN** a page is written
- **THEN** the file SHALL be written to a `.tmp` intermediate path first, then renamed to the final path

---

### Requirement: Scrape result summary
The CLI SHALL print a summary on completion.

#### Scenario: Summary after successful crawl
- **WHEN** a crawl completes
- **THEN** the command SHALL print the count of pages written, failed, and skipped

---

### Requirement: Progress output
The scrape command SHALL display real-time progress during the crawl.

#### Scenario: Progress shows pages and current URL
- **WHEN** a crawl is in progress
- **THEN** a spinner SHALL show the count of pages crawled so far, the current URL being processed, and elapsed time

#### Scenario: Progress shows page cap
- **WHEN** `max_pages` is configured
- **THEN** progress SHALL display as `N / max_pages` since BFS total is unknown upfront
