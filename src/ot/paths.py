"""Path resolution for OneTool global and project directories.

OneTool uses a two-tier directory structure:
- Global: ~/.onetool/ — user-wide settings, secrets
- Project: .onetool/ — project-specific config

Directories are created lazily on first use, not on install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Directory names
GLOBAL_DIR_NAME = ".onetool"
PROJECT_DIR_NAME = ".onetool"


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


def get_global_dir() -> Path:
    """Get the global OneTool directory path.

    Returns:
        Path to ~/.onetool/ (not necessarily existing)
    """
    return Path.home() / GLOBAL_DIR_NAME


def get_project_dir(start: Path | None = None) -> Path | None:
    """Get the project OneTool directory.

    Returns cwd/.onetool if it exists, else None. No tree-walking.
    Uses get_effective_cwd() if start is not provided.

    Args:
        start: Starting directory (default: get_effective_cwd())

    Returns:
        Path to .onetool/ if found, None otherwise
    """
    cwd = start or get_effective_cwd()
    candidate = cwd / PROJECT_DIR_NAME
    if candidate.is_dir():
        return candidate
    return None


def ensure_global_dir(quiet: bool = False) -> Path:
    """Ensure the global OneTool directory exists.

    Creates ~/.onetool/ and copies default config files from resources/config/.
    Prints creation message to stderr (since MCP uses stdout).

    Args:
        quiet: Suppress creation messages

    Returns:
        Path to ~/.onetool/
    """
    import shutil

    global_dir = get_global_dir()

    if global_dir.exists():
        return global_dir

    # Create directory structure
    global_dir.mkdir(parents=True, exist_ok=True)

    # Copy default config files from resources/config/
    resources_config_dir = Path(__file__).parent.parent.parent / "resources" / "config"
    copied_configs: list[str] = []
    if resources_config_dir.exists():
        for config_file in resources_config_dir.glob("*.yaml"):
            dest = global_dir / config_file.name
            if not dest.exists():
                shutil.copy(config_file, dest)
                copied_configs.append(config_file.name)

    if not quiet:
        # Use stderr to avoid interfering with MCP stdout
        print(f"Creating {global_dir}/", file=sys.stderr)
        for config_name in copied_configs:
            print(f"  ✓ {config_name}", file=sys.stderr)

    return global_dir


def ensure_project_dir(path: Path | None = None, quiet: bool = False) -> Path:
    """Ensure the project OneTool directory exists.

    Creates .onetool/ in the specified directory or effective cwd.

    Args:
        path: Project root (default: get_effective_cwd())
        quiet: Suppress creation messages

    Returns:
        Path to .onetool/
    """
    project_root = path or get_effective_cwd()
    project_dir = project_root / PROJECT_DIR_NAME

    if project_dir.exists():
        return project_dir

    # Create directory structure
    project_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"Creating {project_dir.relative_to(project_root)}/", file=sys.stderr)

    return project_dir


def get_config_path(cli_name: str, scope: str = "any") -> Path | None:
    """Get the config file path for a CLI.

    Resolution order for scope="any":
    1. cwd/.onetool/<cli>.yaml (project-specific)
    2. ~/.onetool/<cli>.yaml (global)

    Args:
        cli_name: CLI name (e.g., "ot-serve", "ot-bench")
        scope: "global", "project", or "any" (project first, then global)

    Returns:
        Path to config file if found, None otherwise
    """
    config_name = f"{cli_name}.yaml"

    if scope == "project" or scope == "any":
        cwd = get_effective_cwd()
        project_config = cwd / PROJECT_DIR_NAME / config_name
        if project_config.exists():
            return project_config

    if scope == "global" or scope == "any":
        global_dir = get_global_dir()
        global_config = global_dir / config_name
        if global_config.exists():
            return global_config

    return None


def expand_path(path: str) -> Path:
    """Expand ~ in a path.

    Only expands ~ to home directory. Does NOT expand ${VAR} patterns.
    Use ~/path instead of ${HOME}/path.

    Args:
        path: Path string potentially containing ~

    Returns:
        Expanded absolute Path
    """
    return Path(path).expanduser().resolve()
