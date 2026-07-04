"""Tavily AI search API tools.

Provides AI-powered web search and URL content extraction via the Tavily API.
Optimized for LLM applications with clean, relevant results.

Requires TAVILY_API_KEY secret in secrets.yaml.

API docs: https://docs.tavily.com/docs/rest-api/api-reference

Credit costs (documented per function):
  search basic  = 1 credit, advanced = 2 credits
  extract basic = 1 credit per 5 URLs, advanced = 2 credits per 5 URLs
  research mini = 5 credits, pro = 20 credits, auto = varies
"""

from __future__ import annotations

# Pack for dot notation: tavily.search(), tavily.extract(), etc.
pack = "tavily"
pack_aliases = ("tav",)

__all__ = ["extract", "extract_batch", "research", "search", "search_batch"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "secrets": ["TAVILY_API_KEY"],
}

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

from pydantic import BaseModel, Field

from otpack import (
    BatchEnvelope,
    LogSpan,
    _format_http_error,
    batch_execute_enveloped,
    create_json_http_client,
    extract_structured_data,
    format_batch_results,
    format_sources,
    get_tool_config,
    lazy_client,
    normalize_items,
    require_api_key,
    validate_batch_retry_controls,
)

# Type alias matching ground.py convention
OutputFormat = Literal["full", "text_only", "sources_only"]


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=180.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )


TAVILY_API_BASE = "https://api.tavily.com"

_SEARCH_DEPTH_VALUES = frozenset(["basic", "advanced"])
_TOPIC_VALUES = frozenset(["general", "news", "finance"])
_TIME_RANGE_VALUES = frozenset(["day", "week", "month", "year"])
_OUTPUT_FORMAT_VALUES = frozenset(["full", "text_only", "sources_only"])
_EXTRACT_FORMAT_VALUES = frozenset(["markdown", "text"])
_EXTRACT_DEPTH_VALUES = frozenset(["basic", "advanced"])
_RESEARCH_MODEL_VALUES = frozenset(["mini", "pro", "auto"])
_SUPPORTED_EXTRACT_TYPES = frozenset(["string", "number", "boolean"])

# Pre-sorted for error messages
_SEARCH_DEPTH_LIST = sorted(_SEARCH_DEPTH_VALUES)
_TOPIC_LIST = sorted(_TOPIC_VALUES)
_TIME_RANGE_LIST = sorted(_TIME_RANGE_VALUES)
_OUTPUT_FORMAT_LIST = sorted(_OUTPUT_FORMAT_VALUES)
_EXTRACT_FORMAT_LIST = sorted(_EXTRACT_FORMAT_VALUES)
_EXTRACT_DEPTH_LIST = sorted(_EXTRACT_DEPTH_VALUES)
_RESEARCH_MODEL_LIST = sorted(_RESEARCH_MODEL_VALUES)


_get_http_client = lazy_client(
    lambda: create_json_http_client(
        TAVILY_API_BASE,
        timeout=_get_config().timeout,
        headers={"Content-Type": "application/json"},
    )
)


def _get_config() -> Config:
    """Get tavily pack configuration."""
    return get_tool_config("tavily", Config)


def _make_request(
    endpoint: str,
    payload: dict[str, Any],
    timeout: float | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Make HTTP POST request to Tavily API.

    Args:
        endpoint: API endpoint path (e.g., "/search")
        payload: JSON request body
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, result). If success, result is parsed JSON dict.
        If failure, result is error message string.
    """
    api_key, err = require_api_key("TAVILY_API_KEY")
    if err:
        return False, err

    if timeout is None:
        timeout = _get_config().timeout

    with LogSpan(
        span="tavily.request",
        endpoint=endpoint,
        query=payload.get("query", ""),
    ) as span:
        try:
            client = _get_http_client()
            if client is None:
                return False, "Error: HTTP client not initialized"
            response = client.post(
                endpoint,
                json={**payload, "api_key": api_key},
                timeout=timeout,
            )
            response.raise_for_status()

            result = response.json()
            span.add(status=response.status_code)
            return True, result

        except Exception as e:
            span.add(error=f"{type(e).__name__}: {e}")
            return False, _format_http_error(e)


def _make_get_request(
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Make HTTP GET request to Tavily API (used for polling).

    Args:
        path: API path (e.g., "/research/task_id")
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, result). If success, result is parsed JSON dict.
        If failure, result is error message string.
    """
    api_key, err = require_api_key("TAVILY_API_KEY")
    if err:
        return False, err

    try:
        client = _get_http_client()
        if client is None:
            return False, "Error: HTTP client not initialized"
        response = client.get(
            path,
            params={**(params or {}), "api_key": api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        return True, response.json()

    except Exception as e:
        return False, _format_http_error(e)



def _format_search_results(
    data: dict[str, Any],
    output_format: OutputFormat,
    min_score: float | None,
    max_sources: int | None = None,
) -> str:
    """Format search results according to output_format, filtering by min_score."""
    results: list[dict[str, Any]] = data.get("results", [])
    answer: str = data.get("answer", "") or ""

    # Apply min_score filter
    if min_score is not None:
        results = [r for r in results if r.get("score", 0.0) >= min_score]

    if output_format == "sources_only":
        if not results:
            return "No sources found."
        return format_sources(results, max_sources=max_sources)

    if output_format == "text_only":
        return answer or "No answer available."

    # full format: answer + numbered results + sources section + credit note
    lines: list[str] = []

    if answer:
        lines.append(answer)
        lines.append("")

    if not results:
        no_results = "No results found."
        return ("\n".join(lines) + no_results) if lines else no_results

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        content = result.get("content", "")

        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if content:
            lines.append(f"   {content}")
        lines.append("")

    # Sources section
    sources_text = format_sources(results, max_sources=max_sources)
    if sources_text:
        lines.append("## Sources")
        lines.append(sources_text)
        lines.append("")

    # Credit note from usage data
    usage = data.get("usage", {}) or {}
    credits = usage.get("credits")
    if credits is not None:
        lines.append(f"[Credits: {credits}]")

    return "\n".join(lines)


def _format_extract_results(data: dict[str, Any]) -> str:
    """Format URL extraction results for display."""
    lines: list[str] = []

    results = data.get("results", [])
    failed = data.get("failed_results", [])

    if not results and not failed:
        return "No content extracted."

    for i, result in enumerate(results, 1):
        url = result.get("url", "")
        raw_content = result.get("raw_content", "")

        lines.append(f"{i}. {url}")
        if raw_content:
            lines.append(raw_content)
        lines.append("")

    if failed:
        lines.append(f"Failed ({len(failed)}):")
        for item in failed:
            url = item.get("url", "")
            error = item.get("error", "unknown error")
            lines.append(f"  - {url}: {error}")

    return "\n".join(lines)


def _validate_extract_schema(extract_schema: dict[str, Any] | None) -> str | None:
    """Validate extraction schema shape and supported field types."""
    if extract_schema is None:
        return None
    fields = extract_schema.get("fields")
    if not isinstance(fields, list) or not fields:
        return "Error: extract_schema.fields must be a non-empty list"
    for field in fields:
        if not isinstance(field, dict):
            return "Error: each extract_schema field must be an object"
        name = field.get("name")
        field_type = field.get("type", "string")
        if not isinstance(name, str) or not name.strip():
            return "Error: each extract_schema field requires a non-empty string name"
        if field_type not in _SUPPORTED_EXTRACT_TYPES:
            return (
                f"Error: unsupported extract_schema field type '{field_type}'. "
                f"Use {sorted(_SUPPORTED_EXTRACT_TYPES)}"
            )
    return None



# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _validate_query(query: str) -> str | None:
    """Validate query is non-empty. Returns error string or None if valid."""
    if not query or not query.strip():
        return "Error: Query cannot be empty"
    return None


def _validate_max_results(max_results: int) -> str | None:
    """Validate max_results is in range 1-20. Returns error string or None if valid."""
    if 1 <= max_results <= 20:
        return None
    return f"Error: max_results must be between 1 and 20 (got {max_results})"


def _validate_search_depth(search_depth: str) -> str | None:
    """Validate search_depth value. Returns error string or None if valid."""
    if search_depth in _SEARCH_DEPTH_VALUES:
        return None
    return f"Error: Invalid search_depth '{search_depth}'. Use {_SEARCH_DEPTH_LIST}"


def _validate_topic(topic: str) -> str | None:
    """Validate topic value. Returns error string or None if valid."""
    if topic in _TOPIC_VALUES:
        return None
    return f"Error: Invalid topic '{topic}'. Use {_TOPIC_LIST}"


def _validate_time_range(time_range: str | None) -> str | None:
    """Validate time_range value. Returns error string or None if valid."""
    if time_range is None:
        return None
    if time_range in _TIME_RANGE_VALUES:
        return None
    return f"Error: Invalid time_range '{time_range}'. Use {_TIME_RANGE_LIST}"


def _validate_days(days: int) -> str | None:
    """Validate days is in range 1-30. Returns error string or None if valid."""
    if 1 <= days <= 30:
        return None
    return f"Error: days must be between 1 and 30 (got {days})"



def _validate_research_timeout(timeout_seconds: int) -> str | None:
    """Validate Tavily research total timeout guardrail."""
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        return (
            "Error: timeout_seconds must be between 10 and 1800 "
            f"(got {timeout_seconds})"
        )
    if 10 <= timeout_seconds <= 1_800:
        return None
    return (
        "Error: timeout_seconds must be between 10 and 1800 "
        f"(got {timeout_seconds})"
    )


def _validate_urls(urls: list[str]) -> str | None:
    """Validate URLs list is non-empty. Returns error string or None if valid."""
    if not urls:
        return "Error: urls list cannot be empty"
    return None


def _validate_output_format(output_format: str) -> str | None:
    """Validate output_format value. Returns error string or None if valid."""
    if output_format in _OUTPUT_FORMAT_VALUES:
        return None
    return f"Error: Invalid output_format '{output_format}'. Use {_OUTPUT_FORMAT_LIST}"


def _validate_extract_format(fmt: str) -> str | None:
    """Validate extract format value. Returns error string or None if valid."""
    if fmt in _EXTRACT_FORMAT_VALUES:
        return None
    return f"Error: Invalid format '{fmt}'. Use {_EXTRACT_FORMAT_LIST}"


def _validate_extract_depth(extract_depth: str) -> str | None:
    """Validate extract_depth value. Returns error string or None if valid."""
    if extract_depth in _EXTRACT_DEPTH_VALUES:
        return None
    return f"Error: Invalid extract_depth '{extract_depth}'. Use {_EXTRACT_DEPTH_LIST}"


def _validate_research_model(model: str) -> str | None:
    """Validate research model value. Returns error string or None if valid."""
    if model in _RESEARCH_MODEL_VALUES:
        return None
    return f"Error: Invalid model '{model}'. Use {_RESEARCH_MODEL_LIST}"


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def search(
    *,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    output_format: OutputFormat = "full",
    min_score: float | None = None,
    max_sources: int | None = None,
    time_range: str | None = None,
    days: int = 3,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    extract_schema: dict[str, Any] | None = None,
    return_provenance: bool = False,
) -> dict[str, Any] | str:
    """Search the web using Tavily AI-powered search API.

    Returns an AI-synthesised answer alongside numbered results and sources.

    Credit costs: search_depth="basic" = 1 credit, "advanced" = 2 credits.

    Args:
        query: Search query
        max_results: Number of results to return (1-20, default: 5)
        search_depth: Search depth - "basic" (1 credit, faster) or "advanced"
            (2 credits, more thorough, default: "basic")
        topic: Search topic - "general", "news", or "finance" (default: "general")
        output_format: Controls response structure:
            - "full" (default): AI answer + numbered results + sources + credit note
            - "text_only": AI answer only
            - "sources_only": Numbered source URL list only
        min_score: Minimum Tavily relevance score to include (0.0-1.0, default: None)
        max_sources: Maximum number of sources in the ## Sources section or
            sources_only list (default: None, all sources)
        time_range: Filter results by time - "day", "week", "month", "year"
            (default: None)
        days: For news topic, number of days back to search (1-30, default: 3)
        include_domains: Restrict results to these domains (e.g., ["bbc.com"])
        exclude_domains: Exclude results from these domains

    Returns:
        Formatted search results or error message

    Example:
        # Basic search with AI answer
        tavily.search(query="Python async best practices")

        # News with sources only
        tavily.search(query="AI announcements", topic="news", output_format="sources_only")

        # Finance with domain filter and score threshold
        tavily.search(query="Apple earnings", topic="finance",
                      include_domains=["reuters.com"], min_score=0.5)
    """
    if error := _validate_query(query):
        return error
    if error := _validate_max_results(max_results):
        return error
    if error := _validate_search_depth(search_depth):
        return error
    if error := _validate_topic(topic):
        return error
    if error := _validate_output_format(output_format):
        return error
    if error := _validate_time_range(time_range):
        return error
    if error := _validate_days(days):
        return error
    if error := _validate_extract_schema(extract_schema):
        return error

    payload: dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "topic": topic,
        "include_answer": True,
        "days": days,
    }

    if time_range:
        payload["time_range"] = time_range
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    with LogSpan(span="tavily.search", query=query, depth=search_depth) as s:
        success, result = _make_request("/search", payload)

        if not success:
            return str(result)
        assert isinstance(result, dict)

        output = _format_search_results(result, output_format, min_score, max_sources=max_sources)

        if extract_schema is not None:
            sources = result.get("results", []) or []
            extract_text_parts: list[str] = []
            answer = result.get("answer", "")
            if isinstance(answer, str) and answer:
                extract_text_parts.append(answer)
            for entry in sources:
                content = entry.get("content", "")
                if isinstance(content, str) and content:
                    extract_text_parts.append(content)
            return extract_structured_data(
            confidence_key="score",
                text="\n".join(extract_text_parts),
                sources=sources,
                extract_schema=extract_schema,
                return_provenance=return_provenance,
            )

        filtered = result.get("results", [])
        if min_score is not None:
            filtered = [r for r in filtered if r.get("score", 0.0) >= min_score]
        s.add(resultCount=len(filtered))

        credits = (result.get("usage") or {}).get("credits")
        if credits is not None:
            s.add(credits=credits)

        return output


def extract(
    *,
    urls: list[str],
    format: str = "markdown",
    extract_depth: str = "basic",
) -> str:
    """Extract content from one or more URLs using Tavily.

    Retrieves the raw textual content of each URL, useful for reading articles,
    documentation, or any web page.

    Credit costs: extract_depth="basic" = 1 credit per 5 URLs,
                  "advanced" = 2 credits per 5 URLs.

    Args:
        urls: List of URLs to extract content from
        format: Output format - "markdown" (default) or "text"
        extract_depth: Extraction depth - "basic" (default) or "advanced"

    Returns:
        Extracted content for each URL, with any failures noted, or error message

    Example:
        tavily.extract(urls=["https://docs.python.org/3/library/asyncio.html"])

        tavily.extract(urls=[
            "https://example.com/article-1",
            "https://example.com/article-2",
        ], format="text", extract_depth="advanced")
    """
    if error := _validate_urls(urls):
        return error
    if error := _validate_extract_format(format):
        return error
    if error := _validate_extract_depth(extract_depth):
        return error

    with LogSpan(span="tavily.extract", urlCount=len(urls)) as span:
        payload: dict[str, Any] = {
            "urls": urls,
            "extract_depth": extract_depth,
        }

        success, result = _make_request("/extract", payload)

        if not success:
            return str(result)
        assert isinstance(result, dict)

        output = _format_extract_results(result)
        span.add(outputLen=len(output))
        return output


def extract_batch(
    *,
    url_sets: list[tuple[list[str], str] | list[str]],
    format: str = "markdown",
    extract_depth: str = "basic",
) -> str:
    """Extract content from multiple URL sets concurrently.

    URL sets are processed in parallel using threads for better performance.

    Credit costs: extract_depth="basic" = 1 credit per 5 URLs per set,
                  "advanced" = 2 credits per 5 URLs per set.

    Args:
        url_sets: List of URL sets. Each item can be:
                  - A list of URLs (labeled by first URL)
                  - A tuple of (list_of_urls, label) for custom labeling
        format: Output format - "markdown" (default) or "text"
        extract_depth: Extraction depth - "basic" (default) or "advanced"

    Returns:
        Combined formatted results with labels, or error message

    Example:
        # Simple sets
        tavily.extract_batch(url_sets=[
            ["https://docs.a.com/page1", "https://docs.a.com/page2"],
            ["https://docs.b.com/page1"],
        ])

        # With custom labels
        tavily.extract_batch(url_sets=[
            (["https://docs.react.dev/learn"], "React Docs"),
            (["https://fastapi.tiangolo.com/"], "FastAPI Docs"),
        ])
    """
    if not url_sets:
        return "Error: No URL sets provided"

    if error := _validate_extract_format(format):
        return error
    if error := _validate_extract_depth(extract_depth):
        return error

    # Normalize: convert list[str] → (list[str], label)
    normalized: list[tuple[list[str], str]] = []
    for i, item in enumerate(url_sets):
        if isinstance(item, tuple):
            urls_list, label = item
            normalized.append((urls_list, label or (urls_list[0] if urls_list else f"Set {i + 1}")))
        else:
            label = item[0] if item else f"Set {i + 1}"
            normalized.append((item, label))

    # Validate all URL sets before executing
    for urls_list, _ in normalized:
        if error := _validate_urls(urls_list):
            return error

    with LogSpan(span="tavily.batch", urlSetCount=len(normalized)) as s:

        def _extract_one(urls_list: list[str], label: str) -> tuple[str, str]:
            result = extract(urls=urls_list, format=format, extract_depth=extract_depth)
            return label, result

        results: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=min(len(normalized), 10)) as executor:
            futures = {
                executor.submit(_extract_one, urls_list, label): label
                for urls_list, label in normalized
            }
            for future in as_completed(futures):
                label, result = future.result()
                results[label] = result

        # Preserve order using format_batch_results convention
        output = format_batch_results(
            results,
            [(label, label) for _, label in normalized],
        )
        s.add(outputLen=len(output))
        return output


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    max_results: int = 2,
    search_depth: str = "basic",
    topic: str = "general",
    output_format: OutputFormat = "full",
    min_score: float | None = None,
    max_sources: int | None = None,
    time_range: str | None = None,
    extract_schema: dict[str, Any] | None = None,
    return_provenance: bool = False,
    retries: int = 0,
    retry_delay_ms: int = 250,
) -> BatchEnvelope | str:
    """Execute multiple Tavily searches concurrently and return combined results.

    Queries are executed in parallel using threads for better performance.

    Credit costs: search_depth="basic" = 1 credit per query,
                  "advanced" = 2 credits per query.

    Args:
        queries: List of queries. Each item can be:
                 - A string (query text, used as both query and label)
                 - A tuple of (query, label) for custom labeling
        max_results: Number of results per query (1-20, default: 2)
        search_depth: Search depth - "basic" or "advanced" (default: "basic")
        topic: Search topic - "general", "news", or "finance" (default: "general")
        output_format: Output format - "full" (default), "text_only", or "sources_only"
        min_score: Minimum relevance score to include (0.0-1.0, default: None)
        max_sources: Maximum number of sources per query (default: None, all sources)
        time_range: Filter results by time - "day", "week", "month", "year"

    Returns:
        Structured batch result envelope with `results[]` and `meta`, or error

    Example:
        # Simple list of queries
        tavily.search_batch(queries=["scipy", "sqlalchemy", "jupyterlab"])

        # With custom labels
        tavily.search_batch(queries=[
            ("Python 3.13 new features", "Python 3.13"),
            ("FastAPI vs Django performance 2025", "FastAPI vs Django"),
        ])

        # Sources only, multiple topics
        tavily.search_batch(
            queries=["AI news today", "ML research 2025"],
            output_format="sources_only",
            topic="news",
        )
    """
    if error := _validate_max_results(max_results):
        return error
    if error := _validate_search_depth(search_depth):
        return error
    if error := _validate_topic(topic):
        return error
    if error := _validate_output_format(output_format):
        return error
    if error := _validate_time_range(time_range):
        return error
    if error := _validate_extract_schema(extract_schema):
        return error
    if error := validate_batch_retry_controls(retries, retry_delay_ms):
        return error

    normalized = normalize_items(queries)

    if not normalized:
        return "Error: No queries provided"

    # Fall back empty labels to query text
    normalized = [(q, label or q) for q, label in normalized]

    with LogSpan(
        span="tavily.batch", query_count=len(normalized), max_results=max_results
    ) as s:

        def _search_one(query: str, _label: str) -> dict[str, Any] | str:
            return search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                topic=topic,
                output_format=output_format,
                min_score=min_score,
                max_sources=max_sources,
                time_range=time_range,
                extract_schema=extract_schema,
                return_provenance=return_provenance,
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


def research(
    *,
    input: str,
    model: str = "auto",
    timeout_seconds: int = 300,
) -> str:
    """Perform comprehensive multi-source research using Tavily Research API.

    Submits a research task and polls until complete or timeout. The research
    engine synthesises multiple sources into a detailed report.

    Credit costs: model="mini" = 5 credits, "pro" = 20 credits,
                  "auto" = varies based on complexity.

    Uses synchronous polling with exponential backoff (2s → 10s between polls).

    Args:
        input: Research question or task description (cannot be empty)
        model: Research model - "mini" (fast, fewer sources), "pro" (deeper,
            more sources), "auto" (default, selects automatically)
        timeout_seconds: Maximum seconds to wait before returning a timeout error
            (default: 300)

    Returns:
        Research report synthesised from multiple sources, or error message

    Example:
        # Basic research
        tavily.research(input="How does FastAPI compare to Flask for production APIs?")

        # Deep research with pro model
        tavily.research(input="State of LLM context window scaling 2025", model="pro")

        # Quick research with short timeout
        tavily.research(input="Python GIL removal status", model="mini", timeout_seconds=60)
    """
    if not input or not input.strip():
        return "Error: input cannot be empty"
    if error := _validate_research_model(model):
        return error
    if error := _validate_research_timeout(timeout_seconds):
        return error

    _, err = require_api_key("TAVILY_API_KEY")
    if err:
        return str(err)

    with LogSpan(span="tavily.research", model=model) as s:
        start_time = time.monotonic()

        # Submit research task
        success, result = _make_request(
            "/research",
            {"query": input, "model": model},
            timeout=float(timeout_seconds),
        )

        if not success:
            return str(result)
        assert isinstance(result, dict)

        status = result.get("status", "")

        # Completed immediately (synchronous response)
        if status == "completed" or "content" in result or "report" in result:
            output = result.get("content") or result.get("report") or str(result)
            elapsed = time.monotonic() - start_time
            s.add(elapsed=round(elapsed, 1), status="completed")
            return str(output)

        # Async: poll until completed or timeout
        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            return "Error: research task started but no task ID returned"

        wait_time = 2.0
        max_wait = 10.0

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout_seconds:
                s.add(elapsed=round(elapsed, 1), status="timeout")
                return f"Error: research timed out after {timeout_seconds} seconds"

            remaining = timeout_seconds - elapsed
            sleep_for = min(wait_time, remaining)
            if sleep_for > 0:
                time.sleep(sleep_for)
            wait_time = min(wait_time * 1.5, max_wait)

            remaining = timeout_seconds - (time.monotonic() - start_time)
            if remaining <= 0:
                s.add(elapsed=timeout_seconds, status="timeout")
                return f"Error: research timed out after {timeout_seconds} seconds"

            poll_timeout = max(0.1, min(_get_config().timeout, remaining))
            poll_success, poll_result = _make_get_request(
                f"/research/{task_id}",
                timeout=poll_timeout,
            )

            if not poll_success:
                continue
            assert isinstance(poll_result, dict)

            poll_status = poll_result.get("status", "")

            if poll_status == "completed":
                output = poll_result.get("content") or poll_result.get("report") or ""
                elapsed = time.monotonic() - start_time
                s.add(elapsed=round(elapsed, 1), status="completed")
                return str(output)

            if poll_status == "failed":
                error_msg = poll_result.get("error", "unknown error")
                elapsed = time.monotonic() - start_time
                s.add(elapsed=round(elapsed, 1), status="failed")
                return f"Error: research failed: {error_msg}"
