"""Web content extraction tools using trafilatura.

Provides web page fetching with high-quality content extraction,
supporting single and batch URL processing with configurable output formats.

Reference: https://github.com/adbar/trafilatura
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

# Pack for dot notation: web.fetch(), web.fetch_batch()
pack = "web"

__all__ = ["fetch", "fetch_batch"]

from typing import Any, Literal

import trafilatura
from pydantic import BaseModel, Field
from trafilatura.settings import use_config

from ot.config import get_tool_config
from ot.logging import LogSpan
from ot.utils import (
    batch_execute,
    cache,
    format_batch_results,
    normalize_items,
    truncate,
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


def _get_config() -> Config:
    """Get web pack configuration."""
    return get_tool_config("web", Config)


def _create_config(timeout: float) -> Any:
    """Create trafilatura config with custom settings."""
    config = use_config()
    config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(int(timeout)))
    return config


def _validate_url(url: str) -> None:
    """Validate URL format.

    Args:
        url: The URL to validate

    Raises:
        ValueError: If URL is empty or malformed
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL format: {url}")


def _validate_options(favor_precision: bool, favor_recall: bool) -> None:
    """Validate mutually exclusive options.

    Args:
        favor_precision: Whether precision is favored
        favor_recall: Whether recall is favored

    Raises:
        ValueError: If both options are True
    """
    if favor_precision and favor_recall:
        raise ValueError(
            "Cannot set both favor_precision and favor_recall to True. "
            "Choose one extraction mode: precision (less text, more accurate) "
            "or recall (more text, may include noise)."
        )


def _format_error(
    url: str,
    error: str,
    message: str,
    output_format: str,
) -> str:
    """Format error message, using JSON structure when appropriate.

    Args:
        url: The URL that failed
        error: Error type identifier
        message: Human-readable error message
        output_format: The requested output format

    Returns:
        Formatted error string (JSON if output_format is "json")
    """
    if output_format == "json":
        return json.dumps({"error": error, "url": url, "message": message})
    return f"Error: {message}"


@cache(ttl=300)  # Cache fetched pages for 5 minutes
def _fetch_url_cached(url: str, timeout: float) -> str | None:
    """Fetch URL with caching to avoid redundant requests."""
    with LogSpan(span="web.download", url=url, timeout=timeout) as span:
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
    include_metadata: bool = False,
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
        include_metadata: Include HTTP response metadata (status_code, final_url,
            content_type) in JSON output (default: False, requires output_format="json")
        favor_precision: Prefer precision over recall (default: False)
        favor_recall: Prefer recall over precision (default: False)
        fast: Skip fallback extraction for speed (default: False)
        target_language: Filter by ISO 639-1 language code (e.g., "en")
        max_length: Maximum output length in characters (defaults to config, 0 = unlimited)
        timeout: Request timeout in seconds (defaults to config)
        use_cache: Use cached pages if available (default: True)

    Returns:
        Extracted content in the specified format, or error message on failure

    Raises:
        ValueError: If URL is empty/malformed or if both favor_precision and
            favor_recall are True

    Example:
        # Basic usage with defaults
        content = web.fetch("https://docs.python.org/3/library/asyncio.html")

        # Get plain text with faster extraction
        content = web.fetch(url, output_format="text", fast=True)

        # Include links for research
        content = web.fetch(url, include_links=True)

        # Get content with metadata
        content = web.fetch(url, output_format="json", include_metadata=True)
    """
    # Validate inputs before starting the span
    _validate_url(url)
    _validate_options(favor_precision, favor_recall)

    with LogSpan(span="web.fetch", url=url, output_format=output_format) as s:
        try:
            # Get config values
            pack_config = _get_config()

            if timeout is None:
                timeout = pack_config.timeout
            if max_length is None:
                max_length = pack_config.max_length
            config = _create_config(timeout)

            # Fetch the page (with optional caching)
            if use_cache:
                downloaded = _fetch_url_cached(url, timeout)
            else:
                downloaded = trafilatura.fetch_url(url, config=config)

            if downloaded is None:
                s.add(error="fetch_failed")
                return _format_error(
                    url, "fetch_failed", f"Failed to fetch URL: {url}", output_format
                )

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
                return _format_error(
                    url,
                    "no_content",
                    f"No content could be extracted from: {url}",
                    output_format,
                )

            # Wrap with metadata if requested (JSON only)
            if include_metadata and output_format == "json":
                try:
                    content_data = json.loads(result)
                except json.JSONDecodeError:
                    content_data = result
                result = json.dumps(
                    {
                        "content": content_data,
                        "metadata": {
                            "final_url": url,
                            "content_type": "text/html",
                        },
                    }
                )

            # Truncate if needed
            if max_length > 0:
                result = truncate(
                    result, max_length, indicator="\n\n[Content truncated...]"
                )

            s.add(contentLen=len(result), cached=use_cache)
            return result

        except TimeoutError:
            s.add(error="timeout")
            return _format_error(
                url, "timeout", f"Timeout after {timeout}s fetching: {url}", output_format
            )
        except ConnectionError as e:
            s.add(error="connection_failed")
            return _format_error(
                url, "connection_failed", f"Connection failed for {url}: {e}", output_format
            )
        except Exception as e:
            s.add(error=str(e))
            return _format_error(url, "error", f"Error fetching {url}: {e}", output_format)


def fetch_batch(
    *,
    urls: list[str] | list[tuple[str, str]],
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
        include_images: Include image references (default: False)
        include_tables: Include table content (default: True)
        include_comments: Include comments section (default: False)
        include_formatting: Keep structural elements like headers, lists (default: True)
        favor_precision: Prefer precision over recall (default: False)
        favor_recall: Prefer recall over precision (default: False)
        fast: Skip fallback extraction for speed (default: False)
        target_language: Filter by ISO 639-1 language code (e.g., "en")
        max_length: Max length per URL in characters (defaults to config, 0 = unlimited)
        timeout: Request timeout per URL in seconds (defaults to config)
        use_cache: Use cached pages if available (default: True)
        max_workers: Maximum concurrent fetches (default: 5)

    Returns:
        Concatenated content with section separators

    Raises:
        ValueError: If both favor_precision and favor_recall are True

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
    # Validate mutually exclusive options upfront
    _validate_options(favor_precision, favor_recall)

    normalized = normalize_items(urls)

    with LogSpan(span="web.batch", urlCount=len(normalized), output_format=output_format) as s:

        def _fetch_one(url: str, label: str) -> tuple[str, str]:
            """Fetch a single URL and return (label, result)."""
            result = fetch(
                url=url,
                output_format=output_format,
                include_links=include_links,
                include_images=include_images,
                include_tables=include_tables,
                include_comments=include_comments,
                include_formatting=include_formatting,
                favor_precision=favor_precision,
                favor_recall=favor_recall,
                fast=fast,
                target_language=target_language,
                max_length=max_length,
                timeout=timeout,
                use_cache=use_cache,
            )
            return label, result

        results = batch_execute(_fetch_one, normalized, max_workers=max_workers)
        output = format_batch_results(results, normalized)
        s.add(outputLen=len(output))
        return output
