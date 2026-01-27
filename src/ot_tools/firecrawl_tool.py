# /// script
# requires-python = ">=3.11"
# dependencies = ["firecrawl>=4.13.4", "pydantic>=2.0.0", "pyyaml>=6.0.0"]
# ///
"""Web scraping, crawling, and structured extraction via Firecrawl API.

Provides single URL scraping, batch scraping, URL discovery, web search,
multi-page crawling, and LLM-powered data extraction.

API docs: https://docs.firecrawl.dev/api-reference
Python SDK: https://pypi.org/project/firecrawl/
"""

from __future__ import annotations

# Pack for dot notation: firecrawl.scrape(), firecrawl.crawl(), etc.
pack = "firecrawl"

__all__ = [
    "crawl",
    "crawl_status",
    "deep_research",
    "extract",
    "map_urls",
    "scrape",
    "scrape_batch",
    "search",
]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [("firecrawl", "pip install firecrawl")],
    "secrets": ["FIRECRAWL_API_KEY"],
}

from typing import Any, Literal

from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field

from ot_sdk import (
    batch_execute,
    get_config,
    get_secret,
    lazy_client,
    log,
    normalize_items,
    worker_main,
)


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    api_url: str | None = Field(
        default=None,
        description="Custom API URL for self-hosted Firecrawl instances",
    )


def _create_client() -> FirecrawlApp | None:
    """Create Firecrawl client with API key."""
    api_key = get_secret("FIRECRAWL_API_KEY")
    if not api_key:
        return None

    api_url = get_config("tools.firecrawl.api_url")
    if api_url:
        return FirecrawlApp(api_key=api_key, api_url=api_url)
    return FirecrawlApp(api_key=api_key)


# Thread-safe lazy client using SDK utility
_get_client = lazy_client(_create_client)


def scrape(
    *,
    url: str,
    formats: list[
        Literal[
            "markdown", "html", "rawHtml", "links", "screenshot", "screenshot@fullPage"
        ]
    ]
    | None = None,
    only_main_content: bool = True,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    wait_for: int | None = None,
    mobile: bool = False,
    skip_tls_verification: bool = False,
    remove_base64_images: bool = True,
    location: dict[str, Any] | None = None,
) -> dict[str, Any] | str:
    """Scrape content from a single URL.

    Extracts content in various formats with configurable filtering.

    Args:
        url: The URL to scrape
        formats: Output formats to include. Options:
            - "markdown": Clean markdown text (default)
            - "html": Cleaned HTML
            - "rawHtml": Original HTML
            - "links": All hyperlinks on the page
            - "screenshot": Screenshot image (base64)
            - "screenshot@fullPage": Full page screenshot
        only_main_content: Extract only main content, excluding nav/footer (default: True)
        include_tags: HTML tags to include (e.g., ["article", "main"])
        exclude_tags: HTML tags to exclude (e.g., ["nav", "footer"])
        wait_for: Milliseconds to wait for dynamic content
        mobile: Use mobile user agent
        skip_tls_verification: Skip TLS certificate validation
        remove_base64_images: Remove base64 images from markdown (default: True)
        location: Geolocation for request (e.g., {"country": "US", "languages": ["en"]})

    Returns:
        Dict with scraped content in requested formats, or error message

    Example:
        # Basic scrape
        firecrawl.scrape(url="https://example.com")

        # Get markdown and links
        firecrawl.scrape(url="https://example.com", formats=["markdown", "links"])

        # Scrape with geolocation
        firecrawl.scrape(url="https://example.com", location={"country": "US"})
    """
    with log("firecrawl.scrape", url=url) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            params: dict[str, Any] = {}

            if formats:
                params["formats"] = formats
            if not only_main_content:
                params["onlyMainContent"] = False
            if include_tags:
                params["includeTags"] = include_tags
            if exclude_tags:
                params["excludeTags"] = exclude_tags
            if wait_for is not None:
                params["waitFor"] = wait_for
            if mobile:
                params["mobile"] = True
            if skip_tls_verification:
                params["skipTlsVerification"] = True
            if not remove_base64_images:
                params["removeBase64Images"] = False
            if location:
                params["location"] = location

            result = client.scrape_url(url, params=params if params else None)

            span.add(success=True)
            if isinstance(result, dict):
                span.add(formats=list(result.keys()))
            return result

        except Exception as e:
            error_msg = f"Scrape failed: {e}"
            span.add(error=str(e))
            return error_msg


def scrape_batch(
    *,
    urls: list[str] | list[tuple[str, str]],
    formats: list[
        Literal[
            "markdown", "html", "rawHtml", "links", "screenshot", "screenshot@fullPage"
        ]
    ]
    | None = None,
    only_main_content: bool = True,
    max_workers: int = 5,
) -> dict[str, dict[str, Any] | str]:
    """Scrape multiple URLs concurrently.

    Uses ThreadPoolExecutor for parallel execution with error isolation.

    Args:
        urls: List of URLs to scrape. Each item can be:
            - A string (URL used as key)
            - A tuple of (url, label) for custom labeling
        formats: Output formats (see scrape() for options)
        only_main_content: Extract only main content (default: True)
        max_workers: Maximum concurrent scrapes (default: 5)

    Returns:
        Dict mapping URL/label to scraped content or error message

    Example:
        # Simple list
        firecrawl.scrape_batch(urls=[
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/library/threading.html",
        ])

        # With labels
        firecrawl.scrape_batch(urls=[
            ("https://example.com/page1", "Page 1"),
            ("https://example.com/page2", "Page 2"),
        ])
    """
    normalized = normalize_items(urls)

    with log("firecrawl.scrape_batch", url_count=len(normalized)) as span:

        def _scrape_one(url: str, label: str) -> tuple[str, dict[str, Any] | str]:
            result = scrape(
                url=url,
                formats=formats,
                only_main_content=only_main_content,
            )
            return label, result

        results = batch_execute(_scrape_one, normalized, max_workers=max_workers)
        span.add(success_count=sum(1 for r in results.values() if isinstance(r, dict)))
        return results


def map_urls(
    *,
    url: str,
    search: str | None = None,
    ignore_sitemap: bool = False,
    sitemap_only: bool = False,
    include_subdomains: bool = False,
    limit: int | None = None,
) -> list[str] | str:
    """Discover URLs from a website.

    Maps all accessible URLs from a site via sitemap and crawling.

    Args:
        url: The starting URL to map
        search: Optional search term to filter URLs
        ignore_sitemap: Skip sitemap discovery, only crawl (default: False)
        sitemap_only: Only use sitemap, no crawling (default: False)
        include_subdomains: Include URLs from subdomains (default: False)
        limit: Maximum number of URLs to return

    Returns:
        List of discovered URLs, or error message

    Example:
        # Map entire site
        firecrawl.map_urls(url="https://docs.python.org")

        # Search for specific pages
        firecrawl.map_urls(url="https://docs.python.org", search="asyncio")

        # Limit results
        firecrawl.map_urls(url="https://example.com", limit=100)
    """
    with log("firecrawl.map_urls", url=url, search=search) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            params: dict[str, Any] = {}

            if search:
                params["search"] = search
            if ignore_sitemap:
                params["ignoreSitemap"] = True
            if sitemap_only:
                params["sitemapOnly"] = True
            if include_subdomains:
                params["includeSubdomains"] = True
            if limit:
                params["limit"] = limit

            result = client.map_url(url, params=params if params else None)

            if isinstance(result, list):
                span.add(url_count=len(result))
                return result
            # Handle MapResponse object
            links = getattr(result, "links", None) or []
            span.add(url_count=len(links))
            return links

        except Exception as e:
            error_msg = f"Map failed: {e}"
            span.add(error=str(e))
            return error_msg


def search(
    *,
    query: str,
    limit: int = 5,
    lang: str | None = None,
    country: str | None = None,
    scrape_options: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | str:
    """Search the web and optionally scrape results.

    Performs web search with optional content retrieval for each result.

    Args:
        query: Search query string
        limit: Maximum number of results (default: 5)
        lang: Language code for results (e.g., "en")
        country: Country code for results (e.g., "US")
        scrape_options: Options for scraping result pages (see scrape() params)

    Returns:
        List of search results with optional scraped content, or error message

    Example:
        # Basic search
        firecrawl.search(query="Python async best practices")

        # Search with scraping
        firecrawl.search(
            query="machine learning tutorials",
            limit=3,
            scrape_options={"formats": ["markdown"]}
        )
    """
    with log("firecrawl.search", query=query, limit=limit) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            params: dict[str, Any] = {"limit": limit}

            if lang:
                params["lang"] = lang
            if country:
                params["country"] = country
            if scrape_options:
                params["scrapeOptions"] = scrape_options

            result = client.search(query, params=params)

            if isinstance(result, list):
                span.add(result_count=len(result))
                return result
            # Handle SearchResponse object
            data = getattr(result, "data", None) or []
            span.add(result_count=len(data))
            return data

        except Exception as e:
            error_msg = f"Search failed: {e}"
            span.add(error=str(e))
            return error_msg


def crawl(
    *,
    url: str,
    max_depth: int | None = None,
    limit: int | None = None,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    ignore_sitemap: bool = False,
    scrape_options: dict[str, Any] | None = None,
    webhook: str | None = None,
) -> dict[str, Any] | str:
    """Start an asynchronous multi-page crawl job.

    Crawls a website starting from the given URL. Returns immediately with
    a job ID. Use crawl_status() to poll for results.

    Args:
        url: The starting URL to crawl
        max_depth: Maximum link depth to crawl
        limit: Maximum number of pages to crawl
        include_paths: URL patterns to include (glob syntax)
        exclude_paths: URL patterns to exclude (glob syntax)
        ignore_sitemap: Skip sitemap discovery (default: False)
        scrape_options: Options for scraping pages (see scrape() params)
        webhook: URL to receive completion notification

    Returns:
        Dict with job ID and status URL, or error message

    Example:
        # Start a crawl
        job = firecrawl.crawl(url="https://docs.python.org", max_depth=2, limit=100)

        # Check status
        firecrawl.crawl_status(id=job["id"])
    """
    with log("firecrawl.crawl", url=url, max_depth=max_depth, limit=limit) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            params: dict[str, Any] = {}

            if max_depth is not None:
                params["maxDepth"] = max_depth
            if limit is not None:
                params["limit"] = limit
            if include_paths:
                params["includePaths"] = include_paths
            if exclude_paths:
                params["excludePaths"] = exclude_paths
            if ignore_sitemap:
                params["ignoreSitemap"] = True
            if scrape_options:
                params["scrapeOptions"] = scrape_options
            if webhook:
                params["webhook"] = webhook

            result = client.crawl_url(
                url, params=params if params else None, poll_interval=0
            )

            # Extract job info from response
            if isinstance(result, dict):
                job_id = result.get("id") or result.get("jobId")
                span.add(job_id=job_id)
                return result

            # Handle CrawlResponse object
            job_id = getattr(result, "id", None) or getattr(result, "job_id", None)
            span.add(job_id=job_id)
            return {
                "id": job_id,
                "status": getattr(result, "status", "started"),
                "url": url,
            }

        except Exception as e:
            error_msg = f"Crawl failed: {e}"
            span.add(error=str(e))
            return error_msg


def crawl_status(
    *,
    id: str,
) -> dict[str, Any] | str:
    """Check the status of a crawl job.

    Polls the crawl job for current progress and results.

    Args:
        id: The crawl job ID returned by crawl()

    Returns:
        Dict with status, progress, and results (if complete), or error message

    Example:
        # Check crawl progress
        status = firecrawl.crawl_status(id="abc123")

        if status["status"] == "completed":
            for page in status["data"]:
                print(page["url"])
    """
    with log("firecrawl.crawl_status", job_id=id) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            result = client.check_crawl_status(id)

            if isinstance(result, dict):
                span.add(status=result.get("status"))
                return result

            # Handle CrawlStatusResponse object
            status = getattr(result, "status", "unknown")
            span.add(status=status)

            response: dict[str, Any] = {
                "id": id,
                "status": status,
            }

            # Add optional fields if present
            if hasattr(result, "completed"):
                response["completed"] = result.completed
            if hasattr(result, "total"):
                response["total"] = result.total
            if hasattr(result, "data"):
                response["data"] = result.data

            return response

        except Exception as e:
            error_msg = f"Status check failed: {e}"
            span.add(error=str(e))
            return error_msg


def extract(
    *,
    urls: list[str],
    prompt: str | None = None,
    schema: dict[str, Any] | None = None,
    system_prompt: str | None = None,
    allow_external_links: bool = False,
) -> dict[str, Any] | str:
    """Extract structured data from URLs using LLM.

    Uses an LLM to extract data matching a JSON schema from web pages.

    Args:
        urls: URLs to extract data from
        prompt: Natural language description of what to extract
        schema: JSON schema defining the structure of extracted data
            (OpenAI JSON schema format)
        system_prompt: Custom system prompt for the LLM
        allow_external_links: Follow external links during extraction (default: False)

    Returns:
        Dict with extracted data matching schema, or error message

    Example:
        # Extract with prompt
        firecrawl.extract(
            urls=["https://example.com/products"],
            prompt="Extract product names and prices"
        )

        # Extract with schema
        firecrawl.extract(
            urls=["https://example.com/team"],
            schema={
                "type": "object",
                "properties": {
                    "team_members": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"}
                            }
                        }
                    }
                }
            }
        )
    """
    with log("firecrawl.extract", url_count=len(urls)) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        if not prompt and not schema:
            return "Error: Either prompt or schema is required"

        try:
            params: dict[str, Any] = {"urls": urls}

            if prompt:
                params["prompt"] = prompt
            if schema:
                params["schema"] = schema
            if system_prompt:
                params["systemPrompt"] = system_prompt
            if allow_external_links:
                params["allowExternalLinks"] = True

            result = client.extract(urls, params=params)

            if isinstance(result, dict):
                span.add(success=True)
                return result

            # Handle ExtractResponse object
            data = getattr(result, "data", None)
            span.add(success=True)
            return {"data": data} if data else result

        except Exception as e:
            error_msg = f"Extract failed: {e}"
            span.add(error=str(e))
            return error_msg


def deep_research(
    *,
    prompt: str,
    urls: list[str] | None = None,
    max_depth: int | None = None,
    max_urls: int | None = None,
    time_limit: int | None = None,
) -> dict[str, Any] | str:
    """Run autonomous deep research on a topic.

    Launches an AI agent that autonomously researches a topic by
    searching, crawling, and synthesizing information from the web.

    Args:
        prompt: Research question or topic
        urls: Starting URLs to research (optional, will search if not provided)
        max_depth: Maximum research depth
        max_urls: Maximum URLs to process
        time_limit: Time limit in seconds

    Returns:
        Dict with research results and sources, or error message

    Example:
        # Research a topic
        firecrawl.deep_research(
            prompt="What are the latest developments in quantum computing?",
            max_urls=20
        )

        # Research from specific sources
        firecrawl.deep_research(
            prompt="Compare pricing models",
            urls=["https://company1.com/pricing", "https://company2.com/pricing"]
        )
    """
    with log("firecrawl.deep_research", prompt=prompt[:100]) as span:
        client = _get_client()
        if client is None:
            return "Error: FIRECRAWL_API_KEY secret not configured"

        try:
            params: dict[str, Any] = {}

            if urls:
                params["urls"] = urls
            if max_depth is not None:
                params["maxDepth"] = max_depth
            if max_urls is not None:
                params["maxUrls"] = max_urls
            if time_limit is not None:
                params["timeLimit"] = time_limit

            # The SDK's agent method corresponds to deep research
            result = client.deep_research(prompt, params=params if params else None)

            if isinstance(result, dict):
                span.add(success=True)
                return result

            # Handle response object
            data = getattr(result, "data", None)
            sources = getattr(result, "sources", None)
            span.add(success=True, source_count=len(sources) if sources else 0)
            return {
                "data": data,
                "sources": sources,
            }

        except Exception as e:
            error_msg = f"Deep research failed: {e}"
            span.add(error=str(e))
            return error_msg


if __name__ == "__main__":
    worker_main()
