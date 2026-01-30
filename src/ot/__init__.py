"""OneTool - MCP server with single 'run' tool for LLM code generation.

Features:
- Single 'run' tool for Python code execution
- Tool discovery from src/ot_tools/ directory
- Configurable prompts and instructions
- Namespaces, aliases, and snippets for shortcuts

Usage:
    # Start MCP server (stdio transport)
    onetool

    # With config
    onetool --config config/onetool.yaml

    # Run benchmarks
    bench run harness.yaml
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:
    __version__ = version("onetool-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"  # Running from source or in worker subprocess

__all__ = ["__version__", "main"]


def __getattr__(name: str) -> Any:
    """Lazy import for server module to avoid loading config at import time."""
    if name == "main":
        from ot.server import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
