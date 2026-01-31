"""Inter-tool calling API for bundled and extension tools.

Provides functions for calling other tools programmatically:
- call_tool(): Call a tool by its full pack.function name
- get_pack(): Get a pack proxy for calling multiple functions

Example usage in an extension tool:

    from ot.tools import call_tool, get_pack

    # Call a single tool by name
    result = call_tool("llm.transform", input=text, prompt="Summarize")

    # Get a pack for multiple calls
    brave = get_pack("brave")
    results = brave.search(query="test")

Note: These functions are only available in bundled and extension tools.
Isolated tools (subprocess with PEP 723) cannot use this API.
"""

from __future__ import annotations

from typing import Any


def call_tool(name: str, **kwargs: Any) -> Any:
    """Call another tool by its full name.

    Args:
        name: Full tool name with pack prefix (e.g., "llm.transform", "brave.search").
              Must contain a dot separator.
        **kwargs: Keyword arguments to pass to the tool function.

    Returns:
        The result from the tool function.

    Raises:
        ValueError: If name doesn't contain a dot separator.
        KeyError: If the pack or function is not found.

    Example:
        result = call_tool("llm.transform", input="Hello", prompt="Translate to Spanish")
    """
    if "." not in name:
        raise ValueError(
            f"Tool name must include pack prefix (e.g., 'pack.function'), got: {name}"
        )

    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    if name not in registry.functions:
        pack_name, func_name = name.rsplit(".", 1)

        if pack_name not in registry.packs:
            available_packs = ", ".join(sorted(registry.packs.keys()))
            raise KeyError(
                f"Pack '{pack_name}' not found. Available packs: {available_packs}"
            )

        pack_funcs = registry.packs[pack_name]
        if hasattr(pack_funcs, "__getattr__"):
            # WorkerPackProxy - list functions differently
            available_funcs = "use get_pack() to discover functions"
        else:
            available_funcs = ", ".join(sorted(pack_funcs.keys()))
        raise KeyError(
            f"Function '{func_name}' not found in pack '{pack_name}'. "
            f"Available: {available_funcs}"
        )

    return registry.functions[name](**kwargs)


def get_pack(name: str) -> Any:
    """Get a pack proxy for calling multiple functions.

    Returns a proxy object that allows calling pack functions using dot notation.

    Args:
        name: Pack name (e.g., "brave", "llm", "file").

    Returns:
        Pack proxy object with tool functions as attributes.

    Raises:
        KeyError: If the pack is not found.

    Example:
        brave = get_pack("brave")
        results = brave.search(query="python")

        llm = get_pack("llm")
        summary = llm.transform(input=text, prompt="Summarize")
    """
    from ot.executor.pack_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    if name not in registry.packs:
        available = ", ".join(sorted(registry.packs.keys()))
        raise KeyError(f"Pack '{name}' not found. Available packs: {available}")

    # Build namespace to get the wrapped proxy with stats tracking
    namespace = build_execution_namespace(registry)

    if name in namespace:
        return namespace[name]

    # Fallback to raw pack (shouldn't happen normally)
    return registry.packs[name]
