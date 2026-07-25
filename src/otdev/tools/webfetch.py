"""Web content extraction tools using trafilatura.

Provides web page fetching with high-quality content extraction,
supporting single and batch URL processing with configurable output formats.

Reference: https://github.com/adbar/trafilatura
"""

from __future__ import annotations

# Pack for dot notation: webfetch.fetch(), webfetch.fetch_batch()
pack = "webfetch"
pack_aliases = ("wf",)
doc_slug = "webfetch"

__all__ = ["fetch", "fetch_batch"]

import json
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from otpack import (
    LogSpan,
    batch_execute,
    cache,
    format_batch_results,
    get_tool_config,
    normalize_items,
    truncate,
)


def _require_trafilatura() -> None:
    """Check trafilatura is available, raise helpful error if not."""
    try:
        import trafilatura  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Web tools require the [dev] extra. "
            "Install with: pip install onetool-mcp[dev]"
        ) from exc


class Config(BaseModel):
    """Pack configuration - discovered by registry.

    Deliberately minimal: no retry or custom UA/headers — add on demand.
    """

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
    max_download_bytes: int = Field(
        default=20_000_000,
        ge=100_000,
        description=(
            "Reject responses larger than this many bytes before extraction "
            "(enforced by trafilatura as MAX_FILE_SIZE)"
        ),
    )
    block_private_urls: bool = Field(
        default=False,
        description=(
            "Refuse to fetch URLs whose host resolves to a private, loopback, "
            "link-local, or reserved address (best-effort SSRF guard)"
        ),
    )


def _get_config() -> Config:
    """Get webfetch pack configuration."""
    return get_tool_config("webfetch", Config)


def _create_config(timeout: float) -> Any:
    """Create trafilatura config with custom settings."""
    from trafilatura.settings import use_config

    config = use_config()
    config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(int(timeout)))
    config.set("DEFAULT", "MAX_FILE_SIZE", str(_get_config().max_download_bytes))
    return config


def _validate_url(url: str) -> str | None:
    """Validate URL format.

    Args:
        url: The URL to validate

    Returns:
        Error string if invalid, None if valid
    """
    if not url or not url.strip():
        return "Error: URL cannot be empty"
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return f"Error: Invalid URL format: {url}"
    return None


def _is_loopback_url(url: str) -> bool:
    """Return True when URL points to a local loopback host."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _is_private_url(url: str) -> bool:
    """Best-effort check that a URL's host is private/loopback/link-local.

    Resolves hostnames via DNS; unresolvable hosts are treated as public
    (the fetch will fail on its own). Not a hard security boundary.
    """
    import ipaddress
    import socket

    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _validate_options(favor_precision: bool, favor_recall: bool) -> str | None:
    """Validate mutually exclusive options.

    Args:
        favor_precision: Whether precision is favored
        favor_recall: Whether recall is favored

    Returns:
        Error string if invalid, None if valid
    """
    if favor_precision and favor_recall:
        return (
            "Error: Cannot set both favor_precision and favor_recall to True. "
            "Choose one extraction mode: precision (less text, more accurate) "
            "or recall (more text, may include noise)."
        )
    return None


def _is_html_content_type(content_type: str | None) -> bool:
    """Check if content type indicates HTML content."""
    if not content_type:
        return True  # Assume HTML if no content type (legacy behavior)
    ct_lower = content_type.lower().split(";")[0].strip()
    return ct_lower in ("text/html", "application/xhtml+xml")


def _fetch_url(url: str, timeout: float) -> tuple[str | None, str | None, str]:
    """Fetch a URL.

    Returns:
        Tuple of (content, content_type, final_url). Content is the decoded
        response, content_type is the Content-Type header value, final_url is
        the post-redirect URL (falls back to the requested URL).
    """
    with LogSpan(span="webfetch.download", url=url, timeout=timeout) as span:
        import trafilatura

        config = _create_config(timeout)
        response = trafilatura.fetch_response(
            url, config=config, with_headers=True, decode=True
        )
        if response is None:
            span.add(success=False)
            return None, None, url
        content = response.html
        content_type = (
            response.headers.get("content-type") if response.headers else None
        )
        final_url = getattr(response, "url", None) or url
        span.add(success=content is not None, contentType=content_type)
        if content:
            span.add(responseLen=len(content))
        return content, content_type, final_url


@cache.memoize(ttl=300)  # Cache fetched pages for 5 minutes
def _fetch_url_cached(url: str, timeout: float) -> tuple[str | None, str | None, str]:
    """Cached variant of _fetch_url."""
    return _fetch_url(url, timeout)


def fetch(
    *,
    url: str,
    output_format: Literal["text", "markdown", "json", "html"] = "markdown",
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

    For non-HTML content types (text/plain, application/json, text/xml, text/csv,
    etc.), returns the raw content directly without extraction.

    Args:
        url: The URL to fetch
        output_format: Output format - "text", "markdown" (default), "json", or "html"
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
        Extracted content in the specified format, or error string on failure
        (empty URL, malformed URL, conflicting options, network error, etc.)

    Example:
        # Basic usage with defaults
        content = webfetch.fetch(url="https://docs.python.org/3/library/asyncio.html")

        # Get plain text with faster extraction
        content = webfetch.fetch(url=url, output_format="text", fast=True)

        # Include links for research
        content = webfetch.fetch(url=url, include_links=True)

        # Get content with metadata
        content = webfetch.fetch(url=url, output_format="json", include_metadata=True)
    """
    # Validate inputs before starting the span
    _require_trafilatura()
    if error := _validate_url(url):
        return error
    if error := _validate_options(favor_precision, favor_recall):
        return error

    with LogSpan(span="webfetch.fetch", url=url, outputFormat=output_format) as s:
        try:
            # Get config values
            pack_config = _get_config()

            if timeout is None:
                timeout = pack_config.timeout
            if max_length is None:
                max_length = pack_config.max_length
            config = _create_config(timeout)

            import trafilatura

            # Fetch the page (with optional caching)
            if _get_config().block_private_urls and _is_private_url(url):
                s.add(error="private_url_blocked")
                return (
                    f"Error: Refusing to fetch private/internal URL: {url} "
                    "(tools.webfetch.block_private_urls is enabled)"
                )

            fetcher = _fetch_url_cached if use_cache else _fetch_url
            downloaded, content_type, final_url = fetcher(url, timeout)

            if downloaded is None:
                s.add(error="fetch_failed")
                if _is_loopback_url(url):
                    return (
                        f"Error: Failed to fetch loopback URL: {url}. "
                        "This runtime may block local loopback networking; "
                        "use a publicly reachable fixture URL or load local files with file tools."
                    )
                return f"Error: Failed to fetch URL: {url}"

            # For non-HTML content, return raw content directly (no extraction needed)
            if not _is_html_content_type(content_type):
                s.add(contentType=content_type, rawContent=True)
                result = downloaded
            else:
                # Map output format to trafilatura format
                trafilatura_format: str = output_format
                if output_format == "text":
                    trafilatura_format = "txt"

                # Extract content from HTML
                extracted = trafilatura.extract(
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

                if extracted is None:
                    s.add(error="no_content")
                    return f"Error: No content could be extracted from: {url}"
                result = extracted

            # Wrap with metadata if requested (JSON only)
            if include_metadata and output_format == "json":
                try:
                    content_data = json.loads(result)
                except json.JSONDecodeError:
                    content_data = result
                extracted_metadata: dict[str, Any] = {}
                if isinstance(content_data, dict):
                    for field in ("title", "author", "date"):
                        value = content_data.get(field)
                        if value not in (None, ""):
                            extracted_metadata[field] = value
                result = json.dumps(
                    {
                        "content": content_data,
                        "metadata": {
                            "final_url": final_url,
                            "content_type": content_type,
                            **extracted_metadata,
                        },
                    }
                )

            # Truncate if needed
            if max_length > 0:
                result = truncate(
                    result, max_length, indicator="\n\n[Content truncated...]"
                )

            s.add(contentLen=len(result), cacheEnabled=use_cache)
            return result

        except TimeoutError:
            s.add(error="timeout")
            return f"Error: Timeout after {timeout}s fetching: {url}"
        except ConnectionError as e:
            s.add(error="connection_failed")
            if _is_loopback_url(url):
                return (
                    f"Error: Connection failed for loopback URL {url}: {e}. "
                    "Loopback networking may be restricted in this runtime."
                )
            return f"Error: Connection failed for {url}: {e}"
        except Exception as e:
            s.add(error=str(e))
            return f"Error: Error fetching {url}: {e}"


def fetch_batch(
    *,
    urls: list[str] | list[tuple[str, str]],
    output_format: Literal["text", "markdown", "json", "html"] = "markdown",
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
        output_format: Output format - "text", "markdown" (default), "json", or "html"
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

    Example:
        # Simple list of URLs
        content = webfetch.fetch_batch(urls=[
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/library/threading.html",
        ])

        # With custom labels
        content = webfetch.fetch_batch(urls=[
            ("https://fastapi.tiangolo.com/tutorial/", "FastAPI Tutorial"),
            ("https://docs.pydantic.dev/latest/", "Pydantic Docs"),
        ])
    """
    # Validate mutually exclusive options upfront
    if error := _validate_options(favor_precision, favor_recall):
        return error

    normalized = normalize_items(urls)

    with LogSpan(
        span="webfetch.batch", urlCount=len(normalized), output_format=output_format
    ) as s:

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
