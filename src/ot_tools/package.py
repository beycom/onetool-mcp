"""Package version tools.

Check latest versions for npm, PyPI packages and search OpenRouter AI models.
No API keys required.

Attribution: Based on mcp-package-version by Sam McLeod - MIT License
"""

from __future__ import annotations

# Namespace for dot notation: package.version(), package.npm(), etc.
namespace = "package"

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from typing import Any

from ot.config import get_config
from ot.http_client import http_get
from ot.logging import LogSpan
from ot.utils import format_result

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_API = "https://pypi.org/pypi"
OPENROUTER_API = "https://openrouter.ai/api/v1/models"


def _clean_version(version: str) -> str:
    """Strip semver range prefixes (^, ~, >=, etc.) from version string."""
    import re

    return re.sub(r"^[\^~>=<]+", "", version)


def _fetch(url: str, timeout: float | None = None) -> tuple[bool, dict[str, Any] | str]:
    """Fetch JSON from URL.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (defaults to config)

    Returns:
        Tuple of (success, data_or_error)
    """
    if timeout is None:
        timeout = get_config().tools.package.timeout

    with LogSpan(span="package.fetch", url=url) as span:
        success, data = http_get(url, timeout=timeout)
        span.add(success=success)
        return success, data


def npm(*, packages: list[str]) -> str:
    """Check latest npm package versions.

    Args:
        packages: List of npm package names

    Returns:
        JSON list of {name, latest} entries

    Example:
        package.npm(packages=["react", "lodash", "express"])
    """
    return version(registry="npm", packages=packages)


def pypi(*, packages: list[str]) -> str:
    """Check latest PyPI package versions.

    Args:
        packages: List of Python package names

    Returns:
        JSON list of {name, latest} entries

    Example:
        package.pypi(packages=["requests", "flask", "fastapi"])
    """
    # Delegate to version() for parallel fetching
    return version(registry="pypi", packages=packages)


def _format_price(price: float | str | None) -> str:
    """Format price as $/MTok."""
    if price is None:
        return "N/A"
    try:
        price_float = float(price)
    except (ValueError, TypeError):
        return "N/A"
    # Price is per token, convert to per million tokens
    mtok = price_float * 1_000_000
    if mtok < 0.01:
        return f"${mtok:.4f}/MTok"
    return f"${mtok:.2f}/MTok"


def models(
    *,
    query: str = "",
    provider: str = "",
    limit: int = 20,
) -> str:
    """Search OpenRouter AI models.

    Args:
        query: Search query for model name/id (case-insensitive)
        provider: Filter by provider (e.g., "anthropic", "openai")
        limit: Maximum results to return (default: 20)

    Returns:
        JSON list of models with id, name, context_length, pricing, modality

    Example:
        # Search by name
        package.models(query="claude")

        # Filter by provider
        package.models(provider="anthropic", limit=5)
    """
    with LogSpan(span="package.models", query=query, provider=provider):
        ok, data = _fetch(OPENROUTER_API)
        if not ok or not isinstance(data, dict):
            return "[]"

        models_data = data.get("data", [])
        results = []

        query_lower = query.lower()
        provider_lower = provider.lower()

        for model in models_data:
            model_id = model.get("id", "")
            model_name = model.get("name", "")

            # Filter by query
            if (
                query_lower
                and query_lower not in model_id.lower()
                and query_lower not in model_name.lower()
            ):
                continue

            # Filter by provider
            if provider_lower and not model_id.lower().startswith(provider_lower + "/"):
                continue

            pricing = model.get("pricing", {})
            architecture = model.get("architecture", {})

            results.append(
                {
                    "id": model_id,
                    "name": model_name,
                    "context_length": model.get("context_length"),
                    "pricing": {
                        "prompt": _format_price(pricing.get("prompt")),
                        "completion": _format_price(pricing.get("completion")),
                    },
                    "modality": architecture.get("modality", "text->text"),
                }
            )

            if len(results) >= limit:
                break

        return format_result(results)


def _fetch_package(
    registry: str, pkg: str, current: str | None = None
) -> dict[str, Any]:
    """Fetch single package version from npm or pypi."""
    if registry == "npm":
        ok, data = _fetch(f"{NPM_REGISTRY}/{pkg}")
        latest = (
            data.get("dist-tags", {}).get("latest", "unknown")
            if ok and isinstance(data, dict)
            else "unknown"
        )
    else:  # pypi
        ok, data = _fetch(f"{PYPI_API}/{pkg}/json")
        latest = (
            data.get("info", {}).get("version", "unknown")
            if ok and isinstance(data, dict)
            else "unknown"
        )

    result: dict[str, Any] = {"name": pkg, "registry": registry, "latest": latest}
    if current is not None:
        result["current"] = _clean_version(current)
    return result


def _format_created(timestamp: int | None) -> str:
    """Format Unix timestamp as yyyymmdd."""
    if not timestamp:
        return "unknown"
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return dt.strftime("%Y%m%d")


def _fetch_model(query: str, all_models: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find first matching model by wildcard pattern or contains check.

    Supports glob-style wildcards:
        "openai/gpt-5.*" - matches openai/gpt-5.1, openai/gpt-5.2, etc.
        "google/gemini-*-flash-*" - matches gemini flash variants
        "anthropic/claude-sonnet-4.*" - matches claude-sonnet-4.x versions
    """
    from fnmatch import fnmatch

    query_lower = query.lower()
    use_glob = "*" in query

    for model in all_models:
        model_id = model.get("id", "")
        model_id_lower = model_id.lower()

        # Match: glob pattern or contains check
        if use_glob:
            matched = fnmatch(model_id_lower, query_lower)
        else:
            matched = query_lower in model_id_lower

        if matched:
            pricing = model.get("pricing", {})
            return {
                "query": query,
                "registry": "openrouter",
                "id": model_id,
                "name": model.get("name", ""),
                "created": _format_created(model.get("created")),
                "context_length": model.get("context_length"),
                "pricing": {
                    "prompt": _format_price(pricing.get("prompt")),
                    "completion": _format_price(pricing.get("completion")),
                },
            }
    return {
        "query": query,
        "registry": "openrouter",
        "id": "unknown",
        "created": "unknown",
    }


def version(
    *,
    registry: str,
    packages: list[str] | dict[str, str],
) -> str:
    """Check latest versions for packages from a registry.

    Args:
        registry: Package registry - "npm", "pypi", or "openrouter"
        packages: List of package names, or dict mapping names to current versions

    Returns:
        JSON list of version results. If current versions provided,
        includes both 'current' and 'latest' fields.

    Examples:
        # Just get latest versions
        package.version(registry="npm", packages=["react", "lodash"])
        package.version(registry="pypi", packages=["requests", "flask"])
        package.version(registry="openrouter", packages=["claude", "gpt-4"])

        # Provide current versions, get both current and latest
        package.version(registry="npm", packages={"react": "^18.0.0", "lodash": "^4.0.0"})
        package.version(registry="pypi", packages={"requests": "2.31.0", "flask": "3.0.0"})
    """
    # Normalize input: convert dict to list of tuples (name, current_version)
    if isinstance(packages, dict):
        pkg_list = [(name, ver) for name, ver in packages.items()]
    else:
        pkg_list = [(name, None) for name in packages]

    with LogSpan(span="package.version", registry=registry, count=len(pkg_list)):
        results: list[dict[str, Any]] = []

        if registry in ("npm", "pypi"):
            with ThreadPoolExecutor(max_workers=min(len(pkg_list), 20)) as executor:
                futures = [
                    executor.submit(_fetch_package, registry, pkg, current)
                    for pkg, current in pkg_list
                ]
                results = [f.result() for f in futures]

        elif registry == "openrouter":
            ok, data = _fetch(OPENROUTER_API)
            all_models: list[dict[str, Any]] = []
            if ok and isinstance(data, dict):
                all_models = data.get("data", [])
            for q, _ in pkg_list:
                r = _fetch_model(q, all_models)
                if r:
                    results.append(r)

        else:
            return f"Unknown registry: {registry}. Use npm, pypi, or openrouter."

        return format_result(results)
