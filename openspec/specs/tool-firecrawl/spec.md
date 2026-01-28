# tool-firecrawl Specification

## Purpose
Web scraping, crawling, and structured extraction via the Firecrawl API. Provides single URL scraping, batch scraping, URL discovery, web search, multi-page crawling, and LLM-powered data extraction.
## Requirements
### Requirement: Internal Tool Structure

The firecrawl pack SHALL be implemented as an internal tool and follow OneTool conventions.

#### Scenario: Pack and exports
- **WHEN** the tool is loaded
- **THEN** `pack = "firecrawl"` is declared before imports and `__all__` lists all 8 functions

#### Scenario: Keyword-only arguments
- **WHEN** any tool function is defined
- **THEN** all parameters use keyword-only syntax (`*,`)

#### Scenario: Complete docstrings
- **WHEN** any tool function is defined
- **THEN** it includes Args, Returns, and Example sections

---

### Requirement: Firecrawl Configuration

The firecrawl pack SHALL require `FIRECRAWL_API_KEY` secret for authentication and MAY accept optional `firecrawl.api_url` config for self-hosted instances.

#### Scenario: Cloud API key authentication
- **WHEN** `FIRECRAWL_API_KEY` is configured in secrets
- **THEN** all firecrawl tools authenticate using this key

#### Scenario: Self-hosted instance
- **WHEN** `firecrawl.api_url` is configured
- **THEN** tools connect to the specified URL instead of cloud API

#### Scenario: Missing API key
- **WHEN** `FIRECRAWL_API_KEY` is not configured
- **THEN** tools return a clear error with setup instructions

---

### Requirement: Single URL Scraping

The `firecrawl.scrape` function SHALL extract content from a single URL with configurable output formats.

#### Scenario: Basic markdown extraction
- **WHEN** `firecrawl.scrape(url="https://example.com")` is called
- **THEN** return markdown content of the page

#### Scenario: Multiple formats
- **WHEN** `firecrawl.scrape(url="...", formats=["markdown", "links", "screenshot"])` is called
- **THEN** return content in all requested formats

#### Scenario: Content filtering
- **WHEN** `only_main_content=True` is specified
- **THEN** exclude headers, footers, and navigation from output

#### Scenario: Mobile viewport
- **WHEN** `mobile=True` is specified
- **THEN** render page using mobile user agent and viewport

#### Scenario: Wait for dynamic content
- **WHEN** `wait_for=3000` is specified
- **THEN** wait 3 seconds for JavaScript to render before extraction

---

### Requirement: Batch URL Scraping

The `firecrawl.scrape_batch` function SHALL scrape multiple URLs in parallel with consistent error handling.

#### Scenario: Parallel execution
- **WHEN** `firecrawl.scrape_batch(urls=["url1", "url2", "url3"])` is called
- **THEN** execute scrapes concurrently using thread pool

#### Scenario: Per-URL error isolation
- **WHEN** one URL fails during batch scrape
- **THEN** return error for that URL while completing others successfully

#### Scenario: Shared options
- **WHEN** `formats` or other options are specified
- **THEN** apply them to all URLs in the batch

---

### Requirement: URL Discovery and Mapping

The `firecrawl.map_urls` function SHALL discover URLs from a website via sitemap or crawling.

#### Scenario: Basic URL discovery
- **WHEN** `firecrawl.map_urls(url="https://example.com")` is called
- **THEN** return list of discovered URLs from the site

#### Scenario: Search filter
- **WHEN** `search="blog"` is specified
- **THEN** return only URLs containing "blog" in the path

#### Scenario: Sitemap preference
- **WHEN** `sitemap_only=True` is specified
- **THEN** use only sitemap.xml for URL discovery, no crawling

#### Scenario: Subdomain inclusion
- **WHEN** `include_subdomains=True` is specified
- **THEN** include URLs from subdomains in results

#### Scenario: URL result limit
- **WHEN** `limit=100` is specified
- **THEN** return at most 100 URLs

---

### Requirement: Web Search with Content

The `firecrawl.search` function SHALL perform web searches with optional content scraping of results.

#### Scenario: Basic search
- **WHEN** `firecrawl.search(query="python web scraping")` is called
- **THEN** return search results with URLs and snippets

#### Scenario: Search with scraping
- **WHEN** `scrape_options={"formats": ["markdown"]}` is specified
- **THEN** scrape full content from search result URLs

#### Scenario: Search operators
- **WHEN** query contains `site:`, `inurl:`, or `-exclude`
- **THEN** apply search operators correctly

#### Scenario: Search result limit
- **WHEN** `limit=5` is specified
- **THEN** return at most 5 search results

---

### Requirement: Multi-Page Crawling

The `firecrawl.crawl` function SHALL start an asynchronous crawl job and return a job ID for status polling.

#### Scenario: Start crawl job
- **WHEN** `firecrawl.crawl(url="https://example.com")` is called
- **THEN** return job ID for status polling

#### Scenario: Depth limit
- **WHEN** `max_depth=2` is specified
- **THEN** crawl pages up to 2 links deep from start URL

#### Scenario: Page limit
- **WHEN** `limit=50` is specified
- **THEN** crawl at most 50 pages

#### Scenario: Path filtering
- **WHEN** `include_paths=["/docs/*"]` or `exclude_paths=["/admin/*"]` is specified
- **THEN** filter crawled URLs by path patterns

---

### Requirement: Crawl Status Polling

The `firecrawl.crawl_status` function SHALL return the current status and results of a crawl job.

#### Scenario: In-progress status
- **WHEN** crawl job is still running
- **THEN** return status "crawling" with progress percentage and pages crawled

#### Scenario: Completed status
- **WHEN** crawl job has finished
- **THEN** return status "completed" with all crawled page data

#### Scenario: Failed status
- **WHEN** crawl job encountered an error
- **THEN** return status "failed" with error message

---

### Requirement: Structured Data Extraction

The `firecrawl.extract` function SHALL extract structured data from URLs using LLM and JSON schema.

#### Scenario: Schema-based extraction
- **WHEN** `firecrawl.extract(urls=["..."], prompt="Extract product info", schema={"type": "object", ...})` is called
- **THEN** return data matching the provided JSON schema

#### Scenario: Multiple URLs
- **WHEN** multiple URLs are provided
- **THEN** extract and merge data from all URLs

#### Scenario: External link following
- **WHEN** `allow_external_links=True` is specified
- **THEN** follow external links during extraction to gather more data

---

### Requirement: Autonomous Web Research

The `firecrawl.deep_research` function SHALL autonomously gather web data based on a natural language prompt.

#### Scenario: Autonomous research
- **WHEN** `firecrawl.deep_research(prompt="Find the pricing for top 5 CRM tools")` is called
- **THEN** autonomously search, scrape, and compile the requested information

#### Scenario: Seed URLs
- **WHEN** `urls=["https://example.com"]` is provided
- **THEN** use provided URLs as starting points for research

#### Scenario: Research limits
- **WHEN** `max_urls=20` or `time_limit=300` is specified
- **THEN** constrain research to specified URL count or time limit in seconds

---

### Requirement: Error Handling

All firecrawl functions SHALL return clear error messages without raising exceptions to the caller.

#### Scenario: Network error
- **WHEN** a network error occurs during scraping
- **THEN** return formatted error string describing the issue

#### Scenario: Rate limit exceeded
- **WHEN** API rate limit is exceeded
- **THEN** SDK handles retry internally; if exhausted, return rate limit error

#### Scenario: Invalid URL
- **WHEN** an invalid URL is provided
- **THEN** return validation error with the problematic URL

---

### Requirement: Logging Integration

All firecrawl functions SHALL use LogSpan for operation tracking.

#### Scenario: Scrape logging
- **WHEN** `firecrawl.scrape` is called
- **THEN** log span includes url, formats, and response size

#### Scenario: Batch logging
- **WHEN** `firecrawl.scrape_batch` is called
- **THEN** log span includes url count, success count, and error count

#### Scenario: Crawl logging
- **WHEN** `firecrawl.crawl` is called
- **THEN** log span includes url, job_id, and configuration
