"""Brave Search API tools.

Provides web search, local search, news search, image search, and video search
via the Brave Search API. Requires BRAVE_API_KEY secret in secrets.yaml.

API docs: https://api-dashboard.search.brave.com/app/documentation
Reference: https://github.com/brave/brave-search-mcp-server
"""

from __future__ import annotations

# Pack for dot notation: brave.search(), brave.news(), etc.
pack = "brave"

__all__ = ["image", "news", "search", "search_batch", "video"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "secrets": ["BRAVE_API_KEY"],
}

import re
from typing import Any, Literal

OutputFormat = Literal["full", "text_only", "sources_only"]

import httpx
from otpack import (
    LogSpan,
    _format_http_error,
    batch_execute_enveloped,
    get_tool_config,
    lazy_client,
    normalize_items,
    require_api_key,
    truncate,
)
from pydantic import BaseModel, Field


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )

BRAVE_API_BASE = "https://api.search.brave.com/res/v1"

# Truncation length for video descriptions (147 chars + "..." = 150 total)
VIDEO_DESC_MAX_LENGTH = 150

def _create_http_client() -> httpx.Client:
    """Create HTTP client for Brave API requests."""
    return httpx.Client(
        base_url=BRAVE_API_BASE,
        timeout=60.0,
        headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
    )


# Thread-safe lazy client using SDK utility
_get_http_client = lazy_client(_create_http_client)


def _get_config() -> Config:
    """Get brave pack configuration."""
    return get_tool_config("brave", Config)


def _get_headers(api_key: str) -> dict[str, str]:
    """Get headers for Brave API requests.

    Args:
        api_key: Pre-fetched Brave API key
    """
    return {
        "X-Subscription-Token": api_key,
    }


def _make_request(
    endpoint: str,
    params: dict[str, Any],
    timeout: float | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Make HTTP GET request to Brave API.

    Args:
        endpoint: API endpoint path (e.g., "/web/search")
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, result). If success, result is parsed JSON dict.
        If failure, result is error message string.
    """
    api_key, err = require_api_key("BRAVE_API_KEY")
    if err:
        return False, err

    if timeout is None:
        timeout = _get_config().timeout

    with LogSpan(
        span="brave.request", endpoint=endpoint, query=params.get("q", "")
    ) as span:
        try:
            client = _get_http_client()
            if client is None:
                return False, "Error: HTTP client not initialized"
            response = client.get(
                endpoint,
                params=params,
                headers=_get_headers(api_key),
                timeout=timeout,
            )
            response.raise_for_status()

            result = response.json()
            span.add(status=response.status_code)
            return True, result

        except Exception as e:
            span.add(error=f"{type(e).__name__}: {e}")
            return False, _format_http_error(e)


def _format_sources(
    results: list[dict[str, Any]], *, max_sources: int | None = None
) -> str:
    """Format source URLs as a numbered deduplicated markdown link list."""
    seen_urls: set[str] = set()
    lines: list[str] = []
    num = 0
    for result in results:
        url = result.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        num += 1
        if max_sources is not None and num > max_sources:
            break
        title = result.get("title", "") or url
        lines.append(f"{num}. [{title}]({url})")
    return "\n".join(lines)


def _format_web_results(
    data: dict[str, Any],
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Format web search results for display."""
    web = data.get("web", {})
    results = web.get("results", [])

    if not results:
        return "No results found."

    if output_format == "sources_only":
        return _format_sources(results, max_sources=max_sources) or "No sources found."

    if output_format == "text_only":
        lines: list[str] = []
        for result in results:
            title = result.get("title", "No title")
            description = result.get("description", "")
            lines.append(title)
            if description:
                lines.append(description)
            lines.append("")
        return "\n".join(lines).strip()

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")
        age = result.get("age", "")
        is_live = result.get("is_live", False)

        prefix = "[LIVE] " if is_live else ""
        lines.append(f"{i}. {prefix}{title}")
        if age:
            lines.append(f"   {age}")
        lines.append(f"   {url}")
        if description:
            lines.append(f"   {description}")
        lines.append("")

    sources_text = _format_sources(results, max_sources=max_sources)
    if sources_text:
        lines.append("## Sources")
        lines.append(sources_text)
        lines.append("")

    return "\n".join(lines)


def _format_news_results(
    data: dict[str, Any],
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Format news search results for display."""
    results = data.get("results", [])

    if not results:
        return "No news results found."

    # Sort by page_age (ISO date string) most-recent first; items without it go last
    results = sorted(
        results,
        key=lambda r: r.get("page_age") or "",
        reverse=True,
    )

    if output_format == "sources_only":
        return _format_sources(results, max_sources=max_sources) or "No sources found."

    if output_format == "text_only":
        lines: list[str] = []
        for result in results:
            title = result.get("title", "No title")
            source = result.get("meta_url", {}).get("hostname", "")
            age = result.get("age", "")
            lines.append(title)
            details = ", ".join(part for part in [source, age] if part)
            if details:
                lines.append(details)
            lines.append("")
        return "\n".join(lines).strip()

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        source = result.get("meta_url", {}).get("hostname", "")
        age = result.get("age", "")
        breaking = result.get("breaking", False)
        is_live = result.get("is_live", False)

        prefix = ""
        if breaking:
            prefix += "[BREAKING] "
        if is_live:
            prefix += "[LIVE] "
        lines.append(f"{i}. {prefix}{title}")
        if source:
            lines.append(f"   Source: {source} ({age})")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)



def _format_image_results(
    data: dict[str, Any],
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Format image search results for display."""
    results = data.get("results", [])

    if not results:
        return "No image results found."

    if output_format == "sources_only":
        return _format_sources(results, max_sources=max_sources) or "No sources found."

    if output_format == "text_only":
        lines: list[str] = []
        for result in results:
            title = result.get("title", "") or "No title"
            source = result.get("source", "")
            lines.append(title)
            if source:
                lines.append(f"Source: {source}")
            lines.append("")
        return "\n".join(lines).strip()

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "") or "No title"
        url = result.get("url", "")
        source = result.get("source", "")
        props = result.get("properties", {})
        width = props.get("width", "")
        height = props.get("height", "")
        image_url = props.get("url", "")
        confidence = result.get("confidence", "")

        lines.append(f"{i}. {title}")
        if confidence:
            lines.append(f"   Confidence: {confidence}")
        if width and height:
            lines.append(f"   Size: {width}x{height}")
        if source:
            lines.append(f"   Source: {source}")
        if image_url:
            lines.append(f"   Image: {image_url}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


def _format_video_results(
    data: dict[str, Any],
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Format video search results for display."""
    results = data.get("results", [])

    if not results:
        return "No video results found."

    if output_format == "sources_only":
        return _format_sources(results, max_sources=max_sources) or "No sources found."

    if output_format == "text_only":
        lines: list[str] = []
        for result in results:
            title = result.get("title", "No title")
            description = result.get("description", "")
            lines.append(title)
            if description:
                lines.append(truncate(description, VIDEO_DESC_MAX_LENGTH))
            lines.append("")
        return "\n".join(lines).strip()

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")
        video_data = result.get("video", {}) or {}
        creator_obj = video_data.get("creator", {}) or {}
        creator = (
            creator_obj.get("name", "")
            or creator_obj.get("long_name", "")
            or result.get("meta_url", {}).get("hostname", "")
        )
        duration = video_data.get("duration", "")
        views = video_data.get("views", "")

        lines.append(f"{i}. {title}")
        if creator:
            lines.append(f"   Creator: {creator}")
        if duration:
            lines.append(f"   Duration: {duration}")
        if views:
            lines.append(f"   Views: {views}")
        if description:
            lines.append(f"   {truncate(description, VIDEO_DESC_MAX_LENGTH)}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


_DATE_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}$")
_FRESHNESS_VALUES = frozenset(["pd", "pw", "pm", "py"])
_SAFESEARCH_WEB_VALUES = frozenset(["off", "moderate", "strict"])
_SAFESEARCH_IMAGE_VALUES = frozenset(["off", "strict"])
_OUTPUT_FORMAT_VALUES = frozenset(["full", "text_only", "sources_only"])
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _validate_freshness(freshness: str | None) -> str | None:
    """Validate freshness value. Returns error string or None if valid."""
    if freshness is None:
        return None
    if freshness in _FRESHNESS_VALUES or _DATE_RANGE_RE.match(freshness):
        return None
    return (
        f"Error: Invalid freshness '{freshness}'. "
        f"Use {sorted(_FRESHNESS_VALUES)} or YYYY-MM-DDtoYYYY-MM-DD"
    )


def _validate_safesearch(safesearch: str, valid_values: frozenset[str]) -> str | None:
    """Validate safesearch value. Returns error string or None if valid."""
    if safesearch in valid_values:
        return None
    return f"Error: Invalid safesearch '{safesearch}'. Use {sorted(valid_values)}"


def _validate_count(count: int) -> str | None:
    """Validate count is in range 1-20. Returns error string or None if valid."""
    if 1 <= count <= 20:
        return None
    return f"Error: count must be between 1 and 20 (got {count})"


def _validate_offset(offset: int) -> str | None:
    """Validate offset is in range 0-9. Returns error string or None if valid."""
    if 0 <= offset <= 9:
        return None
    return f"Error: offset must be between 0 and 9 (got {offset})"


def _validate_output_format(output_format: str) -> str | None:
    """Validate output_format value. Returns error string or None if valid."""
    if output_format in _OUTPUT_FORMAT_VALUES:
        return None
    return f"Error: Invalid output_format '{output_format}'. Use {sorted(_OUTPUT_FORMAT_VALUES)}"


def _validate_country(country: str) -> str | None:
    """Validate country is a 2-letter uppercase code. Returns error string or None if valid."""
    if _COUNTRY_RE.match(country):
        return None
    return f"Error: Invalid country '{country}'. Use a 2-letter uppercase country code (e.g. 'US', 'GB')"


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value between min and max."""
    return min(max(value, min_val), max_val)


def _validate_query(query: str) -> str | None:
    """Validate query against Brave API limits.

    Returns None if valid, error message if invalid.
    """
    if not query or not query.strip():
        return "Error: Query cannot be empty"
    if len(query) > 400:
        return f"Error: Query exceeds 400 character limit ({len(query)} chars)"
    word_count = len(query.split())
    if word_count > 50:
        return f"Error: Query exceeds 50 word limit ({word_count} words)"
    return None


def search(
    *,
    query: str,
    count: int = 10,
    offset: int = 0,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "moderate",
    freshness: str | None = None,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Search the web using Brave Search API.

    Args:
        query: Search query (max 400 chars, 50 words)
        count: Number of results to return (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")
        safesearch: Content filter - "off", "moderate", "strict" (default: "moderate")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")
        output_format: Controls response structure:
            - "full" (default): numbered results with titles, ages, URLs, descriptions,
              and a ## Sources section
            - "text_only": plain text titles and descriptions (no URLs/source list)
            - "sources_only": numbered markdown link list of sources only
        max_sources: Maximum number of sources in the ## Sources section or
            sources_only list (default: None, all sources)

    Returns:
        Formatted search results or error message

    Example:
        # Basic search
        brave.search(query="Python async best practices")

        # Recent results only
        brave.search(query="AI news", freshness="pw", count=5)

        # Sources only for piping or extraction
        brave.search(query="Python tutorials", output_format="sources_only")
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_offset(offset):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_WEB_VALUES):
        return error
    if error := _validate_freshness(freshness):
        return error
    if error := _validate_output_format(output_format):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "offset": offset,
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/web/search", params)

    if not success:
        return str(result)

    return _format_web_results(result, output_format=output_format, max_sources=max_sources)  # type: ignore[arg-type]


def news(
    *,
    query: str,
    count: int = 10,
    offset: int = 0,
    country: str = "US",
    search_lang: str = "en",
    freshness: str | None = None,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Search news articles using Brave Search API.

    Uses the dedicated /news/search endpoint for better news results.
    Results are sorted by publication date, most recent first.

    Args:
        query: Search query for news
        count: Number of results (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")
        output_format: Controls response structure:
            - "full" (default): numbered results with source, age, and URL;
              [BREAKING] and [LIVE] flags when applicable
            - "text_only": plain text titles with source/age context (no URLs/source list)
            - "sources_only": numbered markdown link list of sources only
        max_sources: Maximum number of sources in sources_only list (default: None)

    Returns:
        Formatted news results or error message

    Example:
        # Today's tech news
        brave.news(query="artificial intelligence", freshness="pd")

        # UK news
        brave.news(query="technology", country="GB", count=5)

        # Sources only
        brave.news(query="AI funding", output_format="sources_only")
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_offset(offset):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_freshness(freshness):
        return error
    if error := _validate_output_format(output_format):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "offset": offset,
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/news/search", params)

    if not success:
        return str(result)
    return _format_news_results(result, output_format=output_format, max_sources=max_sources)  # type: ignore[arg-type]



def image(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "strict",
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Search for images using Brave Search API.

    Uses the dedicated /images/search endpoint.

    Args:
        query: Search query for images
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        safesearch: Content filter - "off" or "strict" (default: "strict")
        output_format: Controls response structure:
            - "full" (default): title, confidence, size, source, image URL, page URL
            - "text_only": plain text titles with source labels (no URLs/source list)
            - "sources_only": numbered markdown link list of page URLs only
        max_sources: Maximum number of sources in sources_only list (default: None)

    Returns:
        Formatted image results with URLs, sizes, and sources

    Example:
        brave.image(query="Python programming logo")
        brave.image(query="architecture diagrams", count=5)
        brave.image(query="infographics", output_format="sources_only")
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_IMAGE_VALUES):
        return error
    if error := _validate_output_format(output_format):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    success, result = _make_request("/images/search", params)

    if not success:
        return str(result)
    return _format_image_results(result, output_format=output_format, max_sources=max_sources)  # type: ignore[arg-type]


def video(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    freshness: str | None = None,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Search for videos using Brave Search API.

    Uses the dedicated /videos/search endpoint.

    Args:
        query: Search query for videos
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")
        output_format: Controls response structure:
            - "full" (default): title, creator, duration, views, description, URL
            - "text_only": plain text titles and descriptions (no URLs/source list)
            - "sources_only": numbered markdown link list of video URLs only
        max_sources: Maximum number of sources in sources_only list (default: None)

    Returns:
        Formatted video results with titles, creators, durations, and URLs

    Example:
        brave.video(query="Python tutorial for beginners")
        brave.video(query="tech conference keynote", freshness="pm", count=5)
        brave.video(query="machine learning lectures", output_format="sources_only")
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_freshness(freshness):
        return error
    if error := _validate_output_format(output_format):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/videos/search", params)

    if not success:
        return str(result)
    return _format_video_results(result, output_format=output_format, max_sources=max_sources)  # type: ignore[arg-type]


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    count: int = 2,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "moderate",
    freshness: str | None = None,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
    retries: int = 0,
    retry_delay_ms: int = 250,
) -> dict[str, Any] | str:
    """Execute multiple web searches concurrently and return combined results.

    Queries are executed in parallel using threads for better performance.

    Args:
        queries: List of queries. Each item can be:
                 - A string (query text, used as both query and label)
                 - A tuple of (query, label) for custom labeling
        count: Number of results per query (1-20, default: 2)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")
        safesearch: Content filter - "off", "moderate", "strict" (default: "moderate")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")
        output_format: Controls response structure for each query - "full" (default)
            "text_only", or "sources_only" (see brave.search for details)
        max_sources: Maximum number of sources per query (default: None)

    Returns:
        Structured batch result envelope with `results[]` and `meta`

    Example:
        # Simple list of queries
        brave.search_batch(queries=["scipy", "sqlalchemy", "jupyterlab"])

        # With custom labels
        brave.search_batch(queries=[
            ("current Gold price USD/oz today", "Gold (USD/oz)"),
            ("current Silver price USD/oz today", "Silver (USD/oz)"),
            ("current Copper price USD/lb today", "Copper (USD/lb)"),
        ])

        # Sources only across multiple queries
        brave.search_batch(queries=["fastapi", "django"], output_format="sources_only")
    """
    if error := _validate_count(count):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_WEB_VALUES):
        return error
    if error := _validate_freshness(freshness):
        return error
    if error := _validate_output_format(output_format):
        return error

    normalized = normalize_items(queries)

    if not normalized:
        return "Error: No queries provided"

    # Fall back empty labels to query text
    normalized = [(q, label or q) for q, label in normalized]

    with LogSpan(span="brave.batch", queryCount=len(normalized), count=count) as s:

        def _search_one(query: str, _label: str) -> str:
            """Execute a single search and return raw result payload."""
            return search(
                query=query,
                count=count,
                country=country,
                search_lang=search_lang,
                safesearch=safesearch,
                freshness=freshness,
                output_format=output_format,
                max_sources=max_sources,
            )

        output = batch_execute_enveloped(
            _search_one,
            normalized,
            retries=retries,
            retry_delay_ms=retry_delay_ms,
            max_workers=min(len(normalized), 10),
        )
        s.add(successCount=output["meta"]["success_count"], errorCount=output["meta"]["error_count"])
        return output
