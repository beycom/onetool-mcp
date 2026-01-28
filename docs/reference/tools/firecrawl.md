# Firecrawl

**Web scraping, crawling, and structured extraction.**

Scrape single pages, batch URLs, discover sitemaps, crawl sites, and extract structured data via the Firecrawl API.

## Highlights

- Single and batch URL scraping with multiple output formats
- URL discovery via sitemap or crawling
- Multi-page asynchronous crawling with depth/path control
- LLM-powered structured data extraction with JSON schemas
- Autonomous web research with natural language prompts

## Functions

| Function | Description |
|----------|-------------|
| `firecrawl.scrape(url, ...)` | Scrape a single URL |
| `firecrawl.scrape_batch(urls, ...)` | Scrape multiple URLs in parallel |
| `firecrawl.map_urls(url, ...)` | Discover URLs from a website |
| `firecrawl.search(query, ...)` | Web search with optional scraping |
| `firecrawl.crawl(url, ...)` | Start async crawl job |
| `firecrawl.crawl_status(id=...)` | Check crawl job status |
| `firecrawl.extract(urls, prompt, ...)` | Extract structured data with LLM |
| `firecrawl.deep_research(prompt, ...)` | Autonomous web research |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | Target URL to scrape or crawl |
| `urls` | list[str] | Multiple URLs for batch operations |
| `formats` | list[str] | Output formats: "markdown", "html", "links", "screenshot" |
| `only_main_content` | bool | Exclude headers/footers/navigation |
| `mobile` | bool | Use mobile viewport |
| `wait_for` | int | Wait ms for JavaScript to render |
| `max_depth` | int | Crawl depth limit |
| `limit` | int | Max pages/results to return |
| `schema` | dict | JSON schema for structured extraction |

## Requires

- `FIRECRAWL_API_KEY` in secrets.yaml

## Configuration

```yaml
tools:
  firecrawl:
    api_url: null  # Custom URL for self-hosted instances
```

## Examples

```python
# Basic scrape
firecrawl.scrape(url="https://example.com")

# Scrape with multiple formats
firecrawl.scrape(url="https://example.com", formats=["markdown", "links"])

# Batch scrape
firecrawl.scrape_batch(urls=["https://a.com", "https://b.com"])

# Discover site URLs
firecrawl.map_urls(url="https://example.com", limit=100)

# Search and scrape results
firecrawl.search(query="python tutorials", limit=5)

# Start crawl job
firecrawl.crawl(url="https://docs.example.com", max_depth=2, limit=50)

# Check crawl status
firecrawl.crawl_status(id="abc123")

# Extract structured data
firecrawl.extract(
    urls=["https://example.com/pricing"],
    prompt="Extract pricing tiers",
    schema={"type": "object", "properties": {"tiers": {"type": "array"}}}
)

# Autonomous research
firecrawl.deep_research(prompt="Compare pricing of top 5 CRM tools")
```

## Source

[Firecrawl API](https://docs.firecrawl.dev/)
