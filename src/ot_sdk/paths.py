"""Path resolution utilities for worker tools.

Provides functions for resolving paths relative to project or config directories.
Path context is passed to workers via the JSON-RPC request config.

Two path contexts are available:

- **Project paths** (`get_project_path`): For reading/writing project files.
  Resolves relative to `OT_CWD` (the user's project directory).

- **Config paths** (`get_config_path`): For loading config assets like templates.
  Resolves relative to the config directory (`.onetool/`).

Example:
    from ot_sdk import get_project_path, get_config_path

    # Save output to project directory
    output = get_project_path("diagrams/flow.svg")

    # Load template from config directory
    template = get_config_path("templates/default.mmd")
"""

from __future__ import annotations

from pathlib import Path

from ot_sdk.config import _current_config


def get_project_path(path: str) -> Path:
    """Resolve a path relative to the project working directory.

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
