"""OneTool - MCP server with single 'run' tool for LLM code generation.

Features:
- Single 'run' tool for Python code execution
- Tool discovery from src/ot_tools/ directory
- Configurable prompts and instructions
- Namespaces, aliases, and snippets for shortcuts

Usage:
    # Start MCP server (stdio transport)
    ot-serve

    # With config
    ot-serve --config config/ot-serve.yaml

    # Run benchmarks
    ot-bench run harness.yaml
"""

from importlib.metadata import version
from typing import Any

__version__ = version("onetool-mcp")

__all__ = ["__version__", "main"]


def __getattr__(name: str) -> Any:
    """Lazy import for server module to avoid loading config at import time."""
    if name == "main":
        from ot.server import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
