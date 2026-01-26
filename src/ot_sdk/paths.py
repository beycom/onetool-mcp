"""Path resolution utilities for worker tools.

Provides functions for resolving paths relative to project or config directories.
Path context is passed to workers via the JSON-RPC request config.

## Path Contexts

Two primary contexts are available:

- **CWD** (`resolve_cwd_path`): Project working directory (OT_CWD).
  Use for reading/writing user files.

- **OT_DIR** (`resolve_ot_path`): Config directory (.onetool/).
  Use for config assets like templates. Project-first, global fallback.

## Path Prefixes

Paths can use prefixes to specify the resolution base:

| Prefix   | Meaning                    | Use Case                   |
|----------|----------------------------|----------------------------|
| `~`      | Home directory             | Cross-project shared files |
| `CWD`    | OT_CWD (project root)      | Tool I/O files             |
| `GLOBAL` | ~/.onetool/                | Global config/logs         |
| `OT_DIR` | Active .onetool            | Project-first, global fallback |

## Example

    from ot_sdk import resolve_cwd_path, resolve_ot_path, get_ot_dir

    # Save output to project directory
    output = resolve_cwd_path("diagrams/flow.svg")

    # Load template from config directory
    template = resolve_ot_path("templates/default.mmd")

    # Use prefix to override default base
    global_log = resolve_cwd_path("GLOBAL/logs/app.log")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from ot_sdk.config import _current_config

# =============================================================================
# Base Directory Functions
# =============================================================================


def _get_cwd() -> Path:
    """Get the project working directory (OT_CWD).

    Resolution order:
        1. _project_path from config (set for workers via JSON-RPC)
        2. OT_CWD environment variable (set for server-side tools)
        3. Path.cwd() fallback

    Returns:
        Path to the project working directory
    """
    # Check config first (for workers)
    project_path = _current_config.get("_project_path")
    if project_path:
        return Path(project_path)

    # Check env var (for server-side tools)
    ot_cwd = os.environ.get("OT_CWD")
    if ot_cwd:
        return Path(ot_cwd)

    return Path.cwd()


def _get_global_dir() -> Path:
    """Get the global config directory (~/.onetool/)."""
    return Path.home() / ".onetool"


def get_ot_dir() -> Path:
    """Get the active OneTool config directory.

    Resolution order:
        1. Project config dir if set in context (from ot-serve)
        2. CWD/.onetool/ if exists
        3. ~/.onetool/ (global fallback)

    Returns:
        Path to the active .onetool directory

    Example:
        >>> get_ot_dir()
        PosixPath('/project/.onetool')
    """
    # Check if config_dir is set in context (from ot-serve)
    config_dir = _current_config.get("_config_dir")
    if config_dir:
        return Path(config_dir)

    # Check for project-local .onetool
    cwd = _get_cwd()
    project_ot = cwd / ".onetool"
    if project_ot.is_dir():
        return project_ot

    # Fall back to global
    return _get_global_dir()


# =============================================================================
# Core Path Resolution
# =============================================================================


def resolve_path(
    path: str,
    base: Literal["CWD", "OT_DIR", "GLOBAL"] = "CWD",
) -> Path:
    """Resolve a path with prefix expansion and configurable base.

    This is the core path resolution function. Paths can include prefixes
    to override the default base:

    - `~`: Home directory
    - `CWD`: Project working directory (OT_CWD)
    - `GLOBAL`: Global config directory (~/.onetool/)
    - `OT_DIR`: Active config directory (project-first, global fallback)

    Args:
        path: Path string, optionally with prefix
        base: Default base for relative paths ("CWD", "OT_DIR", or "GLOBAL")

    Returns:
        Resolved absolute Path

    Example:
        >>> resolve_path("data/file.txt")  # Default: CWD
        PosixPath('/project/data/file.txt')
        >>> resolve_path("data/file.txt", base="OT_DIR")
        PosixPath('/project/.onetool/data/file.txt')
        >>> resolve_path("GLOBAL/logs/app.log")  # Prefix overrides base
        PosixPath('/home/user/.onetool/logs/app.log')
        >>> resolve_path("CWD/output.txt", base="OT_DIR")  # Prefix overrides
        PosixPath('/project/output.txt')
    """
    # Handle ~ prefix (home directory)
    if path.startswith("~"):
        return Path(path).expanduser().resolve()

    # Check for explicit prefixes
    if path.startswith("CWD/") or path == "CWD":
        remainder = path[4:] if path.startswith("CWD/") else ""
        return (_get_cwd() / remainder).resolve() if remainder else _get_cwd()

    if path.startswith("GLOBAL/") or path == "GLOBAL":
        remainder = path[7:] if path.startswith("GLOBAL/") else ""
        return (_get_global_dir() / remainder).resolve() if remainder else _get_global_dir()

    if path.startswith("OT_DIR/") or path == "OT_DIR":
        remainder = path[7:] if path.startswith("OT_DIR/") else ""
        return (get_ot_dir() / remainder).resolve() if remainder else get_ot_dir()

    # Absolute paths returned as-is
    p = Path(path)
    if p.is_absolute():
        return p.resolve()

    # Resolve relative path against the base
    if base == "CWD":
        return (_get_cwd() / p).resolve()
    elif base == "OT_DIR":
        return (get_ot_dir() / p).resolve()
    elif base == "GLOBAL":
        return (_get_global_dir() / p).resolve()
    else:
        # Shouldn't happen with Literal type, but handle gracefully
        return (_get_cwd() / p).resolve()


def resolve_cwd_path(path: str) -> Path:
    """Resolve a path relative to the project working directory (OT_CWD).

    Convenience wrapper for `resolve_path(path, base="CWD")`.

    Use this for reading/writing files in the user's project.

    Args:
        path: Path string, optionally with prefix

    Returns:
        Resolved absolute Path

    Example:
        >>> resolve_cwd_path("data/file.txt")
        PosixPath('/project/data/file.txt')
        >>> resolve_cwd_path("~/shared/data.txt")
        PosixPath('/home/user/shared/data.txt')
        >>> resolve_cwd_path("GLOBAL/logs/app.log")
        PosixPath('/home/user/.onetool/logs/app.log')
    """
    return resolve_path(path, base="CWD")


def resolve_ot_path(path: str) -> Path:
    """Resolve a path relative to the active OneTool config directory.

    Convenience wrapper for `resolve_path(path, base="OT_DIR")`.

    Use this for loading config assets like templates, schemas, or reference files.

    Args:
        path: Path string, optionally with prefix

    Returns:
        Resolved absolute Path

    Example:
        >>> resolve_ot_path("templates/flow.mmd")
        PosixPath('/project/.onetool/templates/flow.mmd')
        >>> resolve_ot_path("CWD/output.txt")
        PosixPath('/project/output.txt')
    """
    return resolve_path(path, base="OT_DIR")


# =============================================================================
# Legacy Functions (for backward compatibility)
# =============================================================================


def get_project_path(path: str) -> Path:
    """Resolve a path relative to the project working directory.

    .. deprecated:: Use `resolve_cwd_path()` instead.

    Use this for reading/writing files in the user's project.

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path

    Behaviour:
        - Relative paths: resolved relative to project directory (OT_CWD)
        - Absolute paths: returned unchanged
        - ~ paths: expanded to home directory

    Example:
        >>> get_project_path("diagrams/flow.svg")
        PosixPath('/project/diagrams/flow.svg')
        >>> get_project_path("/tmp/output.svg")
        PosixPath('/tmp/output.svg')
        >>> get_project_path("~/output.svg")
        PosixPath('/home/user/output.svg')
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p

    # Get project path from config (set by ot-serve)
    project_path = _current_config.get("_project_path")
    if project_path:
        return (Path(project_path) / p).resolve()

    # Fallback to cwd if not set
    return (Path.cwd() / p).resolve()


def get_config_path(path: str) -> Path:
    """Resolve a path relative to the config directory.

    .. deprecated:: Use `resolve_ot_path()` instead.

    Use this for loading config assets like templates, schemas, or reference files.

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path

    Behaviour:
        - Relative paths: resolved relative to config directory (.onetool/)
        - Absolute paths: returned unchanged
        - ~ paths: expanded to home directory

    Example:
        >>> get_config_path("templates/flow.mmd")
        PosixPath('/project/.onetool/templates/flow.mmd')
        >>> get_config_path("/etc/templates/flow.mmd")
        PosixPath('/etc/templates/flow.mmd')
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p

    # Get config directory from config (set by ot-serve)
    config_dir = _current_config.get("_config_dir")
    if config_dir:
        return (Path(config_dir) / p).resolve()

    # Fallback to cwd if not set
    return (Path.cwd() / p).resolve()


def expand_path(path: str) -> Path:
    """Expand ~ in a path without resolving relative paths.

    Only expands ~ to home directory. Does NOT:
    - Resolve relative paths against any directory
    - Expand ${VAR} environment variables

    Args:
        path: Path string potentially containing ~

    Returns:
        Path with ~ expanded (not resolved)

    Example:
        >>> expand_path("~/config.yaml")
        PosixPath('/home/user/config.yaml')
        >>> expand_path("relative/path.txt")
        PosixPath('relative/path.txt')
        >>> expand_path("${HOME}/config.yaml")
        PosixPath('${HOME}/config.yaml')  # NOT expanded
    """
    return Path(path).expanduser()
