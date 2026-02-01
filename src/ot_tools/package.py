"""Package version tools.

Check latest versions for npm, PyPI packages and search OpenRouter AI models.
No API keys required.

Attribution: Based on mcp-package-version by Sam McLeod - MIT License
"""

from __future__ import annotations

# Pack for dot notation: package.version(), package.npm(), etc.
pack = "package"

__all__ = ["audit", "models", "npm", "pypi", "version"]

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.http_client import http_get
from ot.logging import LogSpan


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_API = "https://pypi.org/pypi"
OPENROUTER_API = "https://openrouter.ai/api/v1/models"


def _clean_version(version: str) -> str:
    """Strip semver range prefixes (^, ~, >=, etc.) from version string."""
    return re.sub(r"^[\^~>=<]+", "", version)


def _parse_version_constraint(constraint: str) -> str | None:
    """Extract version from a constraint string like 'requests>=2.28.0' or '>=2.28.0'.

    Returns the version part or None if no version found.
    """
    # Match patterns like: >=2.28.0, ==1.0.0, ~=3.0, ^18.0.0, etc.
    match = re.search(r"[\^~>=<!=]+\s*(\d+[.\d]*[a-zA-Z0-9.-]*)", constraint)
    if match:
        return match.group(1)
    # Match bare version like "2.28.0"
    match = re.match(r"^(\d+[.\d]*[a-zA-Z0-9.-]*)$", constraint.strip())
    if match:
        return match.group(1)
    return None


def _parse_pyproject_toml(path: Path) -> dict[str, str]:
    """Parse dependencies from pyproject.toml.

    Extracts from:
    - project.dependencies
    - project.optional-dependencies.*
    - dependency-groups.*
    """
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[import-not-found]

    content = path.read_text()
    data = tomllib.loads(content)

    deps: dict[str, str] = {}

    # project.dependencies
    project = data.get("project", {})
    for dep in project.get("dependencies", []):
        name, ver = _parse_dependency_string(dep)
        if name:
            deps[name] = ver

    # project.optional-dependencies
    for group_deps in project.get("optional-dependencies", {}).values():
        for dep in group_deps:
            name, ver = _parse_dependency_string(dep)
            if name:
                deps[name] = ver

    # dependency-groups (PEP 735)
    for group_deps in data.get("dependency-groups", {}).values():
        for dep in group_deps:
            # Skip include-group references like {"include-group": "dev"}
            if isinstance(dep, str):
                name, ver = _parse_dependency_string(dep)
                if name:
                    deps[name] = ver

    return deps


def _parse_dependency_string(dep: str) -> tuple[str | None, str]:
    """Parse a PEP 508 dependency string like 'requests>=2.28.0' or 'requests[security]>=2.28.0'.

    Returns (name, version_constraint) or (None, "") if invalid.
    """
    # Remove extras like [security] and environment markers
    dep = dep.split(";")[0].strip()  # Remove environment markers

    # Match: name[extras]version_spec or name version_spec
    match = re.match(r"^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?\s*(.*)$", dep)
    if match:
        name = match.group(1).lower().replace("_", "-")
        version_spec = match.group(2).strip()
        return name, version_spec
    return None, ""


def _parse_requirements_txt(path: Path) -> dict[str, str]:
    """Parse dependencies from requirements.txt."""
    deps: dict[str, str] = {}

    for line in path.read_text().splitlines():
        line = line.strip()
        # Skip empty lines, comments, and options
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Skip editable installs
        if line.startswith("git+") or line.startswith("http"):
            continue

        name, ver = _parse_dependency_string(line)
        if name:
            deps[name] = ver

    return deps


def _parse_package_json(path: Path) -> dict[str, str]:
    """Parse dependencies from package.json.

    Extracts from:
    - dependencies
    - devDependencies
    """
    import json

    data = json.loads(path.read_text())
    deps: dict[str, str] = {}

    for section in ("dependencies", "devDependencies"):
        for name, ver in data.get(section, {}).items():
            deps[name] = ver

    return deps


def _compare_versions(current: str | None, latest: str) -> str:
    """Compare current version against latest and return status.

    Returns: "current", "update_available", "major_update", or "unknown"
    """
    if not current or latest == "unknown":
        return "unknown"

    # Clean version strings
    current_clean = _clean_version(current)
    latest_clean = latest

    if current_clean == latest_clean:
        return "current"

    # Try to parse semver for major version comparison
    current_parts = current_clean.split(".")
    latest_parts = latest_clean.split(".")

    try:
        current_match = re.match(r"(\d+)", current_parts[0])
        latest_match = re.match(r"(\d+)", latest_parts[0])

        if current_match and latest_match:
            current_major = int(current_match.group(1))
            latest_major = int(latest_match.group(1))

            if latest_major > current_major:
                return "major_update"
    except (ValueError, IndexError):
        pass

    return "update_available"


def _detect_manifest(path: Path) -> tuple[str, Path] | None:
    """Auto-detect manifest file in directory.

    Returns (registry, manifest_path) or None if not found.
    """
    # Check in order of preference
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        return "pypi", pyproject

    requirements = path / "requirements.txt"
    if requirements.exists():
        return "pypi", requirements

    package_json = path / "package.json"
    if package_json.exists():
        return "npm", package_json

    return None


def audit(
    *,
    path: str = ".",
    registry: str | None = None,
) -> dict[str, Any]:
    """Audit project dependencies against latest registry versions.

    Auto-detects manifest files (pyproject.toml, requirements.txt, package.json)
    and compares current versions against the latest available.

    Args:
        path: Project directory path (default: current directory)
        registry: Force specific registry ("npm" or "pypi"). Auto-detects if not specified.

    Returns:
        Dict with manifest, registry, packages list, and summary counts.
        Each package has: name, required, latest, status.

    Example:
        package.audit()
        package.audit(path="./frontend", registry="npm")
    """
    with LogSpan(span="package.audit", path=path, registry=registry) as span:
        base_path = Path(path).resolve()

        # Determine registry and manifest
        if registry:
            # Explicit registry - find matching manifest
            if registry == "npm":
                manifest_path = base_path / "package.json"
                if not manifest_path.exists():
                    span.add(error="manifest_not_found")
                    return {"error": f"No package.json found in {path}"}
            elif registry == "pypi":
                manifest_path = base_path / "pyproject.toml"
                if not manifest_path.exists():
                    manifest_path = base_path / "requirements.txt"
                if not manifest_path.exists():
                    span.add(error="manifest_not_found")
                    return {"error": f"No pyproject.toml or requirements.txt found in {path}"}
            else:
                span.add(error="invalid_registry")
                return {"error": f"Invalid registry: {registry}. Use 'npm' or 'pypi'."}
        else:
            # Auto-detect
            detected = _detect_manifest(base_path)
            if not detected:
                span.add(error="no_manifest")
                return {
                    "error": f"No manifest found in {path}. Looking for: pyproject.toml, requirements.txt, package.json"
                }
            registry, manifest_path = detected

        # Parse manifest
        deps: dict[str, str] = {}
        manifest_name = manifest_path.name

        if manifest_name == "pyproject.toml":
            deps = _parse_pyproject_toml(manifest_path)
        elif manifest_name == "requirements.txt":
            deps = _parse_requirements_txt(manifest_path)
        elif manifest_name == "package.json":
            deps = _parse_package_json(manifest_path)

        if not deps:
            span.add(error="no_dependencies")
            return {"error": f"No dependencies found in {manifest_path}"}

        span.add(count=len(deps))

        # Fetch latest versions in parallel
        with ThreadPoolExecutor(max_workers=min(len(deps), 20)) as executor:
            futures = {
                name: executor.submit(_fetch_package, registry, name, ver)
                for name, ver in deps.items()
            }
            results = {name: f.result() for name, f in futures.items()}

        # Build package list with status
        packages: list[dict[str, Any]] = []
        summary = {"current": 0, "update_available": 0, "major_update": 0, "unknown": 0}

        for name in sorted(deps.keys()):
            result = results[name]
            required = deps[name] or "*"
            latest = result.get("latest", "unknown")

            # Get version from required constraint
            current_ver = _parse_version_constraint(required) if required != "*" else None
            status = _compare_versions(current_ver, latest)

            packages.append(
                {
                    "name": name,
                    "required": required,
                    "latest": latest,
                    "status": status,
                }
            )
            summary[status] += 1

        span.add(summary=summary)

        return {
            "manifest": str(manifest_path),
            "registry": registry,
            "packages": packages,
            "summary": summary,
        }


def _fetch(url: str, timeout: float | None = None) -> tuple[bool, dict[str, Any] | str]:
    """Fetch JSON from URL.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (defaults to config)

    Returns:
        Tuple of (success, data_or_error)
    """
    if timeout is None:
        timeout = get_tool_config("package", Config).timeout

    with LogSpan(span="package.fetch", url=url) as span:
        success, data = http_get(url, timeout=timeout)
        span.add(success=success)
        return success, data


def npm(*, packages: list[str]) -> list[dict[str, Any]]:
    """Check latest npm package versions.

    Args:
        packages: List of npm package names

    Returns:
        List of dicts with name, registry, latest fields

    Example:
        package.npm(packages=["react", "lodash", "express"])
    """
    return version(registry="npm", packages=packages)


def pypi(*, packages: list[str]) -> list[dict[str, Any]]:
    """Check latest PyPI package versions.

    Args:
        packages: List of Python package names

    Returns:
        List of dicts with name, registry, latest fields

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
) -> list[dict[str, Any]]:
    """Search OpenRouter AI models.

    Args:
        query: Search query for model name/id (case-insensitive)
        provider: Filter by provider (e.g., "anthropic", "openai")
        limit: Maximum results to return (default: 20)

    Returns:
        List of model dicts with id, name, context_length, pricing, modality

    Example:
        # Search by name
        package.models(query="claude")

        # Filter by provider
        package.models(provider="anthropic", limit=5)
    """
    with LogSpan(span="package.models", query=query, provider=provider):
        ok, data = _fetch(OPENROUTER_API)
        if not ok or not isinstance(data, dict):
            return []

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

        return results


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
) -> list[dict[str, Any]] | str:
    """Check latest versions for packages from a registry.

    Args:
        registry: Package registry - "npm", "pypi", or "openrouter"
        packages: List of package names, or dict mapping names to current versions

    Returns:
        List of version result dicts. If current versions provided,
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

        return results
