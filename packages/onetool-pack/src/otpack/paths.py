"""Path resolution utilities for OneTool packs.

Provides standalone path helpers that work with or without onetool installed.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "expand_path",
    "get_effective_cwd",
    "get_project_artifact_dir",
    "get_project_state_dir",
    "resolve_cwd_path",
]


def _validate_relative_fragment(value: str, *, label: str) -> Path:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(
            f"{label} must be a non-empty relative path fragment: {value!r}"
        )
    return path


def get_effective_cwd() -> Path:
    """Get the effective working directory.

    Returns OT_CWD if set, else Path.cwd(). This provides a single point
    of control for working directory resolution across all CLIs.

    Returns:
        Resolved Path for working directory
    """
    env_cwd = os.getenv("OT_CWD")
    if env_cwd:
        return Path(env_cwd).resolve()
    return Path.cwd()


def expand_path(path: str) -> Path:
    """Expand ~ in a path.

    Only expands ~ to home directory. Does NOT expand ${VAR} patterns.

    Args:
        path: Path string potentially containing ~

    Returns:
        Expanded absolute Path
    """
    return Path(path).expanduser().resolve()


def resolve_cwd_path(path: str) -> Path:
    """Resolve a path relative to the project working directory (OT_CWD).

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path

    Behaviour:
        - ~ paths: expanded to home directory
        - Absolute paths: returned unchanged
        - Relative paths: resolved relative to get_effective_cwd()
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (get_effective_cwd() / p).resolve()


def get_project_state_dir(pack: str) -> Path:
    """Return a project-local pack state directory under CWD/.onetool/state/."""
    return (
        get_effective_cwd()
        / ".onetool"
        / "state"
        / _validate_relative_fragment(pack, label="pack")
    )


def get_project_artifact_dir(kind: str) -> Path:
    """Return a generated artifact directory under the effective project CWD."""
    return get_effective_cwd() / _validate_relative_fragment(
        kind, label="artifact kind"
    )
