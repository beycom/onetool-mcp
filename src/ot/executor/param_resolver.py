"""Parameter name prefix matching for tool calls.

Resolves abbreviated parameter names to full parameter names using prefix matching.
For example: q= -> query=, c= -> count=
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
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
# Uses OrderedDict for LRU eviction with bounded size
_MCP_PARAM_CACHE_MAXSIZE = 256
_mcp_param_cache: OrderedDict[tuple[str, str], tuple[str, ...]] = OrderedDict()


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
        _mcp_param_cache.move_to_end(cache_key)
        return _mcp_param_cache[cache_key]

    from ot.proxy import get_proxy_manager

    proxy = get_proxy_manager()
    tools = proxy.list_tools(server_name)
    result: tuple[str, ...] = ()
    for tool in tools:
        if tool.name == tool_name:
            result = tuple(get_param_names_from_schema(tool.input_schema))
            break

    _mcp_param_cache[cache_key] = result
    while len(_mcp_param_cache) > _MCP_PARAM_CACHE_MAXSIZE:
        _mcp_param_cache.popitem(last=False)
    return result


def evict_mcp_param_cache(server_name: str | None = None) -> None:
    """Evict cached MCP tool param names (D14).

    Called on server disconnect/restart so a subsequent call resolves parameters
    against the server's *current* schema rather than a stale pre-restart one.

    Args:
        server_name: Server whose entries to drop. ``None`` clears every entry
            (used on a full reconnect where any server's schema may have changed).
    """
    if server_name is None:
        _mcp_param_cache.clear()
        return
    for key in [k for k in _mcp_param_cache if k[0] == server_name]:
        _mcp_param_cache.pop(key, None)


def resolve_kwargs(
    kwargs: dict[str, object], param_names: Sequence[str]
) -> dict[str, object]:
    """Resolve abbreviated parameter names to full parameter names.

    Matching rules:
    1. Exact match wins - if param name matches exactly, use it
    2. Prefix match - find all params that start with the abbreviated name
    3. First match wins - if a *single* provided key prefix-matches multiple
       different params, use the first in param_names order
    4. Collision refusal (D4) - if two *different* provided keys would resolve to
       the *same* target parameter, raise ValueError instead of silently letting
       dict-iteration order pick a winner and discard the other value.

    Args:
        kwargs: Dictionary of parameter names to values.
        param_names: Sequence of valid parameter names in signature order.

    Returns:
        New dictionary with resolved parameter names.

    Raises:
        ValueError: If two provided keys collide on one target parameter.

    Examples:
        >>> resolve_kwargs({"q": "test"}, ["query", "count"])
        {"query": "test"}

        >>> resolve_kwargs({"query": "test"}, ["query", "count"])
        {"query": "test"}  # exact match

        >>> resolve_kwargs({"q": "x"}, ["query_info", "query", "quality"])
        {"query_info": "x"}  # first prefix match

        >>> resolve_kwargs({"xyz": "test"}, ["query"])
        {"xyz": "test"}  # no match, passthrough

        >>> resolve_kwargs({"query": "real", "q": "typo"}, ["query", "count"])
        Traceback (most recent call last):
        ValueError: ...  # 'query' and 'q' both target 'query'
    """
    if not kwargs or not param_names:
        return kwargs

    param_set = set(param_names)
    resolved: dict[str, object] = {}
    # target parameter name -> the provided key that first claimed it
    claimed_by: dict[str, str] = {}

    def _claim(target: str, key: str, value: object) -> None:
        prev = claimed_by.get(target)
        if prev is not None and prev != key:
            raise ValueError(
                f"Ambiguous parameters: both '{prev}' and '{key}' resolve to "
                f"parameter '{target}'. Provide only one."
            )
        claimed_by[target] = key
        resolved[target] = value

    for key, value in kwargs.items():
        # Exact match - use as-is
        if key in param_set:
            _claim(key, key, value)
            continue

        # Find prefix matches (preserve signature order)
        matches = [p for p in param_names if p.startswith(key)]

        if matches:
            # Single match: only option, first (and only) in signature order wins.
            # Multiple matches: prefer a target that isn't already claimed by
            # another key and isn't itself an exact key elsewhere in kwargs
            # (that key will claim it exactly), so we don't fabricate an
            # ambiguity collision with an unrelated provided key. Fall back to
            # the first match in signature order if every candidate is taken —
            # that case is a genuine ambiguity and _claim will raise.
            target = next(
                (m for m in matches if m not in claimed_by and m not in kwargs),
                matches[0],
            )
            _claim(target, key, value)
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
