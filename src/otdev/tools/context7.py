"""Context7 API tools for library search and documentation.

These built-in tools provide access to the Context7 documentation API
for fetching up-to-date library documentation and code examples.

Based on context7 by Upstash (MIT License).
https://github.com/upstash/context7
"""

from __future__ import annotations

# Pack for dot notation: context7.search(), context7.doc()
pack = "context7"
pack_aliases = ("c7",)

__all__ = ["doc", "search"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "secrets": ["CONTEXT7_API_KEY"],
}

import re
from typing import Any

import httpx
from otpack import (
    LogSpan,
    _format_http_error,
    cache,
    get_tool_config,
    lazy_client,
    require_api_key,
)
from pydantic import BaseModel, Field


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )


# Context7 REST API configuration
CONTEXT7_SEARCH_URL = "https://context7.com/api/v2/libs/search"
CONTEXT7_CONTEXT_URL = "https://context7.com/api/v2/context"


def _get_config() -> Config:
    """Get context7 pack configuration."""
    return get_tool_config("context7", Config)


def _create_http_client() -> httpx.Client:
    """Create HTTP client for Context7 API requests.

    Called exactly once by lazy_client (double-checked locking). The timeout
    set here is a client-level default, but every request also passes an
    explicit per-request timeout via _make_request(), so the effective timeout
    is always read fresh from config on each call.
    """
    return httpx.Client(timeout=_get_config().timeout, follow_redirects=True)


# Thread-safe lazy singleton — factory is called once on first request.
_get_http_client = lazy_client(_create_http_client)


def _make_request(
    url: str,
    params: dict[str, str | int] | None = None,
    timeout: float | None = None,
) -> tuple[bool, str | dict[str, Any]]:
    """Make HTTP GET request to Context7 API.

    Args:
        url: Full URL to request
        params: Query parameters
        timeout: Request timeout in seconds (defaults to config)

    Returns:
        Tuple of (success, result). If success, result is parsed JSON or text.
        If failure, result is error message string.
    """
    api_key, err = require_api_key("CONTEXT7_API_KEY")
    if err:
        return False, err

    if timeout is None:
        # Read config per-call so the timeout reflects the current config value,
        # not the one baked into the cached client at startup.
        timeout = _get_config().timeout

    headers = {"Authorization": f"Bearer {api_key}"}

    with LogSpan(span="context7.request", url=url) as span:
        try:
            client = _get_http_client()
            if client is None:
                return False, "Error: HTTP client not initialized"
            response = client.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            span.add(status=response.status_code)
            if "application/json" in content_type:
                return True, response.json()
            return True, response.text

        except Exception as e:
            span.add(error=f"{type(e).__name__}: {e}")
            return False, _format_http_error(e)


def _normalize_library_id(library_id: str) -> str:
    """Normalize library ID to Context7 format with leading slash.

    Handles various input formats:
    - "/vercel/next.js" -> "/vercel/next.js"
    - "vercel/next.js" -> "/vercel/next.js"
    - "/vercel/next.js/v14.3.0-canary.87" -> "/vercel/next.js/v14.3.0-canary.87"
    - "next.js" -> "/next.js" (search will be needed)
    - "https://github.com/vercel/next.js" -> "/vercel/next.js"
    - Stray quotes: '"vercel/next.js"' -> "/vercel/next.js"
    - Double slashes: "vercel//next.js" -> "/vercel/next.js"

    Args:
        library_id: Raw library ID from user input

    Returns:
        Normalized Context7 library ID with leading slash
    """
    key = library_id.strip()

    # Remove stray quotes (single or double)
    key = key.strip("\"'")

    # Handle GitHub URLs
    github_match = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/?#]+).*", key)
    if github_match:
        return f"/{github_match.group(1)}/{github_match.group(2)}"

    # Handle Context7 URLs: extract the path portion
    context7_match = re.match(r"https?://(?:www\.)?context7\.com(/[^?#]+)", key)
    if context7_match:
        return context7_match.group(1).rstrip("/")

    # Fix double slashes
    key = re.sub(r"//{1,}", "/", key)

    # Remove trailing slash
    key = key.rstrip("/")

    # Ensure leading slash
    if not key.startswith("/"):
        key = f"/{key}"

    return key


def _has_title_overlap(query: str, title: str) -> bool:
    """Return True if query and title share meaningful name overlap.

    Strips punctuation and checks if either string contains the other,
    or if a 4+ character segment of the shorter string appears in the longer.
    This prevents clearly irrelevant search results from being accepted.

    Examples:
        _has_title_overlap("nextjs", "Next.js") -> True  (strips to "nextjs"/"nextjs")
        _has_title_overlap("react", "React")    -> True
        _has_title_overlap("nonexistent-xyz", "paperless-ai") -> False
    """

    def clean(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    q = clean(query)
    t = clean(title)

    if not q or not t:
        return False

    if q in t or t in q:
        return True

    # Check if any 4+ char segment of the shorter appears in the longer
    shorter, longer = (q, t) if len(q) <= len(t) else (t, q)
    seg_len = max(4, len(shorter) // 2)
    return any(
        shorter[i : i + seg_len] in longer for i in range(len(shorter) - seg_len + 1)
    )


def _pick_best_library(
    data: dict[str, Any] | list[Any] | None, query: str
) -> str | None:
    """Pick the best library from Context7 search response.

    Handles {"results": [...]} and [...] response formats.
    Returns None if no result has meaningful name overlap with the query,
    preventing silent wrong-library resolution.

    Scoring:
    - Exact title match: +100
    - Title contains query: +50
    - VIP library: +60
    - Verified: +40
    - Trust score: +trustScore * 5
    - Large corpus (>100k tokens): +5
    - Stars (capped at 20): +stars/1000
    - Benchmark score (capped at ~10): +benchmarkScore/10
    """
    # Unwrap response
    if isinstance(data, dict):
        results = data.get("results", [])
    elif isinstance(data, list):
        results = data
    else:
        return None

    if not results:
        return None

    query_lower = query.lower()

    def score_result(r: dict[str, Any]) -> float:
        score = 0.0
        title = r.get("title", "").lower()

        if title == query_lower:
            score += 100
        elif query_lower in title:
            score += 50

        if r.get("vip"):
            score += 60
        if r.get("verified"):
            score += 40

        trust = r.get("trustScore", 0)
        if trust > 0:
            score += trust * 5

        if r.get("totalTokens", 0) > 100000:
            score += 5

        # Star-based scoring (capped at 20 bonus points)
        stars = r.get("stars", 0)
        if stars > 0:
            score += min(stars / 1000, 20)

        # Benchmark score contribution (max ~10 bonus points)
        benchmark = r.get("benchmarkScore", 0)
        if benchmark > 0:
            score += benchmark / 10

        return score

    best = max(results, key=score_result)

    # Reject if no meaningful name overlap — prevents silently returning docs for
    # a completely unrelated library when the query doesn't match anything real.
    if not _has_title_overlap(query, best.get("title", "")):
        return None

    lib_id = best.get("id", "")

    # Ensure leading slash
    if lib_id and not lib_id.startswith("/"):
        lib_id = f"/{lib_id}"

    return lib_id if lib_id.count("/") >= 2 else None


@cache.memoize(ttl=3600)  # Cache library ID resolutions for 1 hour
def _resolve_library_id(library_id: str) -> tuple[str, bool, bool]:
    """Resolve a library ID, searching if needed.

    If the ID doesn't look like a valid /org/repo format,
    search Context7 to find the best match.

    Args:
        library_id: Raw or partial library ID

    Returns:
        Tuple of (resolved library ID with leading slash, was_searched, found_match).
        was_searched is True if a search was performed to resolve the ID.
        found_match is True if search found a valid library match.
    """
    normalized = _normalize_library_id(library_id)

    # If it looks like a valid /org/repo[/version], use it directly
    # Strip leading slash and check for at least org/repo
    parts = normalized.lstrip("/").split("/")
    if len(parts) >= 2 and parts[0] and parts[1] and not parts[0].startswith("http"):
        return normalized, False, True

    # Otherwise, search for the library using the name portion
    search_term = normalized.lstrip("/")
    success, data = _make_request(
        CONTEXT7_SEARCH_URL,
        params={"query": search_term, "libraryName": search_term},
    )

    if not success:
        return normalized, True, False

    # Use smart scoring to pick the best match
    best = _pick_best_library(
        data if isinstance(data, (dict, list)) else None, search_term
    )
    if best:
        return best, True, True
    return normalized, True, False


def search(*, query: str, library_name: str, output_format: str = "str") -> str:
    """Search for libraries by name in Context7.

    Args:
        query: The user's task or question — used for LLM relevance ranking
               (e.g., 'How do I set up JWT auth?')
        library_name: The library to find (e.g., 'express', 'react', 'fastapi')
        output_format: Response format - 'str' for string (default), 'dict' for JSON string

    Returns:
        Search results with matching libraries and their IDs.
        If output_format='dict', returns JSON string of the API response.
        If output_format='str', returns a formatted string representation.

    Example:
        context7.search(query="How do I set up JWT auth?", library_name="express")
        context7.search(query="react hooks tutorial", library_name="react")
        context7.search(query="fastapi", library_name="fastapi", output_format="dict")
    """
    if not query or not query.strip():
        return "query is required — used for LLM relevance ranking of search results."

    if output_format not in ("str", "dict"):
        return f"Invalid output_format '{output_format}'. Valid options: 'str', 'dict'."

    with LogSpan(
        span="context7.search",
        query=query,
        library_name=library_name,
        output_format=output_format,
    ) as s:
        success, result = _make_request(
            CONTEXT7_SEARCH_URL,
            params={"query": query, "libraryName": library_name},
        )

        s.add(success=success)
        if not success:
            return f"{result} query={query}"

        if output_format == "dict":
            s.add(resultType=type(result).__name__)
            return result

        # Format as a human-readable markdown list
        results = result.get("results", []) if isinstance(result, dict) else []
        if not results:
            result_str = "No libraries found."
        else:
            # Filter to results with meaningful name overlap
            matched = [
                r for r in results if _has_title_overlap(library_name, r.get("title", ""))
            ]

            lines = []
            if not matched:
                lines.append(
                    f"No libraries matching '{library_name}' were found. "
                    f"The following results may not be relevant:"
                )
                matched = results  # Show all with warning

            for r in matched:
                title = r.get("title", "")
                lib_id = r.get("id", "")
                desc = r.get("description", "")
                if not lib_id.startswith("/"):
                    lib_id = f"/{lib_id}"
                lines.append(f"- **{title}** (`{lib_id}`)")
                if desc:
                    lines.append(f"  {desc}")
            result_str = "\n".join(lines)
        s.add(resultLen=len(result_str))
        return result_str


def doc(
    *,
    library_id: str,
    query: str,
) -> str:
    """Fetch documentation for a library from Context7.

    Uses semantic reranking on the server side based on the query.

    Args:
        library_id: The library ID - can be flexible format:
            - Context7 format: '/vercel/next.js'
            - With version: '/vercel/next.js/v14.3.0-canary.87'
            - Without leading slash: 'vercel/next.js'
            - Shorthand: 'next.js', 'nextjs', 'react' (resolved via search)
            - GitHub URL: 'https://github.com/vercel/next.js'
        query: The user's natural-language question for server-side semantic
               reranking (e.g., 'How do I configure middleware for JWT?').
               Required — the Context7 API does not accept empty queries.

    Returns:
        Documentation content for the requested library and query.
        If the library ID was resolved via search, a note is prepended:
        "[Resolved 'nextjs' → '/vercel/next.js']"

    Example:
        # Get docs on a specific topic with semantic reranking
        context7.doc(library_id="/vercel/next.js", query="How do I configure middleware for JWT?")

        # Version-specific docs
        context7.doc(library_id="/vercel/next.js/v14.3.0-canary.87", query="app router migration")

        # Shorthand — resolved via search
        context7.doc(library_id="react", query="How do hooks work?")
    """
    if not query or not query.strip():
        return "query is required — the Context7 API does not accept empty queries."

    with LogSpan(span="context7.doc", libraryId=library_id, query=query) as s:
        # Normalize and resolve library ID (searches if needed)
        resolved_id, was_searched, found_match = _resolve_library_id(library_id)
        s.add(resolvedId=resolved_id, wasSearched=was_searched, foundMatch=found_match)

        # If search was performed but found no match, library doesn't exist
        if was_searched and not found_match:
            return (
                f"Library '{library_id}' not found. "
                f'Use context7.search(query="{library_id}", library_name="{library_id}") '
                f"to find available libraries."
            )

        # Build resolution note if library was found via search
        note = ""
        if was_searched and found_match:
            note = f"[Resolved '{library_id}' → '{resolved_id}']\n\n"

        # Fetch context
        params: dict[str, str] = {"libraryId": resolved_id, "type": "txt"}
        if query:
            params["query"] = query

        success, data = _make_request(CONTEXT7_CONTEXT_URL, params=params)
        s.add(success=success)

        if not success:
            error_str = str(data)
            if "404" in error_str:
                return (
                    f"Library '{resolved_id}' was not found in Context7. "
                    f'Use context7.search(query="...", library_name="...") '
                    f"to find the correct library ID."
                )
            return f"{data} library_id={library_id}"

        # Handle response
        if isinstance(data, str):
            if data in ("No content available", "No context data available", ""):
                return (
                    f"No documentation found for '{resolved_id}'. "
                    f"Try a different library ID or query."
                )
            s.add(resultLen=len(data))
            return note + data

        if isinstance(data, dict):
            result = str(data.get("content", data.get("text", str(data))))
            s.add(resultLen=len(result))
            return note + result

        result = str(data)
        s.add(resultLen=len(result))
        return note + result
