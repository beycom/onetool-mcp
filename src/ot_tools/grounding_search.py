"""Grounding search tools.

Provides web search with Google's grounding capabilities via Gemini API.
Supports general search, developer resources, documentation, and Reddit searches.
Requires GEMINI_API_KEY in secrets.yaml.
"""

from __future__ import annotations

# Namespace for dot notation: ground.search(), ground.dev(), etc.
namespace = "ground"

__all__ = ["dev", "docs", "reddit", "search"]

from typing import Any, Literal

from ot.config import get_config
from ot.config.secrets import get_secret
from ot.logging import LogSpan

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

    if not hasattr(response, "candidates") or not response.candidates:
        return sources

    candidate = response.candidates[0]
    if not hasattr(candidate, "grounding_metadata"):
        return sources

    metadata = candidate.grounding_metadata
    if not metadata:
        return sources

    # Extract from grounding_chunks
    if hasattr(metadata, "grounding_chunks") and metadata.grounding_chunks:
        for chunk in metadata.grounding_chunks:
            if hasattr(chunk, "web") and chunk.web:
                web = chunk.web
                title = getattr(web, "title", "") or ""
                uri = getattr(web, "uri", "") or ""
                if uri:
                    sources.append({"title": title, "url": uri})

    # Extract from grounding_supports as fallback
    if not sources and hasattr(metadata, "grounding_supports"):
        for support in metadata.grounding_supports or []:
            if hasattr(support, "grounding_chunk_indices"):
                for idx in support.grounding_chunk_indices or []:
                    if (
                        hasattr(metadata, "grounding_chunks")
                        and metadata.grounding_chunks
                        and idx < len(metadata.grounding_chunks)
                    ):
                        chunk = metadata.grounding_chunks[idx]
                        if hasattr(chunk, "web") and chunk.web:
                            web = chunk.web
                            title = getattr(web, "title", "") or ""
                            uri = getattr(web, "uri", "") or ""
                            if uri and {"title": title, "url": uri} not in sources:
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
    with LogSpan(span=span_name, **log_extras) as s:
        try:
            if model is None:
                model = get_config().tools.ground.model
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
        query=query,
        focus=focus,
    )


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
