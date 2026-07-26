"""Dependency validation utilities for OneTool.

Provides decorators and functions for declaring and checking normalized tool
requirements.

Example:
    # Decorator usage
    from ot.utils import requires_cli, requires_lib

    @requires_cli(
        "rg",
        purpose="Search files",
        authoritative_url="https://github.com/BurntSushi/ripgrep",
    )
    from ot.catalog import InstallExtra

    @requires_lib(
        "sqlalchemy",
        purpose="Database access",
        install_extra=InstallExtra.DEV,
    )
    def query(sql: str) -> str:
        ...

    # Module-level declaration (for AST scanning)
    __ot_requires__ = [
        {
            "kind": "cli",
            "name": "ripgrep",
            "executable": "rg",
            "purpose": "Search files",
            "authoritative_url": "https://github.com/BurntSushi/ripgrep",
        },
    ]
"""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from ot.catalog import InstallExtra, PackRequirement, RequirementKind

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "Dependency",
    "DepsCheckResult",
    "check_cli",
    "check_deps",
    "check_lib",
    "check_secret",
    "ensure_cli",
    "ensure_lib",
    "requires_cli",
    "requires_lib",
]

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class Dependency:
    """Represents a single dependency."""

    name: str
    kind: RequirementKind
    purpose: str = ""
    install: str = ""
    version: str = ""
    available: bool = False
    error: str = ""


@dataclass
class DepsCheckResult:
    """Result of checking dependencies for a tool or pack."""

    tool: str
    dependencies: list[Dependency] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Check if all dependencies are available."""
        return all(dep.available for dep in self.dependencies)

    @property
    def missing(self) -> list[Dependency]:
        """Get list of missing dependencies."""
        return [dep for dep in self.dependencies if not dep.available]


def requires_cli(
    name: str,
    *,
    purpose: str,
    authoritative_url: str | None = None,
    optional: bool = False,
) -> Callable[[F], F]:
    """Decorator to declare a CLI tool dependency.

    Adds dependency metadata to the function for discovery by check_deps().
    Does NOT perform runtime checking - use check_cli() for that.

    Args:
        name: CLI command name (e.g., "rg", "ffmpeg", "pandoc")
        purpose: Why the executable is needed.
        authoritative_url: Publisher documentation for platform-specific setup.
        optional: Whether the whole pack can operate without this workflow.

    Returns:
        Decorator that adds dependency metadata to the function

    Example:
        @requires_cli(
            "rg",
            purpose="Search files",
            authoritative_url="https://github.com/BurntSushi/ripgrep",
        )
        def search_with_ripgrep(pattern: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = []  # type: ignore[attr-defined]
        func.__ot_requires__.append(  # type: ignore[attr-defined]
            PackRequirement(
                kind=RequirementKind.CLI,
                name=name,
                executable=name,
                purpose=purpose,
                authoritative_url=authoritative_url,
                optional=optional,
            )
        )
        return func

    return decorator


def requires_lib(
    name: str,
    *,
    purpose: str,
    install_extra: InstallExtra,
    import_name: str | None = None,
    optional: bool = False,
) -> Callable[[F], F]:
    """Decorator to declare a Python library dependency.

    Adds dependency metadata to the function for discovery by check_deps().
    Does NOT perform runtime checking - use check_lib() for that.

    Args:
        name: Package name (e.g., "sqlalchemy", "openai")
        purpose: Why the library is needed.
        install_extra: Supported OneTool installation extra.
        import_name: Import name if different from package name
        optional: Whether the whole pack can operate without this workflow.

    Returns:
        Decorator that adds dependency metadata to the function

    Example:
        @requires_lib(
            "sqlalchemy",
            purpose="Database access",
            install_extra=InstallExtra.DEV,
        )
        def query_database(sql: str) -> str:
            ...

        @requires_lib(
            "google-genai",
            purpose="Run Gemini requests",
            install_extra=InstallExtra.UTIL,
            import_name="google.genai",
        )
        def search_with_gemini(query: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = []  # type: ignore[attr-defined]
        func.__ot_requires__.append(  # type: ignore[attr-defined]
            PackRequirement(
                kind=RequirementKind.LIB,
                name=name,
                purpose=purpose,
                install_extra=install_extra,
                import_name=import_name or name,
                optional=optional,
            )
        )
        return func

    return decorator


def check_cli(name: str) -> Dependency:
    """Check if a CLI tool is available in PATH.

    Args:
        name: CLI command name to check

    Returns:
        Dependency object with availability status
    """
    dep = Dependency(name=name, kind=RequirementKind.CLI)
    path = shutil.which(name)
    if path:
        dep.available = True
    else:
        dep.error = f"'{name}' not found in PATH"
    return dep


def check_lib(name: str, import_name: str = "") -> Dependency:
    """Check if a Python library is importable.

    Args:
        name: Package name
        import_name: Import name if different from package name

    Returns:
        Dependency object with availability status
    """
    dep = Dependency(name=name, kind=RequirementKind.LIB)
    module_name = import_name or name

    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        dep.available = True
    else:
        dep.error = f"Module '{module_name}' not importable"

    return dep


def check_secret(name: str) -> Dependency:
    """Check if a secret is configured.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Dependency object with availability status
    """
    from ot.config.secrets import get_secret

    dep = Dependency(name=name, kind=RequirementKind.SECRET)
    value = get_secret(name)
    if value:
        dep.available = True
    else:
        dep.error = f"Secret '{name}' not configured"
    return dep


def check_deps(
    tool_path: str | Path | None = None,
) -> list[DepsCheckResult]:
    """Check dependencies for all tools or a specific tool.

    Uses the ToolRegistry to scan tool files for __ot_requires__ declarations
    and checks each dependency for availability.

    Args:
        tool_path: Path to a specific tool file, or None to check all tools

    Returns:
        List of DepsCheckResult for each tool with declared dependencies

    Example:
        results = check_deps()
        for result in results:
            if not result.ok:
                print(f"{result.tool}: missing {len(result.missing)} deps")
                for dep in result.missing:
                    print(f"  - {dep.name}: {dep.install}")
    """
    from pathlib import Path

    from ot.registry import ToolRegistry

    results: list[DepsCheckResult] = []

    # Determine which files to check
    if tool_path:
        files = [Path(tool_path)]
    else:
        files = []

        try:
            from ot.config.loader import get_config
            from ot.executor.tool_loader import _get_tool_files

            config = get_config()
            current_files, _internal_files, _cache_key = _get_tool_files(None, config)
            files.extend(sorted(current_files))
        except Exception:
            pass

        if not files:
            return results

    # Use ToolRegistry to parse files (extracts __ot_requires__ via AST)
    registry = ToolRegistry()
    tools = registry.scan_files(files)

    # Group tools by pack/module to dedupe (all tools in a file share requires)
    seen_packs: set[str] = set()
    for tool in tools:
        if not tool.requires:
            continue

        # Use pack name or module stem as identifier
        pack_id = tool.pack or tool.module.split(".")[-1]
        if pack_id in seen_packs:
            continue
        seen_packs.add(pack_id)

        tool_result = DepsCheckResult(tool=pack_id)

        for requirement in tool.requires:
            if requirement.kind is RequirementKind.CLI:
                dep = check_cli(requirement.executable or requirement.name)
                dep.install = requirement.authoritative_url or ""
            elif requirement.kind is RequirementKind.LIB:
                dep = check_lib(
                    requirement.name,
                    requirement.import_name or requirement.name,
                )
                if requirement.install_extra:
                    dep.install = f"pip install onetool-mcp{requirement.install_extra}"
            elif requirement.kind is RequirementKind.SECRET:
                dep = check_secret(requirement.name)
                dep.install = "Configure the named secret through OneTool"
            else:
                continue
            dep.purpose = requirement.purpose
            tool_result.dependencies.append(dep)

        if tool_result.dependencies:
            results.append(tool_result)

    return results


def ensure_cli(
    name: str,
    *,
    install: str = "",
) -> str | None:
    """Check CLI availability at runtime, returning error message if missing.

    Convenience function for early validation in tool functions.

    Args:
        name: CLI command name
        install: Installation instructions

    Returns:
        None if available, error message string if missing

    Example:
        def my_tool() -> str:
            if error := ensure_cli("rg", install="brew install ripgrep"):
                return error
            # Continue with ripgrep operations
    """
    dep = check_cli(name)
    if dep.available:
        return None
    msg = f"Error: '{name}' CLI tool not found"
    if install:
        msg += f". Install with: {install}"
    return msg


def ensure_lib(
    name: str,
    *,
    import_name: str = "",
    install: str = "",
) -> str | None:
    """Check library availability at runtime, returning error message if missing.

    Convenience function for early validation in tool functions.

    Args:
        name: Package name
        import_name: Import name if different from package name
        install: Installation instructions

    Returns:
        None if available, error message string if missing

    Example:
        def my_tool() -> str:
            if error := ensure_lib("sqlalchemy"):
                return error
            import sqlalchemy
            # Continue with sqlalchemy operations
    """
    dep = check_lib(name, import_name)
    if dep.available:
        return None
    install = install or f"pip install {name}"
    return f"Error: '{name}' library not available. Install with: {install}"
