"""Platform detection utilities for cross-platform support."""

from __future__ import annotations

import sys

# Platform-specific install commands for external dependencies
INSTALL_COMMANDS: dict[str, dict[str, str]] = {
    "rg": {
        "darwin": "brew install ripgrep",
        "linux": "apt install ripgrep  # or: snap install ripgrep",
        "win32": "winget install BurntSushi.ripgrep.MSVC  # or: scoop install ripgrep",
    },
    "playwright": {
        "darwin": "pip install playwright && playwright install",
        "linux": "pip install playwright && playwright install",
        "win32": "pip install playwright && playwright install",
    },
}


def get_install_hint(tool: str) -> str:
    """Get platform-appropriate install command for a tool.

    Args:
        tool: Tool name (e.g., "rg", "playwright")

    Returns:
        Install command for the current platform, or generic message if unknown.

    Example:
        >>> get_install_hint("rg")  # On macOS
        'brew install ripgrep'
        >>> get_install_hint("rg")  # On Linux
        'apt install ripgrep  # or: snap install ripgrep'
        >>> get_install_hint("rg")  # On Windows
        'winget install BurntSushi.ripgrep.MSVC  # or: scoop install ripgrep'
    """
    platform = sys.platform
    # Normalize Linux variants (linux2, etc.)
    if platform.startswith("linux"):
        platform = "linux"

    commands = INSTALL_COMMANDS.get(tool, {})
    return commands.get(platform, f"Install {tool} for your platform")
