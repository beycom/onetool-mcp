"""Brave Search API tools.

Provides web search, local search, news search, image search, video search,
and AI summarization via the Brave Search API.
Requires BRAVE_API_KEY secret in secrets.yaml.

API docs: https://api-dashboard.search.brave.com/app/documentation
Reference: https://github.com/brave/brave-search-mcp-server
"""

from __future__ import annotations

# Pack for dot notation: brave.search(), brave.news(), etc.
pack = "brave"

__all__ = ["image", "local", "news", "search", "search_batch", "summarize", "video"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "secrets": ["BRAVE_API_KEY"],
}

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan
from ot.utils import batch_execute, format_batch_results, normalize_items


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

# Shared HTTP client for connection pooling
_client = httpx.Client(
    base_url=BRAVE_API_BASE,
    timeout=60.0,
    headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
)


def _get_config() -> Config:
    """Get brave pack configuration."""
    return get_tool_config("brave", Config)


def _get_api_key() -> str:
    """Get Brave API key from secrets."""
    return get_secret("BRAVE_API_KEY") or ""


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
    api_key = _get_api_key()
    if not api_key:
        return False, "Error: BRAVE_API_KEY secret not configured"

    if timeout is None:
        timeout = _get_config().timeout

    with LogSpan(
        span="brave.request", endpoint=endpoint, query=params.get("q", "")
    ) as span:
        try:
            response = _client.get(
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
            error_type = type(e).__name__
            span.add(error=f"{error_type}: {e}")

            if hasattr(e, "response"):
                status = getattr(e.response, "status_code", "unknown")
                text = getattr(e.response, "text", "")[:200]
                return False, f"HTTP error ({status}): {text}"
            return False, f"Request failed: {e}"


def _format_web_results(data: dict[str, Any]) -> str:
    """Format web search results for display."""
    lines: list[str] = []

    web = data.get("web", {})
    results = web.get("results", [])

    if not results:
        return "No results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")

        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if description:
            lines.append(f"   {description}")
        lines.append("")

    return "\n".join(lines)


def _format_news_results(data: dict[str, Any]) -> str:
    """Format news search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No news results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        source = result.get("meta_url", {}).get("hostname", "")
        age = result.get("age", "")
        breaking = result.get("breaking", False)

        prefix = "[BREAKING] " if breaking else ""
        lines.append(f"{i}. {prefix}{title}")
        if source:
            lines.append(f"   Source: {source} ({age})")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


def _format_local_results_from_web(data: dict[str, Any]) -> str:
    """Format local results from web search with locations filter."""
    lines: list[str] = []

    locations = data.get("locations", {})
    results = locations.get("results", [])

    if not results:
        # Fall back to web results if no locations
        return _format_web_results(data)

    for i, result in enumerate(results, 1):
        name = result.get("title", "No name")

        lines.append(f"{i}. {name}")

        # Address
        address = result.get("address", {})
        if address:
            addr_parts = [
                address.get("streetAddress", ""),
                address.get("addressLocality", ""),
                address.get("addressRegion", ""),
            ]
            addr_str = ", ".join(p for p in addr_parts if p)
            if addr_str:
                lines.append(f"   Address: {addr_str}")

        # Rating
        rating = result.get("rating", {})
        if rating:
            stars = rating.get("ratingValue", "")
            count = rating.get("ratingCount", "")
            if stars:
                lines.append(f"   Rating: {stars}/5 ({count} reviews)")

        # Phone
        phone = result.get("phone", "")
        if phone:
            lines.append(f"   Phone: {phone}")

        lines.append("")

    return "\n".join(lines)


def _format_image_results(data: dict[str, Any]) -> str:
    """Format image search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No image results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        source = result.get("source", "")
        width = result.get("properties", {}).get("width", "")
        height = result.get("properties", {}).get("height", "")

        lines.append(f"{i}. {title}")
        if width and height:
            lines.append(f"   Size: {width}x{height}")
        if source:
            lines.append(f"   Source: {source}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


def _format_video_results(data: dict[str, Any]) -> str:
    """Format video search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No video results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")
        creator = result.get("meta_url", {}).get("hostname", "")
        duration = result.get("video", {}).get("duration", "")
        views = result.get("video", {}).get("views", "")

        lines.append(f"{i}. {title}")
        if creator:
            lines.append(f"   Channel: {creator}")
        if duration:
            lines.append(f"   Duration: {duration}")
        if views:
            lines.append(f"   Views: {views}")
        if description:
            if len(description) > VIDEO_DESC_MAX_LENGTH:
                description = description[: VIDEO_DESC_MAX_LENGTH - 3] + "..."
            lines.append(f"   {description}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value between min and max."""
    return min(max(value, min_val), max_val)


def _validate_query(query: str) -> str | None:
    """Validate query against Brave API limits.

    Returns None if valid, error message if invalid.
    """
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
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
    freshness: Literal["pd", "pw", "pm", "py"] | None = None,
    summary: bool = False,
) -> str:
    """Search the web using Brave Search API.

    Args:
        query: Search query (max 400 chars, 50 words)
        count: Number of results to return (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")
        safesearch: Content filter - "off", "moderate", "strict" (default: "moderate")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year)
        summary: Include AI-generated summary (requires Pro plan)

    Returns:
        YAML flow style search results or error message

    Example:
        # Basic search
        brave.search(query="Python async best practices")

        # Recent results only
        brave.search(query="AI news", freshness="pw", count=5)
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": _clamp(count, 1, 20),
        "offset": _clamp(offset, 0, 9),
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    if freshness:
        params["freshness"] = freshness
    if summary:
        params["result_filter"] = "summarizer"

    success, result = _make_request("/web/search", params)

    if not success:
        return str(result)

    return _format_web_results(result)  # type: ignore[arg-type]


def news(
    *,
    query: str,
    count: int = 10,
    offset: int = 0,
    country: str = "US",
    search_lang: str = "en",
    freshness: Literal["pd", "pw", "pm"] | None = None,
) -> str:
    """Search news articles using Brave Search API.

    Uses the dedicated /news/search endpoint for better news results.

    Args:
        query: Search query for news
        count: Number of results (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month)

    Returns:
        Formatted news results or error message

    Example:
        # Today's tech news
        brave.news(query="artificial intelligence", freshness="pd")

        # UK news
        brave.news(query="technology", country="GB", count=5)
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": _clamp(count, 1, 20),
        "offset": _clamp(offset, 0, 9),
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/news/search", params)

    if not success:
        return str(result)
    return _format_news_results(result)  # type: ignore[arg-type]


def local(
    *,
    query: str,
    count: int = 5,
    country: str = "US",
) -> str:
    """Search for local businesses and places using Brave Search API.

    Performs web search optimized for local queries. Returns location results
    if available, otherwise falls back to web results.

    Args:
        query: Local search query (e.g., "pizza near Central Park")
        count: Number of results (1-20, default: 5)
        country: 2-letter country code (default: "US")

    Returns:
        Formatted local results with addresses, ratings, phone numbers

    Example:
        brave.local(query="coffee shops near Times Square")
        brave.local(query="restaurants in San Francisco", count=10)
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": _clamp(count, 1, 20),
        "country": country,
    }

    success, result = _make_request("/web/search", params)

    if not success:
        return str(result)
    return _format_local_results_from_web(result)  # type: ignore[arg-type]


def image(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    safesearch: Literal["off", "strict"] = "strict",
) -> str:
    """Search for images using Brave Search API.

    Uses the dedicated /images/search endpoint.

    Args:
        query: Search query for images
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        safesearch: Content filter - "off" or "strict" (default: "strict")

    Returns:
        Formatted image results with URLs, sizes, and sources

    Example:
        brave.image(query="Python programming logo")
        brave.image(query="architecture diagrams", count=5)
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": _clamp(count, 1, 20),
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    success, result = _make_request("/images/search", params)

    if not success:
        return str(result)
    return _format_image_results(result)  # type: ignore[arg-type]


def video(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    freshness: Literal["pd", "pw", "pm", "py"] | None = None,
) -> str:
    """Search for videos using Brave Search API.

    Uses the dedicated /videos/search endpoint.

    Args:
        query: Search query for videos
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year)

    Returns:
        Formatted video results with titles, channels, durations, and URLs

    Example:
        brave.video(query="Python tutorial for beginners")
        brave.video(query="tech conference keynote", freshness="pm", count=5)
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": _clamp(count, 1, 20),
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/videos/search", params)

    if not success:
        return str(result)
    return _format_video_results(result)  # type: ignore[arg-type]


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    count: int = 2,
    country: str = "US",
    search_lang: str = "en",
) -> str:
    """Execute multiple web searches concurrently and return combined results.

    Queries are executed in parallel using threads for better performance.

    Args:
        queries: List of queries. Each item can be:
                 - A string (query text, used as both query and label)
                 - A tuple of (query, label) for custom labeling
        count: Number of results per query (1-20, default: 2)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")

    Returns:
        Combined formatted results with labels

    Example:
        # Simple list of queries
        brave.search_batch(["scipy", "sqlalchemy", "jupyterlab"])

        # With custom labels
        brave.search_batch([
            ("current Gold price USD/oz today", "Gold (USD/oz)"),
            ("current Silver price USD/oz today", "Silver (USD/oz)"),
            ("current Copper price USD/lb today", "Copper (USD/lb)"),
        ])
    """
    normalized = normalize_items(queries)

    with LogSpan(span="brave.batch", query_count=len(normalized), count=count) as s:

        def _search_one(query: str, label: str) -> tuple[str, str]:
            """Execute a single search and return (label, result)."""
            result = search(
                query=query,
                count=count,
                country=country,
                search_lang=search_lang,
            )
            return label, result

        results = batch_execute(_search_one, normalized, max_workers=len(normalized))
        output = format_batch_results(results, normalized)
        s.add(outputLen=len(output))
        return output


def summarize(
    *,
    query: str,
    country: str = "US",
    search_lang: str = "en",
) -> str:
    """Get an AI-generated summary for a search query.

    Performs a web search and returns an AI-powered summary of the results.
    Requires a Brave Search Pro plan.

    Args:
        query: Search query to summarize
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")

    Returns:
        AI-generated summary or error message

    Example:
        brave.summarize(query="What is quantum computing?")
        brave.summarize(query="Latest developments in AI", country="GB")
    """
    if error := _validate_query(query):
        return error

    params: dict[str, Any] = {
        "q": query,
        "country": country,
        "search_lang": search_lang,
        "result_filter": "summarizer",
    }

    success, result = _make_request("/web/search", params)

    if not success:
        return str(result)

    # Extract summary from response
    data: dict[str, Any] = result  # type: ignore[assignment]
    summarizer = data.get("summarizer", {})

    if not summarizer:
        return "No summary available for this query."

    summary_type = summarizer.get("type", "")
    results = summarizer.get("results", [])

    lines: list[str] = []
    if summary_type:
        lines.append(f"Summary type: {summary_type}")
        lines.append("")

    for item in results:
        text = item.get("text", "")
        if text:
            lines.append(text)

    return "\n".join(lines) if lines else "No summary content available."
