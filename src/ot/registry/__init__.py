"""Tool registry package with auto-discovery for user-defined Python tools.

The registry scans the `src/ot_tools/` directory, extracts function signatures and
docstrings using AST parsing, and provides formatted context for LLM code generation.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from docstring_parser import parse as parse_docstring

from .models import ArgInfo, ToolInfo
from .registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Callable
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


def _build_tool_info_from_callable(
    name: str,
    func: Callable[..., Any],
    pack: str | None = None,
) -> ToolInfo:
    """Build ToolInfo from a callable using inspect.

    Args:
        name: Full tool name (e.g., "ot.tools").
        func: The function object.
        pack: Pack name if applicable.

    Returns:
        ToolInfo with extracted signature and docstring info.
    """
    # Get signature
    try:
        sig = inspect.signature(func)
        signature = f"{name}{sig}"
    except (ValueError, TypeError):
        signature = f"{name}(...)"

    # Parse docstring
    doc = func.__doc__ or ""
    parsed = parse_docstring(doc)

    # Build args list
    args: list[ArgInfo] = []
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        # Get type annotation
        if param.annotation != inspect.Parameter.empty:
            param_type = (
                param.annotation.__name__
                if hasattr(param.annotation, "__name__")
                else str(param.annotation)
            )
        else:
            param_type = "Any"

        # Get default value
        default = None
        if param.default != inspect.Parameter.empty:
            default = repr(param.default)

        # Get description from parsed docstring
        description = ""
        for doc_param in parsed.params:
            if doc_param.arg_name == param_name:
                description = doc_param.description or ""
                break

        args.append(
            ArgInfo(
                name=param_name,
                type=param_type,
                default=default,
                description=description,
            )
        )

    # Get return description
    returns = (parsed.returns.description or "") if parsed.returns else ""

    return ToolInfo(
        name=name,
        pack=pack,
        module=func.__module__,
        signature=signature,
        description=parsed.short_description or "",
        args=args,
        returns=returns,
    )


def _register_ot_pack(registry: ToolRegistry) -> None:
    """Register the ot pack tools in the registry.

    The ot pack provides introspection functions that need parameter
    shorthand support like other tools.
    """
    from ot.meta import PACK_NAME, get_ot_pack_functions

    ot_functions = get_ot_pack_functions()

    for func_name, func in ot_functions.items():
        full_name = f"{PACK_NAME}.{func_name}"
        tool_info = _build_tool_info_from_callable(full_name, func, pack=PACK_NAME)
        registry.register_tool(tool_info)


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
        # Register ot pack tools for param shorthand support
        _register_ot_pack(_registry)
    elif rescan:
        # Rescan using config's tool files
        config = get_config()
        tool_files = config.get_tool_files()
        if tool_files:
            _registry.scan_files(tool_files)
        else:
            _registry.scan_directory()
        # Re-register ot pack tools after rescan
        _register_ot_pack(_registry)

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
