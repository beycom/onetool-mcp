"""Grounding search tools.

Provides web search with Google's grounding capabilities via Gemini API.
Supports general search, developer resources, documentation, and Reddit searches.
Requires GEMINI_API_KEY in secrets.yaml.
"""

from __future__ import annotations

# Pack for dot notation: ground.search(), ground.dev(), etc.
pack = "ground"

__all__ = ["dev", "docs", "reddit", "search", "search_batch"]

from typing import Any, Literal

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot_sdk import batch_execute, format_batch_results, log, normalize_items

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


def _create_client() -> genai.Client:
    """Create a Gemini client with API key."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in secrets.yaml")
    return genai.Client(api_key=api_key)


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


def _format_response(response: Any) -> str:
    """Format Gemini response with content and sources.

    Args:
        response: Gemini API response object

    Returns:
        Formatted string with content and source citations
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

    if not text:
        return "No results found."

    # Extract and format sources
    sources = _extract_sources(response)

    if sources:
        text += "\n\n## Sources\n"
        seen_urls: set[str] = set()
        for i, source in enumerate(sources, 1):
            url = source["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = source["title"] or url
            text += f"{i}. [{title}]({url})\n"

    return text


def _grounded_search(
    prompt: str,
    *,
    span_name: str,
    model: str | None = None,
    **log_extras: Any,
) -> str:
    """Execute a grounded search query.

    Args:
        prompt: The search prompt to send to Gemini
        span_name: Name for the log span
        model: Gemini model to use (defaults to config)
        **log_extras: Additional fields to log

    Returns:
        Formatted search results with sources
    """
    with log(span_name, **log_extras) as s:
        try:
            if model is None:
                model = get_tool_config("ground", Config).model
            client = _create_client()

            # Configure grounding with Google Search
            google_search_tool = types.Tool(google_search=types.GoogleSearch())

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                ),
            )

            result = _format_response(response)
            s.add("hasResults", bool(result and result != "No results found."))
            s.add("resultLen", len(result))
            return result

        except Exception as e:
            s.add("error", str(e))
            return f"Error: {e}"


def search(
    *,
    query: str,
    context: str = "",
    focus: Literal["general", "code", "documentation", "troubleshooting"] = "general",
    model: str | None = None,
) -> str:
    """Search the web using Google Gemini with grounding.

    Performs a grounded web search using Google Search via Gemini.
    Results include content and source citations.

    Args:
        query: The search query
        context: Additional context to refine the search (e.g., "Python async")
        focus: Search focus mode:
            - "general": General purpose search (default)
            - "code": Focus on code examples and implementations
            - "documentation": Focus on official documentation
            - "troubleshooting": Focus on solving problems and debugging
        model: Gemini model to use (defaults to config, e.g., "gemini-2.5-flash")

    Returns:
        Search results with content and source citations

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
    """
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
        query=query,
        focus=focus,
    )


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    context: str = "",
    focus: Literal["general", "code", "documentation", "troubleshooting"] = "general",
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

    Returns:
        Combined formatted results with labels

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
    """
    normalized = normalize_items(queries)

    with log("ground.batch", query_count=len(normalized), focus=focus) as s:

        def _search_one(query: str, label: str) -> tuple[str, str]:
            """Execute a single search and return (label, result)."""
            result = search(
                query=query,
                context=context,
                focus=focus,
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
) -> str:
    """Search for developer resources and documentation.

    Searches for developer-focused content including GitHub repositories,
    Stack Overflow discussions, and technical documentation.

    Args:
        query: The technical search query
        language: Programming language to prioritize (e.g., "Python", "TypeScript")
        framework: Framework to prioritize (e.g., "FastAPI", "React")

    Returns:
        Developer resources with content and source citations

    Example:
        # Basic developer search
        ground.dev(query="websocket connection handling")

        # Language-specific search
        ground.dev(query="parse JSON", language="Python")

        # Framework-specific search
        ground.dev(query="dependency injection", framework="FastAPI")
    """
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
        query=query,
        language=language or None,
        framework=framework or None,
    )


def docs(
    *,
    query: str,
    technology: str = "",
) -> str:
    """Search for official documentation.

    Searches specifically for official documentation and API references.
    Prioritizes authoritative sources.

    Args:
        query: The documentation search query
        technology: Technology/library name to focus on (e.g., "React", "Django")

    Returns:
        Documentation content with source citations

    Example:
        # Basic documentation search
        ground.docs(query="async context managers")

        # Technology-specific docs
        ground.docs(query="hooks lifecycle", technology="React")
    """
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
        query=query,
        technology=technology or None,
    )


def reddit(
    *,
    query: str,
    subreddit: str = "",
) -> str:
    """Search Reddit discussions.

    Searches indexed Reddit posts and comments for community discussions,
    opinions, and real-world experiences.

    Args:
        query: The Reddit search query
        subreddit: Specific subreddit to search (e.g., "programming", "python")

    Returns:
        Reddit discussion content with source citations

    Example:
        # General Reddit search
        ground.reddit(query="best Python web framework 2024")

        # Subreddit-specific search
        ground.reddit(query="FastAPI vs Flask", subreddit="python")
    """
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
        query=query,
        subreddit=subreddit or None,
    )
