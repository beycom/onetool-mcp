"""Grounding search tools.

Provides web search with Google's grounding capabilities via Gemini API.
Supports general search, developer resources, documentation, and Reddit searches.
Requires GEMINI_API_KEY in secrets.yaml.
"""

from __future__ import annotations

import functools

# Pack for dot notation: ground.search(), ground.dev(), etc.
pack = "ground"

__all__ = ["dev", "docs", "reddit", "search", "search_batch"]

from typing import Any, Literal

# Type alias for output format
OutputFormat = Literal["full", "text_only", "sources_only"]

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot.logging import LogSpan
from ot.utils import batch_execute, format_batch_results, normalize_items

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [{"name": "google-genai", "import_name": "google.genai", "install": "pip install google-genai"}],
    "secrets": ["GEMINI_API_KEY"],
}


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model for grounding search (e.g., gemini-2.5-flash)",
    )

try:
    from google import genai
    from google.genai import types
except ImportError as e:
    raise ImportError(
        "google-genai is required for grounding_search. "
        "Install with: pip install google-genai"
    ) from e


def _get_api_key() -> str:
    """Get Gemini API key from secrets."""
    return get_secret("GEMINI_API_KEY") or ""


@functools.lru_cache(maxsize=1)
def _get_cached_client(api_key: str) -> genai.Client:
    """Get or create a cached Gemini client.

    Args:
        api_key: The Gemini API key (used as cache key)

    Returns:
        Cached Gemini client instance
    """
    return genai.Client(api_key=api_key)


def _create_client() -> genai.Client:
    """Create a Gemini client with API key (cached)."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in secrets.yaml")
    return _get_cached_client(api_key)


def _extract_sources(response: Any) -> list[dict[str, str]]:
    """Extract grounding sources from Gemini response.

    Args:
        response: Gemini API response object

    Returns:
        List of source dicts with 'title' and 'url' keys
    """
    sources: list[dict[str, str]] = []

    # Navigate to grounding metadata
    if not hasattr(response, "candidates") or not response.candidates:
        return sources

    candidate = response.candidates[0]
    metadata = getattr(candidate, "grounding_metadata", None)
    if not metadata:
        return sources

    # Extract from grounding_chunks
    chunks = getattr(metadata, "grounding_chunks", None)
    if not chunks:
        return sources

    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if not web:
            continue
        uri = getattr(web, "uri", "") or ""
        if uri:
            title = getattr(web, "title", "") or ""
            sources.append({"title": title, "url": uri})

    return sources


def _format_response(
    response: Any,
    *,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
) -> str:
    """Format Gemini response with content and sources.

    Args:
        response: Gemini API response object
        output_format: Output format - "full" (default), "text_only", or "sources_only"
        max_sources: Maximum number of sources to include (None for unlimited)

    Returns:
        Formatted string with content and/or source citations
    """
    # Extract text content
    text = ""
    if hasattr(response, "text"):
        text = response.text or ""
    elif hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and candidate.content:
            content = candidate.content
            if hasattr(content, "parts") and content.parts:
                text = "".join(getattr(part, "text", "") for part in content.parts)

    # Extract sources
    sources = _extract_sources(response)

    # Handle output format
    if output_format == "sources_only":
        if not sources:
            return "No sources found."
        return _format_sources(sources, max_sources=max_sources)

    if not text:
        return "No results found."

    if output_format == "text_only":
        return text

    # Full format: text + sources
    if sources:
        text += "\n\n## Sources\n"
        text += _format_sources(sources, max_sources=max_sources)

    return text


def _format_sources(sources: list[dict[str, str]], *, max_sources: int | None = None) -> str:
    """Format source citations with deduplication and optional limit.

    Args:
        sources: List of source dicts with 'title' and 'url' keys
        max_sources: Maximum number of sources to include (None for unlimited)

    Returns:
        Formatted source list with numbered markdown links
    """
    result = ""
    seen_urls: set[str] = set()
    display_num = 0

    for source in sources:
        url = source["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        display_num += 1

        if max_sources is not None and display_num > max_sources:
            break

        title = source["title"] or url
        result += f"{display_num}. [{title}]({url})\n"

    return result


def _format_error(e: Exception) -> str:
    """Format error message with helpful context.

    Args:
        e: The exception that occurred

    Returns:
        User-friendly error message
    """
    error_str = str(e).lower()

    if "quota" in error_str or "rate" in error_str:
        return "Error: API quota exceeded. Try again later."
    elif "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
        return "Error: Invalid GEMINI_API_KEY. Check secrets.yaml."
    elif "timeout" in error_str:
        return "Error: Request timed out. Try a simpler query or increase timeout."
    else:
        return f"Search failed: {e}"


def _grounded_search(
    prompt: str,
    *,
    span_name: str,
    model: str | None = None,
    timeout: float = 30.0,
    output_format: OutputFormat = "full",
    max_sources: int | None = None,
    **log_extras: Any,
) -> str:
    """Execute a grounded search query.

    Args:
        prompt: The search prompt to send to Gemini
        span_name: Name for the log span
        model: Gemini model to use (defaults to config)
        timeout: Request timeout in seconds (default: 30.0)
        output_format: Output format - "full", "text_only", or "sources_only"
        max_sources: Maximum number of sources to include (None for unlimited)
        **log_extras: Additional fields to log

    Returns:
        Formatted search results with sources
    """
    with LogSpan(span=span_name, **log_extras) as s:
        try:
            if model is None:
                model = get_tool_config("ground", Config).model
            client = _create_client()

            # Configure grounding with Google Search
            google_search_tool = types.Tool(google_search=types.GoogleSearch())

            # Build config with timeout
            config = types.GenerateContentConfig(
                tools=[google_search_tool],
                http_options={"timeout": timeout * 1000},  # Convert to milliseconds
            )

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

            result = _format_response(
                response,
                output_format=output_format,
                max_sources=max_sources,
            )
            s.add("hasResults", bool(result and result not in ("No results found.", "No sources found.")))
            s.add("resultLen", len(result))
            return result

        except Exception as e:
            s.add("error", str(e))
            return _format_error(e)


def search(
    *,
    query: str,
    context: str = "",
    focus: Literal["general", "code", "documentation", "troubleshooting"] = "general",
    model: str | None = None,
    timeout: float = 30.0,
    max_sources: int | None = None,
    output_format: OutputFormat = "full",
) -> str:
    """Search the web using Google Gemini with grounding.

    Performs a grounded web search using Google Search via Gemini.
    Results include content and source citations.

    Args:
        query: The search query (cannot be empty)
        context: Additional context to refine the search (e.g., "Python async")
        focus: Search focus mode:
            - "general": General purpose search (default)
            - "code": Focus on code examples and implementations
            - "documentation": Focus on official documentation
            - "troubleshooting": Focus on solving problems and debugging
        model: Gemini model to use (defaults to config, e.g., "gemini-2.5-flash")
        timeout: Request timeout in seconds (default: 30.0)
        max_sources: Maximum number of sources to include (None for unlimited)
        output_format: Output format - "full" (default), "text_only", or "sources_only"

    Returns:
        Search results with content and source citations

    Raises:
        ValueError: If query is empty or whitespace-only

    Example:
        # Basic search
        ground.search(query="Python asyncio best practices")

        # With context
        ground.search(
            query="how to handle timeouts",
            context="Python async programming"
        )

        # Focus on code examples
        ground.search(query="fastapi middleware", focus="code")

        # Use a specific model
        ground.search(query="latest AI news", model="gemini-3.0-flash")

        # Get only sources
        ground.search(query="Python tutorials", output_format="sources_only")

        # Limit sources
        ground.search(query="machine learning", max_sources=5)
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    # Build the search prompt
    focus_instructions = {
        "general": "Provide a comprehensive answer with relevant information.",
        "code": "Focus on code examples, implementations, and technical details.",
        "documentation": "Focus on official documentation and API references.",
        "troubleshooting": "Focus on solutions, debugging tips, and common issues.",
    }

    prompt_parts = [query]

    if context:
        prompt_parts.append(f"\nContext: {context}")

    prompt_parts.append(f"\n{focus_instructions[focus]}")

    prompt = "".join(prompt_parts)

    return _grounded_search(
        prompt,
        span_name="ground.search",
        model=model,
        timeout=timeout,
        output_format=output_format,
        max_sources=max_sources,
        query=query,
        focus=focus,
    )


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    context: str = "",
    focus: Literal["general", "code", "documentation", "troubleshooting"] = "general",
    model: str | None = None,
    timeout: float = 30.0,
    max_sources: int | None = None,
    output_format: OutputFormat = "full",
) -> str:
    """Execute multiple grounded searches concurrently and return combined results.

    Queries are executed in parallel using threads for better performance.

    Args:
        queries: List of queries. Each item can be:
                 - A string (query text, used as both query and label)
                 - A tuple of (query, label) for custom labeling
        context: Additional context to refine all searches (e.g., "Python async")
        focus: Search focus mode for all queries:
            - "general": General purpose search (default)
            - "code": Focus on code examples and implementations
            - "documentation": Focus on official documentation
            - "troubleshooting": Focus on solving problems and debugging
        model: Gemini model to use (defaults to config)
        timeout: Request timeout in seconds (default: 30.0)
        max_sources: Maximum number of sources per query (None for unlimited)
        output_format: Output format - "full" (default), "text_only", or "sources_only"

    Returns:
        Combined formatted results with labels

    Raises:
        ValueError: If queries list is empty

    Example:
        # Simple list of queries
        ground.search_batch(queries=["fastapi", "django", "flask"])

        # With custom labels
        ground.search_batch(queries=[
            ("Python async best practices", "Async"),
            ("Python type hints guide", "Types"),
            ("Python testing frameworks", "Testing"),
        ])

        # With context and focus
        ground.search_batch(
            queries=["error handling", "logging", "debugging"],
            context="Python web development",
            focus="code"
        )

        # With model and timeout
        ground.search_batch(
            queries=["AI news", "ML trends"],
            model="gemini-3.0-flash",
            timeout=60.0
        )
    """
    normalized = normalize_items(queries)

    if not normalized:
        raise ValueError("queries list cannot be empty")

    with LogSpan(span="ground.batch", query_count=len(normalized), focus=focus) as s:

        def _search_one(query: str, label: str) -> tuple[str, str]:
            """Execute a single search and return (label, result)."""
            result = search(
                query=query,
                context=context,
                focus=focus,
                model=model,
                timeout=timeout,
                max_sources=max_sources,
                output_format=output_format,
            )
            return label, result

        results = batch_execute(_search_one, normalized, max_workers=len(normalized))
        output = format_batch_results(results, normalized)
        s.add(outputLen=len(output))
        return output


def dev(
    *,
    query: str,
    language: str = "",
    framework: str = "",
    timeout: float = 30.0,
    max_sources: int | None = None,
    output_format: OutputFormat = "full",
) -> str:
    """Search for developer resources and documentation.

    Searches for developer-focused content including GitHub repositories,
    Stack Overflow discussions, and technical documentation.

    Args:
        query: The technical search query (cannot be empty)
        language: Programming language to prioritize (e.g., "Python", "TypeScript")
        framework: Framework to prioritize (e.g., "FastAPI", "React")
        timeout: Request timeout in seconds (default: 30.0)
        max_sources: Maximum number of sources to include (None for unlimited)
        output_format: Output format - "full" (default), "text_only", or "sources_only"

    Returns:
        Developer resources with content and source citations

    Raises:
        ValueError: If query is empty or whitespace-only

    Example:
        # Basic developer search
        ground.dev(query="websocket connection handling")

        # Language-specific search
        ground.dev(query="parse JSON", language="Python")

        # Framework-specific search
        ground.dev(query="dependency injection", framework="FastAPI")
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    prompt_parts = [
        f"Developer search: {query}",
        "\nFocus on: GitHub repositories, Stack Overflow, technical documentation, "
        "and developer resources.",
    ]

    if language:
        prompt_parts.append(f"\nProgramming language: {language}")

    if framework:
        prompt_parts.append(f"\nFramework/Library: {framework}")

    prompt_parts.append("\nProvide code examples and technical details where relevant.")

    prompt = "".join(prompt_parts)

    return _grounded_search(
        prompt,
        span_name="ground.dev",
        timeout=timeout,
        output_format=output_format,
        max_sources=max_sources,
        query=query,
        language=language or None,
        framework=framework or None,
    )


def docs(
    *,
    query: str,
    technology: str = "",
    timeout: float = 30.0,
    max_sources: int | None = None,
    output_format: OutputFormat = "full",
) -> str:
    """Search for official documentation.

    Searches specifically for official documentation and API references.
    Prioritizes authoritative sources.

    Args:
        query: The documentation search query (cannot be empty)
        technology: Technology/library name to focus on (e.g., "React", "Django")
        timeout: Request timeout in seconds (default: 30.0)
        max_sources: Maximum number of sources to include (None for unlimited)
        output_format: Output format - "full" (default), "text_only", or "sources_only"

    Returns:
        Documentation content with source citations

    Raises:
        ValueError: If query is empty or whitespace-only

    Example:
        # Basic documentation search
        ground.docs(query="async context managers")

        # Technology-specific docs
        ground.docs(query="hooks lifecycle", technology="React")
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    prompt_parts = [f"Documentation search: {query}"]

    if technology:
        prompt_parts.append(f"\nTechnology: {technology}")
        prompt_parts.append(
            f"\nSearch specifically in {technology} official documentation "
            "and authoritative API references."
        )
    else:
        prompt_parts.append(
            "\nFocus on official documentation, API references, and authoritative "
            "technical guides."
        )

    prompt = "".join(prompt_parts)

    return _grounded_search(
        prompt,
        span_name="ground.docs",
        timeout=timeout,
        output_format=output_format,
        max_sources=max_sources,
        query=query,
        technology=technology or None,
    )


def reddit(
    *,
    query: str,
    subreddit: str = "",
    timeout: float = 30.0,
    max_sources: int | None = None,
    output_format: OutputFormat = "full",
) -> str:
    """Search Reddit discussions.

    Searches indexed Reddit posts and comments for community discussions,
    opinions, and real-world experiences.

    Tips:
        - Use shorter, more general queries for better results
        - Always specify a relevant subreddit for technical topics;
          the subreddit parameter acts as important context for the grounding model

    Args:
        query: The Reddit search query (cannot be empty)
        subreddit: Specific subreddit to search (e.g., "programming", "python")
        timeout: Request timeout in seconds (default: 30.0)
        max_sources: Maximum number of sources to include (None for unlimited)
        output_format: Output format - "full" (default), "text_only", or "sources_only"

    Returns:
        Reddit discussion content with source citations

    Raises:
        ValueError: If query is empty or whitespace-only

    Example:
        # General Reddit search
        ground.reddit(query="best Python web framework 2024")

        # Subreddit-specific search
        ground.reddit(query="FastAPI vs Flask", subreddit="python")
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    prompt_parts = [f"Reddit search: {query}"]

    if subreddit:
        prompt_parts.append(f"\nSearch in r/{subreddit} subreddit.")
    else:
        prompt_parts.append("\nSearch Reddit discussions, posts, and comments.")

    prompt_parts.append(
        "\nInclude community opinions, real-world experiences, and discussions. "
        "Cite specific Reddit threads when relevant."
    )

    prompt = "".join(prompt_parts)

    return _grounded_search(
        prompt,
        span_name="ground.reddit",
        timeout=timeout,
        output_format=output_format,
        max_sources=max_sources,
        query=query,
        subreddit=subreddit or None,
    )
