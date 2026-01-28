"""Parameter name prefix matching for tool calls.

Resolves abbreviated parameter names to full parameter names using prefix matching.
For example: q= -> query=, c= -> count=
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=256)
def get_tool_param_names(tool_name: str) -> tuple[str, ...]:
    """Get parameter names for a tool from the registry (cached).

    Args:
        tool_name: Full tool name (e.g., "brave.web_search").

    Returns:
        Tuple of parameter names in signature order, or empty tuple if not found.
    """
    from ot.registry import get_registry

    registry = get_registry()
    tool_info = registry.get_tool(tool_name)
    if tool_info:
        return tuple(arg.name for arg in tool_info.args)
    return ()


# Cache for MCP tool param names: (server_name, tool_name) -> param_names
_mcp_param_cache: dict[tuple[str, str], tuple[str, ...]] = {}


def get_mcp_tool_param_names(server_name: str, tool_name: str) -> tuple[str, ...]:
    """Get parameter names for an MCP tool from its input schema (cached).

    Args:
        server_name: Name of the MCP server.
        tool_name: Name of the tool.

    Returns:
        Tuple of parameter names, or empty tuple if not found.
    """
    cache_key = (server_name, tool_name)
    if cache_key in _mcp_param_cache:
        return _mcp_param_cache[cache_key]

    from ot.proxy import get_proxy_manager

    proxy = get_proxy_manager()
    tools = proxy.list_tools(server_name)
    for tool in tools:
        if tool.name == tool_name:
            result = tuple(get_param_names_from_schema(tool.input_schema))
            _mcp_param_cache[cache_key] = result
            return result

    _mcp_param_cache[cache_key] = ()
    return ()


def resolve_kwargs(kwargs: dict[str, object], param_names: list[str]) -> dict[str, object]:
    """Resolve abbreviated parameter names to full parameter names.

    Matching rules:
    1. Exact match wins - if param name matches exactly, use it
    2. Prefix match - find all params that start with the abbreviated name
    3. First match wins - if multiple params match, use first in param_names order

    Args:
        kwargs: Dictionary of parameter names to values.
        param_names: List of valid parameter names in signature order.

    Returns:
        New dictionary with resolved parameter names.

    Examples:
        >>> resolve_kwargs({"q": "test"}, ["query", "count"])
        {"query": "test"}

        >>> resolve_kwargs({"query": "test"}, ["query", "count"])
        {"query": "test"}  # exact match

        >>> resolve_kwargs({"q": "x"}, ["query_info", "query", "quality"])
        {"query_info": "x"}  # first prefix match

        >>> resolve_kwargs({"xyz": "test"}, ["query"])
        {"xyz": "test"}  # no match, passthrough
    """
    if not kwargs or not param_names:
        return kwargs

    param_set = set(param_names)
    resolved: dict[str, object] = {}

    for key, value in kwargs.items():
        # Exact match - use as-is
        if key in param_set:
            resolved[key] = value
            continue

        # Find prefix matches (preserve signature order)
        matches = [p for p in param_names if p.startswith(key)]

        if len(matches) == 1:
            # Single match - use it
            resolved[matches[0]] = value
        elif len(matches) > 1:
            # Multiple matches - use first in signature order
            resolved[matches[0]] = value
        else:
            # No match - passthrough (let function raise its own error)
            resolved[key] = value

    return resolved


def get_param_names_from_schema(input_schema: dict[str, object]) -> list[str]:
    """Extract parameter names from a JSON schema.

    Args:
        input_schema: JSON schema dict with "properties" key.

    Returns:
        List of parameter names in schema order.
    """
    properties = input_schema.get("properties", {})
    if isinstance(properties, dict):
        return list(properties.keys())
    return []
