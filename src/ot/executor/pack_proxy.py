"""Pack proxy creation for dot notation access.

Creates proxy objects that allow:
- brave.web_search(query="test") - pack access to tool functions
- context7.resolve_library_id() - MCP proxy access
- proxy.list_servers() - introspection of MCP servers

Used by the runner to build the execution namespace.
"""

from __future__ import annotations

import inspect
import warnings
from collections import OrderedDict
from functools import wraps
from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.executor.param_resolver import (
    get_mcp_tool_param_names,
    resolve_kwargs,
)
from ot.stats import timed_tool_call

if TYPE_CHECKING:
    from collections.abc import Callable

    from ot.executor.tool_loader import LoadedTools


def _wrap_with_stats(
    pack_name: str, func_name: str, func: Callable[..., Any]
) -> Callable[..., Any]:
    """Wrap a function to record execution-level stats, track calls, and resolve param prefixes."""
    tool_name = f"{pack_name}.{func_name}"

    try:
        _param_names = tuple(inspect.signature(func).parameters.keys())
    except (ValueError, TypeError):
        _param_names = ()

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if kwargs and _param_names:
            kwargs = resolve_kwargs(kwargs, _param_names)

        with timed_tool_call(tool_name):
            return func(*args, **kwargs)

    return wrapper


def _create_pack_proxy(pack_name: str, pack_funcs: dict[str, Any]) -> Any:
    """Create a pack proxy instance for dot notation access.

    Returns an object that allows pack.func() syntax where func is looked up
    from pack_funcs dict. Each function call is tracked for execution-level stats.
    """

    class PackProxy:
        """Proxy object that provides dot notation access to pack functions."""

        def __init__(self) -> None:
            # Cache wrapped functions to avoid recreating on each access
            self._function_cache: dict[str, Callable[..., Any]] = {}

        def __getattr__(self, name: str) -> Any:
            if name.startswith("_"):
                raise AttributeError(f"Cannot access private attribute '{name}'")

            if name in pack_funcs:
                # Return cached wrapper or create and cache new one
                if name not in self._function_cache:
                    self._function_cache[name] = _wrap_with_stats(
                        pack_name, name, pack_funcs[name]
                    )
                return self._function_cache[name]

            available = ", ".join(sorted(pack_funcs.keys()))
            raise AttributeError(
                f"Function '{name}' not found in pack '{pack_name}'. "
                f"Available: {available}"
            )

    return PackProxy()


def _create_mcp_proxy_pack(server_name: str, tool_prefix: str | None = None) -> Any:
    """Create a pack proxy for an MCP server.

    Allows calling proxied MCP tools using dot notation with automatic aliasing:
    - context7.resolve_library_id(library_name="next.js")
    - github.list_repositories()        # matches list-repositories
    - github.listRepositories()         # also matches list-repositories

    Supports fuzzy matching across naming conventions (snake_case, kebab-case, camelCase, PascalCase).
    Each call is tracked for execution-level stats.

    Args:
        server_name: Name of the MCP server.
        tool_prefix: Optional prefix that the server's tools carry (e.g. "aws_").
            When provided, a second match attempt is made with the prefix prepended,
            so callers can omit it: knowledge.search_documentation() resolves to
            aws_search_documentation.

    Returns:
        Object with __getattr__ that routes to proxy manager.
    """
    from ot.executor.naming import find_canonical_match, suggest_similar_names
    from ot.proxy import get_proxy_manager

    class McpProxyPack:
        """Proxy object that routes tool calls to an MCP server."""

        def __init__(self) -> None:
            # Cache callable proxies to avoid recreating on each access
            self._function_cache: dict[str, Callable[..., Any]] = {}

        def __getattr__(self, accessor_name: str) -> Any:
            if accessor_name.startswith("_"):
                raise AttributeError(f"Cannot access private attribute '{accessor_name}'")

            if accessor_name in self._function_cache:
                return self._function_cache[accessor_name]

            # Resolve accessor to actual tool name using fuzzy matching
            proxy = get_proxy_manager()
            available_tools = [t.name for t in proxy.list_tools(server_name)]

            # Find matching tool via canonical normalization
            try:
                match_result = find_canonical_match(accessor_name, available_tools)
            except ValueError as e:
                # Ambiguous match
                raise AttributeError(str(e)) from None

            if match_result is None and tool_prefix:
                # Server declares a tool_prefix (e.g. "aws_"): try matching with it
                # prepended so callers can omit it.
                match_result = find_canonical_match(
                    f"{tool_prefix}{accessor_name}", available_tools
                )

            if match_result is None:
                # No match found - provide suggestions
                suggestions = suggest_similar_names(accessor_name, available_tools)
                if suggestions:
                    suggestion_list = ", ".join(f"'{s}'" for s in suggestions)
                    raise AttributeError(
                        f"Tool '{accessor_name}' not found in MCP server '{server_name}'. "
                        f"Did you mean: {suggestion_list}? "
                        f"Available tools: {len(available_tools)} total."
                    )
                else:
                    available = ", ".join(f"'{t}'" for t in sorted(available_tools)[:10])
                    more = f" (and {len(available_tools) - 10} more)" if len(available_tools) > 10 else ""
                    raise AttributeError(
                        f"Tool '{accessor_name}' not found in MCP server '{server_name}'. "
                        f"Available: {available}{more}"
                    )

            actual_tool_name = match_result

            def call_proxy_tool(**kwargs: Any) -> str | dict[str, Any] | list[Any]:
                tool_full_name = f"{server_name}.{actual_tool_name}"

                # Resolve abbreviated parameter names (cached lookup)
                if kwargs:
                    param_names = get_mcp_tool_param_names(server_name, actual_tool_name)
                    if param_names:
                        kwargs = resolve_kwargs(kwargs, param_names)

                with timed_tool_call(tool_full_name):
                    timeout = proxy.get_server_timeout(server_name)
                    return proxy.call_tool_sync(server_name, actual_tool_name, kwargs, timeout=timeout)

            self._function_cache[accessor_name] = call_proxy_tool
            return call_proxy_tool

    return McpProxyPack()


def _create_proxy_introspection_pack() -> Any:
    """Create the 'proxy' pack for introspection.

    Provides:
    - proxy.list_servers() - List all configured MCP servers with status
    - proxy.list_tools(server="name") - List tools available on a server

    Returns:
        Object with introspection methods.
    """
    from ot.proxy import get_proxy_manager

    class ProxyIntrospectionPack:
        """Provides introspection methods for proxied MCP servers."""

        def list_servers(self) -> list[dict[str, Any]]:
            """List all configured MCP servers with connection status.

            Returns:
                List of dicts with server name, type, enabled, and connected status.
            """
            config = get_config()
            proxy = get_proxy_manager()

            servers = []
            for name, cfg in (config.servers or {}).items():
                servers.append(
                    {
                        "name": name,
                        "type": cfg.type,
                        "enabled": cfg.enabled,
                        "connected": name in proxy.servers,
                    }
                )
            return servers

        def list_tools(self, server: str) -> list[dict[str, str]]:
            """List tools available on a proxied MCP server.

            Args:
                server: Name of the MCP server.

            Returns:
                List of dicts with tool name and description.

            Raises:
                ValueError: If server is not connected.
            """
            proxy = get_proxy_manager()

            if server not in proxy.servers:
                available = ", ".join(proxy.servers) or "none"
                raise ValueError(
                    f"Server '{server}' not connected. Available: {available}"
                )

            tools = proxy.list_tools(server)
            return [{"name": t.name, "description": t.description} for t in tools]

    return ProxyIntrospectionPack()


# Cache for execution namespace:
# key=(registry_id, connected_proxy_servers, configured_server_fingerprint)
# Uses OrderedDict for proper LRU eviction
_NAMESPACE_CACHE_MAXSIZE = 10
_namespace_cache: OrderedDict[
    tuple[int, frozenset[str], frozenset[tuple[str, str | None]]], dict[str, Any]
] = (
    OrderedDict()
)


def build_execution_namespace(
    registry: LoadedTools,
) -> dict[str, Any]:
    """Build execution namespace with pack proxies for dot notation access.

    Results are cached based on registry identity, connected proxy servers, and
    configured server fingerprints (name + tool_prefix).
    Cache is invalidated when any of those dimensions change.

    Provides dot notation access to tools:
    - brave.web_search(query="test")  # pack access
    - context7.resolve_library_id()   # MCP proxy access

    Args:
        registry: LoadedTools registry with functions and packs

    Returns:
        Dict suitable for use as exec() globals
    """
    from ot.executor.worker_proxy import WorkerPackProxy
    from ot.proxy import get_proxy_manager

    config = get_config()
    configured_servers = config.servers or {}
    configured_server_fingerprint = frozenset(
        (server_name, server_cfg.tool_prefix)
        for server_name, server_cfg in configured_servers.items()
    )

    # Check cache - key is registry identity + current proxy servers + configured servers
    proxy_mgr = get_proxy_manager()
    cache_key = (
        id(registry),
        frozenset(proxy_mgr.servers),
        configured_server_fingerprint,
    )

    if cache_key in _namespace_cache:
        # LRU: move to end on access
        _namespace_cache.move_to_end(cache_key)
        return _namespace_cache[cache_key]

    namespace: dict[str, Any] = {}

    from ot.meta._constants import PACK_SHORT_NAMES

    # Add pack proxies for dot notation
    for pack_name, pack_funcs in registry.packs.items():
        if isinstance(pack_funcs, WorkerPackProxy):
            # Extension tools already have a proxy - use directly
            namespace[pack_name] = pack_funcs
        else:
            namespace[pack_name] = _create_pack_proxy(pack_name, pack_funcs)

    # Inject short-name aliases (e.g. wf → webfetch, wb → whiteboard)
    for full_name, short_name in PACK_SHORT_NAMES.items():
        if full_name in namespace and short_name not in namespace:
            namespace[short_name] = namespace[full_name]

    # Add MCP proxy packs (only if not already defined locally).
    # Include configured servers up-front so packs can be used immediately
    # after ot_servers.enable(...) within the same command block.
    configured_server_names = set(configured_servers.keys())
    known_servers = sorted(set(proxy_mgr.servers) | configured_server_names)

    for server_name in known_servers:
        server_cfg = configured_servers.get(server_name)
        tool_prefix = server_cfg.tool_prefix if server_cfg else None

        # Compute the Python-safe identifier for this server.
        # aws-* servers: strip prefix and normalise hyphens (aws-iam → iam).
        # Other hyphenated servers: replace hyphens with underscores (my-server → my_server).
        if server_name.startswith("aws-"):
            safe_name = server_name[4:].replace("-", "_")
        elif "-" in server_name:
            safe_name = server_name.replace("-", "_")
            warnings.warn(
                f"Server '{server_name}' uses hyphens — rename to '{safe_name}' in servers.yaml. "
                "Hyphen names are not valid Python identifiers.",
                UserWarning,
                stacklevel=2,
            )
        else:
            safe_name = server_name

        # Register under safe name (primary) so agents can call it directly.
        # Keep the original hyphen name as an alias for backward compatibility.
        if safe_name not in namespace:
            namespace[safe_name] = _create_mcp_proxy_pack(server_name, tool_prefix)
        if safe_name != server_name and server_name not in namespace:
            namespace[server_name] = namespace[safe_name]

    # Add proxy introspection pack (always available)
    if "proxy" not in namespace:
        namespace["proxy"] = _create_proxy_introspection_pack()

    # Cache result with LRU eviction
    _namespace_cache[cache_key] = namespace
    while len(_namespace_cache) > _NAMESPACE_CACHE_MAXSIZE:
        _namespace_cache.popitem(last=False)

    return namespace


def reset() -> None:
    """Clear the execution namespace cache.

    Called by ot.reload() to release stale proxy/registry references.
    """
    _namespace_cache.clear()
