# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "pyyaml>=6.0.0"]
# ///
"""Context7 API tools for library search and documentation.

These built-in tools provide access to the Context7 documentation API
for fetching up-to-date library documentation and code examples.

Based on context7 by Upstash (MIT License).
https://github.com/upstash/context7
"""

from __future__ import annotations

# Namespace for dot notation: context7.search(), context7.doc()
namespace = "context7"

__all__ = ["doc", "search"]

import re

from ot_sdk import cache, get_config, get_secret, http, log, worker_main

# Context7 REST API configuration
CONTEXT7_SEARCH_URL = "https://context7.com/api/v2/search"
CONTEXT7_DOCS_CODE_URL = "https://context7.com/api/v2/docs/code"
CONTEXT7_DOCS_INFO_URL = "https://context7.com/api/v2/docs/info"

# Shared HTTP client for connection pooling
_client = http.client(timeout=30.0)


def _get_api_key() -> str:
    """Get Context7 API key from secrets."""
    return get_secret("CONTEXT7_API_KEY") or ""


def _get_headers() -> dict[str, str]:
    """Get authorization headers for Context7 API."""
    api_key = _get_api_key()
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _make_request(
    url: str,
    params: dict[str, str | int] | None = None,
    timeout: float | None = None,
) -> tuple[bool, str | dict]:
    """Make HTTP GET request to Context7 API.

    Args:
        url: Full URL to request
        params: Query parameters
        timeout: Request timeout in seconds (defaults to config)

    Returns:
        Tuple of (success, result). If success, result is parsed JSON or text.
        If failure, result is error message string.
    """
    api_key = _get_api_key()
    if not api_key:
        return False, "[Context7 API key not configured]"

    if timeout is None:
        timeout = get_config("tools.context7.timeout") or 30.0

    with log("context7.request", url=url) as span:
        try:
            response = _client.get(
                url,
                params=params,
                headers=_get_headers(),
                timeout=timeout,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            span.add(status=response.status_code)
            if "application/json" in content_type:
                return True, response.json()
            return True, response.text

        except Exception as e:
            error_type = type(e).__name__
            span.add(error=f"{error_type}: {e}")
            if hasattr(e, "response"):
                status = getattr(e.response, "status_code", "unknown")
                return False, f"HTTP error ({status}): {error_type}"
            return False, f"Request failed: {e}"


@cache(ttl=3600)  # Cache library key resolutions for 1 hour
def _normalize_library_key(library_key: str) -> str:
    """Normalize library key to Context7 API format.

    Handles various input formats and common issues:
    - "/vercel/next.js/v16.0.3" -> "vercel/next.js"
    - "/vercel/next.js" -> "vercel/next.js"
    - "vercel/next.js" -> "vercel/next.js"
    - "next.js" -> "next.js" (search will be needed)
    - "https://github.com/vercel/next.js" -> "vercel/next.js"
    - Stray quotes: '"vercel/next.js"' -> "vercel/next.js"
    - Double slashes: "vercel//next.js" -> "vercel/next.js"
    - Trailing slashes: "vercel/next.js/" -> "vercel/next.js"

    Args:
        library_key: Raw library key from user input

    Returns:
        Normalized org/repo format for Context7 API
    """
    key = library_key.strip()

    # Remove stray quotes (single or double)
    key = key.strip("\"'")

    # Handle GitHub URLs
    github_match = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/?.*", key)
    if github_match:
        return f"{github_match.group(1)}/{github_match.group(2)}"

    # Handle Context7 URLs
    context7_match = re.match(
        r"https?://(?:www\.)?context7\.com/([^/]+)/([^/]+)/?.*", key
    )
    if context7_match:
        return f"{context7_match.group(1)}/{context7_match.group(2)}"

    # Fix double slashes
    while "//" in key:
        key = key.replace("//", "/")

    # Strip leading and trailing slashes
    key = key.strip("/")

    # Extract org/repo (ignore version suffix like /v16.0.3)
    parts = key.split("/")
    if len(parts) >= 2:
        # Check if third part looks like a version
        if len(parts) > 2 and re.match(r"v?\d+", parts[2]):
            return f"{parts[0]}/{parts[1]}"
        # Otherwise just take first two parts
        return f"{parts[0]}/{parts[1]}"

    return key


def _normalize_topic(topic: str) -> str:
    """Normalize topic string for search.

    Handles:
    - Stray quotes: '"PPR"' -> "PPR"
    - Placeholder syntax: "<relevant topic>" -> ""
    - Path-like topics: "app/partial-pre-rendering/index" -> "partial pre-rendering"
    - Extra whitespace
    - Escaped quotes: '\\"topic\\"' -> "topic"

    Args:
        topic: Raw topic from user input

    Returns:
        Cleaned topic string
    """
    topic = topic.strip()

    # Remove stray quotes (single or double)
    topic = topic.strip("\"'")

    # Remove escaped quotes
    topic = topic.replace('\\"', "").replace("\\'", "")

    # Remove placeholder markers
    if topic.startswith("<") and topic.endswith(">"):
        topic = topic[1:-1].strip()

    # If it's a placeholder like "relevant topic", return empty to get general docs
    if topic.lower() in ("relevant topic", "topic", "extract from question", ""):
        return ""

    # Convert path-like topics to search terms
    # "app/partial-pre-rendering/index" -> "partial pre-rendering"
    if "/" in topic and not topic.startswith("http"):
        # Take the most specific part (usually the last meaningful segment)
        parts = [p for p in topic.split("/") if p and p != "index"]
        if parts:
            topic = parts[-1]

    # Convert kebab-case to spaces
    topic = topic.replace("-", " ").replace("_", " ")

    # Clean up whitespace
    topic = " ".join(topic.split())

    return topic


def search(*, query: str) -> str:
    """Search for libraries by name in Context7.

    Args:
        query: The search query (e.g., 'next.js', 'react', 'vue')

    Returns:
        Search results with matching libraries and their IDs

    Example:
        context7.search(query="fastapi")
        context7.search(query="react hooks")
    """
    with log("context7.search", query=query) as s:
        success, result = _make_request(CONTEXT7_SEARCH_URL, params={"query": query})

        s.add(success=success)
        if not success:
            return f"{result} query={query}"

        result_str = str(result)
        s.add(resultLen=len(result_str))
        return result_str


def _resolve_library_key(library_key: str) -> str:
    """Resolve a library key, searching if needed.

    If the key doesn't look like a valid org/repo format,
    search Context7 to find the best match.

    Args:
        library_key: Raw or partial library key

    Returns:
        Resolved org/repo library key
    """
    normalized = _normalize_library_key(library_key)

    # If it looks like a valid org/repo, use it directly
    if "/" in normalized and len(normalized.split("/")) == 2:
        org, repo = normalized.split("/")
        if org and repo and not org.startswith("http"):
            return normalized

    # Otherwise, search for the library
    success, data = _make_request(CONTEXT7_SEARCH_URL, params={"query": normalized})

    if not success:
        return normalized

    # Context7 returns a list of results, pick the first/best match
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            for key_name in ("id", "key", "library_key", "path"):
                if key_name in first:
                    resolved = str(first[key_name]).lstrip("/")
                    if "/" in resolved:
                        return resolved
    elif isinstance(data, dict):
        for key_name in ("id", "key", "library_key", "path"):
            if key_name in data:
                resolved = str(data[key_name]).lstrip("/")
                if "/" in resolved:
                    return resolved

    return normalized


def doc(
    *,
    library_key: str,
    topic: str = "",
    mode: str = "info",
    page: int = 1,
    limit: int | None = None,
    doc_type: str = "txt",
) -> str:
    """Fetch documentation for a library from Context7.

    Args:
        library_key: The library key - can be flexible format:
            - Full: 'vercel/next.js'
            - With version: '/vercel/next.js/v16.0.3'
            - Shorthand: 'next.js', 'nextjs', 'react'
            - URL: 'https://github.com/vercel/next.js'
        topic: Topic to focus documentation on (e.g., 'routing', 'hooks', 'ssr').
               Default: empty string for general docs
        mode: Documentation mode - 'info' for conceptual guides and narrative documentation (default),
              'code' for API references and code examples
        page: Page number for pagination (default: 1, max: 10)
        limit: Number of results per page (defaults to config, max: config docs_limit)
        doc_type: Response format 'txt' or 'json' (default: 'txt')

    Returns:
        Documentation content and code examples for the requested topic

    Example:
        # Get general docs
        context7.doc(library_key="fastapi/fastapi")

        # Get docs on a specific topic
        context7.doc(library_key="vercel/next.js", topic="routing")

        # Get code examples
        context7.doc(library_key="pallets/flask", topic="blueprints", mode="code")
    """
    with log("context7.doc", library_key=library_key, topic=topic, mode=mode) as s:
        # Normalize and resolve library key (searches if needed)
        resolved_key = _resolve_library_key(library_key)
        s.add(resolvedKey=resolved_key)

        # Validate resolved key has org/repo format
        if "/" not in resolved_key:
            return (
                f"Could not resolve library '{library_key}' to org/repo format. "
                f"Please use full format like 'facebook/react' or 'vercel/next.js'. "
                f"Use context7.search(query=\"{library_key}\") to find the correct library key."
            )

        # Normalize topic
        normalized_topic = _normalize_topic(topic)

        # Clamp page and limit to valid ranges
        config_docs_limit = get_config("tools.context7.docs_limit") or 10
        page = max(1, min(page, 10))
        if limit is None:
            limit = config_docs_limit
        limit = max(1, min(limit, config_docs_limit))

        # Select endpoint based on mode
        base_url = CONTEXT7_DOCS_INFO_URL if mode == "info" else CONTEXT7_DOCS_CODE_URL
        url = f"{base_url}/{resolved_key}"
        params: dict[str, str | int] = {
            "type": doc_type,
            "page": page,
            "limit": limit,
        }
        # Only include topic if non-empty
        if normalized_topic:
            params["topic"] = normalized_topic

        success, data = _make_request(url, params=params)
        s.add(success=success)

        if not success:
            return f"{data} library_key={library_key}"

        # Handle response
        if isinstance(data, str):
            # Check for "no content" responses
            if data in ("No content available", "No context data available", ""):
                other_mode = "info" if mode == "code" else "code"
                return f"No {mode} documentation available for this library. Try mode='{other_mode}'."
            s.add(resultLen=len(data))
            return data

        if isinstance(data, dict):
            result = str(data.get("content", data.get("text", str(data))))
            s.add(resultLen=len(result))
            return result

        result = str(data)
        s.add(resultLen=len(result))
        return result


if __name__ == "__main__":
    worker_main()
