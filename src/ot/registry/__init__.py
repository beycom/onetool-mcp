"""Tool registry package with auto-discovery for user-defined Python tools.

The registry scans the `src/ot_tools/` directory, extracts function signatures and
docstrings using AST parsing, and provides formatted context for LLM code generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import ArgInfo, ToolInfo
from .registry import ToolRegistry

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "ArgInfo",
    "ToolInfo",
    "ToolRegistry",
    "describe_tool",
    "get_registry",
    "list_tools",
]

# Global registry instance
_registry: ToolRegistry | None = None


def get_registry(tools_path: Path | None = None, rescan: bool = False) -> ToolRegistry:
    """Get or create the global tool registry.

    Uses config's tools_dir glob patterns if available, otherwise falls back
    to the provided tools_path or default 'src/ot_tools/' directory.

    Args:
        tools_path: Path to tools directory (fallback if no config).
        rescan: If True, rescan even if registry exists.

    Returns:
        ToolRegistry instance with discovered tools.
    """
    from ot.config.loader import get_config

    global _registry

    if _registry is None:
        _registry = ToolRegistry(tools_path)
        # Use config's tool files if available
        config = get_config()
        tool_files = config.get_tool_files()
        if tool_files:
            _registry.scan_files(tool_files)
        else:
            _registry.scan_directory()
    elif rescan:
        # Rescan using config's tool files
        config = get_config()
        tool_files = config.get_tool_files()
        if tool_files:
            _registry.scan_files(tool_files)
        else:
            _registry.scan_directory()

    return _registry


def list_tools() -> str:
    """List all registered tools.

    Returns:
        Summary of all registered tools.
    """
    registry = get_registry(rescan=True)
    return registry.format_summary()


def describe_tool(name: str) -> str:
    """Describe a specific tool.

    Args:
        name: Tool function name.

    Returns:
        Detailed tool description.
    """
    registry = get_registry()
    return registry.describe_tool(name)
