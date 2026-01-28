"""Dependency validation utilities for OneTool.

Provides decorators and functions for declaring and checking tool dependencies.
Supports both CLI tools (external binaries) and Python libraries.

Example:
    # Decorator usage
    from ot.utils import requires_cli, requires_lib

    @requires_cli("rg", install="brew install ripgrep")
    @requires_lib("duckdb", install="pip install duckdb")
    def search(query: str) -> str:
        ...

    # Module-level declaration (for AST scanning)
    __ot_requires__ = {
        "cli": [("rg", "brew install ripgrep")],
        "lib": [("duckdb", "pip install duckdb")],
    }
"""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

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
    kind: str  # "cli" or "lib"
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
    install: str = "",
    version_flag: str = "--version",
) -> Callable[[F], F]:
    """Decorator to declare a CLI tool dependency.

    Adds dependency metadata to the function for discovery by check_deps().
    Does NOT perform runtime checking - use check_cli() for that.

    Args:
        name: CLI command name (e.g., "rg", "ffmpeg", "pandoc")
        install: Installation instructions shown when missing
        version_flag: Flag to check version (default: "--version")

    Returns:
        Decorator that adds dependency metadata to the function

    Example:
        @requires_cli("rg", install="brew install ripgrep")
        def search_with_ripgrep(pattern: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        # Initialize or extend __ot_requires__ attribute
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = {"cli": [], "lib": []}  # type: ignore[attr-defined]

        func.__ot_requires__["cli"].append(  # type: ignore[attr-defined]
            {"name": name, "install": install, "version_flag": version_flag}
        )
        return func

    return decorator


def requires_lib(
    name: str,
    *,
    install: str = "",
    import_name: str = "",
) -> Callable[[F], F]:
    """Decorator to declare a Python library dependency.

    Adds dependency metadata to the function for discovery by check_deps().
    Does NOT perform runtime checking - use check_lib() for that.

    Args:
        name: Package name (e.g., "duckdb", "openai")
        install: Installation instructions (default: "pip install {name}")
        import_name: Import name if different from package name

    Returns:
        Decorator that adds dependency metadata to the function

    Example:
        @requires_lib("duckdb", install="pip install duckdb")
        def query_database(sql: str) -> str:
            ...

        @requires_lib("google-genai", import_name="google.genai")
        def search_with_gemini(query: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = {"cli": [], "lib": []}  # type: ignore[attr-defined]

        func.__ot_requires__["lib"].append(  # type: ignore[attr-defined]
            {
                "name": name,
                "install": install or f"pip install {name}",
                "import_name": import_name or name,
            }
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
    dep = Dependency(name=name, kind="cli")
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
    dep = Dependency(name=name, kind="lib")
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

    dep = Dependency(name=name, kind="secret")
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

        # Always include bundled tools from ot_tools package
        try:
            import ot_tools

            bundled_dir = Path(ot_tools.__file__).parent
            bundled_files = [
                f for f in bundled_dir.glob("*.py") if f.name != "__init__.py"
            ]
            files.extend(bundled_files)
        except ImportError:
            pass

        # Add config-specified tools
        try:
            from ot.config.loader import get_config

            config = get_config()
            if config:
                config_files = config.get_tool_files()
                files.extend(config_files)
        except Exception:
            pass  # Config may not be available, use bundled tools only

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

        # Check CLI dependencies
        for cli_dep in tool.requires.get("cli", []):
            # Handle both tuple format (name, install) and dict format
            if isinstance(cli_dep, tuple):
                name, install = cli_dep[0], cli_dep[1] if len(cli_dep) > 1 else ""
            else:
                name = cli_dep.get("name", "")
                install = cli_dep.get("install", "")
            dep = check_cli(name)
            dep.install = install
            tool_result.dependencies.append(dep)

        # Check library dependencies
        for lib_dep in tool.requires.get("lib", []):
            # Handle both tuple format (name, install) and dict format
            if isinstance(lib_dep, tuple):
                name, install = lib_dep[0], lib_dep[1] if len(lib_dep) > 1 else ""
                import_name = ""
            else:
                name = lib_dep.get("name", "")
                install = lib_dep.get("install", f"pip install {name}")
                import_name = lib_dep.get("import_name", "")
            dep = check_lib(name, import_name)
            dep.install = install or f"pip install {name}"
            tool_result.dependencies.append(dep)

        # Check secret dependencies
        for secret_name in tool.requires.get("secrets", []):
            dep = check_secret(secret_name)
            dep.install = "Add to secrets.yaml"
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
            if error := ensure_lib("duckdb"):
                return error
            import duckdb
            # Continue with duckdb operations
    """
    dep = check_lib(name, import_name)
    if dep.available:
        return None
    install = install or f"pip install {name}"
    return f"Error: '{name}' library not available. Install with: {install}"
