# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "pydantic>=2.0.0", "pyyaml>=6.0.0", "trafilatura>=2.0.0"]
# ///
"""Web content extraction tools using trafilatura.

Provides web page fetching with high-quality content extraction,
supporting single and batch URL processing with configurable output formats.

Reference: https://github.com/adbar/trafilatura
"""

from __future__ import annotations

# Pack for dot notation: web.fetch(), web.fetch_batch()
pack = "web"

__all__ = ["fetch", "fetch_batch"]

from typing import Any, Literal

import trafilatura
from pydantic import BaseModel, Field
from trafilatura.settings import use_config

from ot_sdk import (
    batch_execute,
    cache,
    format_batch_results,
    get_config,
    log,
    normalize_items,
    truncate,
    worker_main,
)


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )
    max_length: int = Field(
        default=50000,
        ge=1000,
        le=500000,
        description="Maximum content length in characters",
    )


def _create_config(timeout: float) -> Any:
    """Create trafilatura config with custom settings."""
    config = use_config()
    config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(int(timeout)))
    return config


@cache(ttl=300)  # Cache fetched pages for 5 minutes
def _fetch_url_cached(url: str, timeout: float) -> str | None:
    """Fetch URL with caching to avoid redundant requests."""
    with log("web.download", url=url, timeout=timeout) as span:
        config = _create_config(timeout)
        result = trafilatura.fetch_url(url, config=config)
        span.add(success=result is not None)
        if result:
            span.add(responseLen=len(result))
        return result


def fetch(
    *,
    url: str,
    output_format: Literal["text", "markdown", "json"] = "markdown",
    include_links: bool = False,
    include_images: bool = False,
    include_tables: bool = True,
    include_comments: bool = False,
    include_formatting: bool = True,
    favor_precision: bool = False,
    favor_recall: bool = False,
    fast: bool = False,
    target_language: str | None = None,
    max_length: int | None = None,
    timeout: float | None = None,
    use_cache: bool = True,
) -> str:
    """Fetch and extract main content from a web page.

    Uses trafilatura to extract the main content, filtering out navigation,
    ads, and boilerplate. Returns clean text optimized for LLM consumption.

    Args:
        url: The URL to fetch
        output_format: Output format - "text", "markdown" (default), or "json"
        include_links: Include hyperlinks in output (default: False)
        include_images: Include image references (default: False)
        include_tables: Include table content (default: True)
        include_comments: Include comments section (default: False)
        include_formatting: Keep structural elements like headers, lists (default: True)
        favor_precision: Prefer precision over recall (default: False)
        favor_recall: Prefer recall over precision (default: False)
        fast: Skip fallback extraction for speed (default: False)
        target_language: Filter by ISO 639-1 language code (e.g., "en")
        max_length: Maximum output length in characters (defaults to config, 0 = unlimited)
        timeout: Request timeout in seconds (defaults to config)
        use_cache: Use cached pages if available (default: True)

    Returns:
        Extracted content in the specified format, or error message on failure

    Example:
        # Basic usage with defaults
        content = web.fetch("https://docs.python.org/3/library/asyncio.html")

        # Get plain text with faster extraction
        content = web.fetch(url, output_format="text", fast=True)

        # Include links for research
        content = web.fetch(url, include_links=True)
    """
    with log("web.fetch", url=url, output_format=output_format) as s:
        try:
            # Get config values
            web_timeout = get_config("tools.web_fetch.timeout") or 30.0
            web_max_length = get_config("tools.web_fetch.max_length") or 50000

            if timeout is None:
                timeout = web_timeout
            if max_length is None:
                max_length = web_max_length
            config = _create_config(timeout)

            # Fetch the page (with optional caching)
            if use_cache:
                downloaded = _fetch_url_cached(url, timeout)
            else:
                downloaded = trafilatura.fetch_url(url, config=config)

            if downloaded is None:
                s.add(error="fetch_failed")
                return f"Error: Failed to fetch URL: {url}"

            # Map output format to trafilatura format
            trafilatura_format: str = output_format
            if output_format == "text":
                trafilatura_format = "txt"

            # Extract content
            result = trafilatura.extract(
                downloaded,
                url=url,
                output_format=trafilatura_format,
                include_links=include_links,
                include_images=include_images,
                include_tables=include_tables,
                include_comments=include_comments,
                include_formatting=include_formatting,
                favor_precision=favor_precision,
                favor_recall=favor_recall,
                fast=fast,
                target_language=target_language,
                with_metadata=output_format == "json",
                config=config,
            )

            if result is None:
                s.add(error="no_content")
                return f"Error: No content could be extracted from: {url}"

            # Truncate if needed
            if max_length > 0:
                result = truncate(
                    result, max_length, indicator="\n\n[Content truncated...]"
                )

            s.add(contentLen=len(result), cached=use_cache)
            return result

        except Exception as e:
            s.add(error=str(e))
            return f"Error fetching {url}: {e}"


def fetch_batch(
    *,
    urls: list[str] | list[tuple[str, str]],
    output_format: Literal["text", "markdown", "json"] = "markdown",
    include_links: bool = False,
    include_tables: bool = True,
    fast: bool = False,
    max_length: int | None = None,
    timeout: float | None = None,
    max_workers: int = 5,
) -> str:
    """Fetch multiple URLs concurrently and return concatenated results.

    Fetches all URLs in parallel using threads, then concatenates the results
    with clear section separators. Failed fetches include error messages.

    Args:
        urls: List of URLs to fetch. Each item can be:
              - A string (URL used as both source and label)
              - A tuple of (url, label) for custom section labels
        output_format: Output format - "text", "markdown" (default), or "json"
        include_links: Include hyperlinks in output (default: False)
        include_tables: Include table content (default: True)
        fast: Skip fallback extraction for speed (default: False)
        max_length: Max length per URL in characters (defaults to config, 0 = unlimited)
        timeout: Request timeout per URL in seconds (defaults to config)
        max_workers: Maximum concurrent fetches (default: 5)

    Returns:
        Concatenated content with section separators

    Example:
        # Simple list of URLs
        content = web.fetch_batch([
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/library/threading.html",
        ])

        # With custom labels
        content = web.fetch_batch([
            ("https://fastapi.tiangolo.com/tutorial/", "FastAPI Tutorial"),
            ("https://docs.pydantic.dev/latest/", "Pydantic Docs"),
        ])
    """
    normalized = normalize_items(urls)

    with log("web.batch", urlCount=len(normalized), output_format=output_format) as s:

        def _fetch_one(url: str, label: str) -> tuple[str, str]:
            """Fetch a single URL and return (label, result)."""
            result = fetch(
                url=url,
                output_format=output_format,
                include_links=include_links,
                include_tables=include_tables,
                fast=fast,
                max_length=max_length,
                timeout=timeout,
            )
            return label, result

        results = batch_execute(_fetch_one, normalized, max_workers=max_workers)
        output = format_batch_results(results, normalized)
        s.add(outputLen=len(output))
        return output


if __name__ == "__main__":
    worker_main()
