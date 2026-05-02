"""Grounding search tools.

Provides web search with Google's grounding capabilities via Gemini API.
Supports general search, developer resources, documentation, and Reddit searches.
Requires GEMINI_API_KEY in secrets.yaml.
"""

from __future__ import annotations

# Pack for dot notation: ground.search(), ground.dev(), etc.
pack = "ground"

__all__ = ["dev", "docs", "reddit", "search", "search_batch"]

import re
from typing import Any, Literal

# Type alias for output format
OutputFormat = Literal["full", "text_only", "sources_only"]

from otpack import (
    LogSpan,
    batch_execute_enveloped,
    get_tool_config,
    lazy_client,
    normalize_items,
    require_api_key,
)
from pydantic import BaseModel, Field

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


_SUPPORTED_EXTRACT_TYPES = frozenset({"string", "number", "boolean"})
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


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


def _extract_structured_data(
    *,
    text: str,
    sources: list[dict[str, str]],
    extract_schema: dict[str, Any],
    return_provenance: bool,
) -> dict[str, Any]:
    """Extract structured fields from grounded text using a constrained schema."""
    data: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    provenance: dict[str, dict[str, Any]] = {}
    source_url = sources[0]["url"] if sources else None

    for field in extract_schema.get("fields", []):
        name = str(field.get("name", "")).strip()
        field_type = str(field.get("type", "string"))
        required = bool(field.get("required", False))
        lowered_name = name.lower()
        value: Any = None
        snippet: str = ""

        if field_type == "boolean":
            for token in ("true", "false"):
                idx = text.lower().find(token)
                if idx >= 0:
                    value = token == "true"
                    snippet = text[max(0, idx - 20):idx + len(token) + 20].strip()
                    break
        elif field_type == "number":
            match = _NUMBER_RE.search(text)
            if match:
                snippet = match.group(0)
                value = float(snippet) if "." in snippet else int(snippet)
        else:
            if "email" in lowered_name:
                match = _EMAIL_RE.search(text)
                if match:
                    value = match.group(0)
                    snippet = value
            if value is None:
                key_match = re.search(
                    rf"{re.escape(name)}\s*[:=-]\s*(.+)",
                    text,
                    flags=re.IGNORECASE,
                )
                if key_match:
                    value = key_match.group(1).strip().splitlines()[0]
                    snippet = value

        data[name] = value
        if required and value in (None, ""):
            errors.append(
                {
                    "field": name,
                    "error_code": "required_field_missing",
                    "error_message": f"Required field '{name}' could not be extracted",
                }
            )

        if return_provenance:
            provenance[name] = {
                "source_url": source_url,
                "snippet": snippet,
                "confidence": None,
            }

    result: dict[str, Any] = {
        "mode": "structured_extraction",
        "data": data,
        "errors": errors,
    }
    if return_provenance:
        result["provenance"] = provenance
    return result

def _require_google_genai() -> None:
    """Raise ImportError if google-genai is not installed."""
    try:
        import google.genai  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "google-genai is required for grounding_search. "
            "Install with: pip install onetool-mcp[util]"
        ) from exc


def _build_client() -> Any:
    """Build a Gemini client with API key."""
    from google import genai

    api_key, err = require_api_key("GEMINI_API_KEY")
    if err:
        raise ValueError(err)
    return genai.Client(api_key=api_key)


_get_client = lazy_client(_build_client)


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
    extract_schema: dict[str, Any] | None = None,
    return_provenance: bool = False,
    **log_extras: Any,
) -> dict[str, Any] | str:
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
        Formatted search results with sources or structured extraction payload
    """
    _require_google_genai()
    from google.genai import types

    with LogSpan(span=span_name, **log_extras) as s:
        try:
            if model is None:
                model = get_tool_config("ground", Config).model
            client = _get_client()

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

            if extract_schema is not None:
                text = response.text or ""
                sources = _extract_sources(response)
                result = _extract_structured_data(
                    text=text,
                    sources=sources,
                    extract_schema=extract_schema,
                    return_provenance=return_provenance,
                )
                s.add("hasResults", bool(result.get("data")))
                s.add("resultLen", len(str(result)))
                return result

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
    extract_schema: dict[str, Any] | None = None,
    return_provenance: bool = False,
) -> dict[str, Any] | str:
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
        Search results with content/sources, structured extraction payload,
        or error message

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
        return "Error: query cannot be empty"
    if error := _validate_extract_schema(extract_schema):
        return error

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
        extract_schema=extract_schema,
        return_provenance=return_provenance,
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
    extract_schema: dict[str, Any] | None = None,
    return_provenance: bool = False,
    retries: int = 0,
    retry_delay_ms: int = 250,
) -> dict[str, Any] | str:
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
        Structured batch result envelope with `results[]` and `meta`, or error

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
        return "Error: queries list cannot be empty"
    if error := _validate_extract_schema(extract_schema):
        return error

    with LogSpan(span="ground.batch", queryCount=len(normalized), focus=focus) as s:

        def _search_one(query: str, _label: str) -> str:
            """Execute a single search and return raw result payload."""
            return search(
                query=query,
                context=context,
                focus=focus,
                model=model,
                timeout=timeout,
                max_sources=max_sources,
                output_format=output_format,
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
        Developer resources with content and source citations, or error message

    Example:
        # Basic developer search
        ground.dev(query="websocket connection handling")

        # Language-specific search
        ground.dev(query="parse JSON", language="Python")

        # Framework-specific search
        ground.dev(query="dependency injection", framework="FastAPI")
    """
    if not query or not query.strip():
        return "Error: query cannot be empty"

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
        Documentation content with source citations, or error message

    Example:
        # Basic documentation search
        ground.docs(query="async context managers")

        # Technology-specific docs
        ground.docs(query="hooks lifecycle", technology="React")
    """
    if not query or not query.strip():
        return "Error: query cannot be empty"

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
        Reddit discussion content with source citations, or error message

    Example:
        # General Reddit search
        ground.reddit(query="best Python web framework 2024")

        # Subreddit-specific search
        ground.reddit(query="FastAPI vs Flask", subreddit="python")
    """
    if not query or not query.strip():
        return "Error: query cannot be empty"

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
