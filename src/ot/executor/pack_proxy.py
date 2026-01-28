"""Pack proxy creation for dot notation access.

Creates proxy objects that allow:
- brave.web_search(query="test") - pack access to tool functions
- context7.resolve_library_id() - MCP proxy access
- proxy.list_servers() - introspection of MCP servers

Used by the runner to build the execution namespace.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from ot.stats import timed_tool_call

if TYPE_CHECKING:
    from collections.abc import Callable

    from ot.executor.tool_loader import LoadedTools


def _wrap_with_stats(
    pack_name: str, func_name: str, func: Callable[..., Any]
) -> Callable[..., Any]:
    """Wrap a function to record execution-level stats."""
    tool_name = f"{pack_name}.{func_name}"

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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

        def __getattr__(self, name: str) -> Any:
            if name in pack_funcs:
                # Wrap function with stats tracking
                return _wrap_with_stats(pack_name, name, pack_funcs[name])
            available = ", ".join(sorted(pack_funcs.keys()))
            raise AttributeError(
                f"Function '{name}' not found in pack '{pack_name}'. "
                f"Available: {available}"
            )

    return PackProxy()


def _create_mcp_proxy_pack(server_name: str) -> Any:
    """Create a pack proxy for an MCP server.

    Allows calling proxied MCP tools using dot notation:
    - context7.resolve_library_id(library_name="next.js")

    Each call is tracked for execution-level stats.

    Args:
        server_name: Name of the MCP server.

    Returns:
        Object with __getattr__ that routes to proxy manager.
    """
    from ot.proxy import get_proxy_manager

    class McpProxyPack:
        """Proxy object that routes tool calls to an MCP server."""

        def __getattr__(self, tool_name: str) -> Any:
            def call_proxy_tool(**kwargs: Any) -> str:
                tool_full_name = f"{server_name}.{tool_name}"
                with timed_tool_call(tool_full_name):
                    proxy = get_proxy_manager()
                    return proxy.call_tool_sync(server_name, tool_name, kwargs)

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
            from ot.config import get_config

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


# Cache for execution namespace: key=(registry_id, frozenset of proxy servers)
_namespace_cache: dict[tuple[int, frozenset[str]], dict[str, Any]] = {}


def build_execution_namespace(
    registry: LoadedTools,
) -> dict[str, Any]:
    """Build execution namespace with pack proxies for dot notation access.

    Results are cached based on registry identity and proxy server configuration.
    Cache is invalidated when registry changes or proxy servers are added/removed.

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

    # Check cache - key is registry identity + current proxy servers
    proxy_mgr = get_proxy_manager()
    cache_key = (id(registry), frozenset(proxy_mgr.servers))

    if cache_key in _namespace_cache:
        return _namespace_cache[cache_key]

    namespace: dict[str, Any] = {}

    # Add pack proxies for dot notation
    for pack_name, pack_funcs in registry.packs.items():
        if isinstance(pack_funcs, WorkerPackProxy):
            # Extension tools already have a proxy - use directly
            namespace[pack_name] = pack_funcs
        else:
            namespace[pack_name] = _create_pack_proxy(pack_name, pack_funcs)

    # Add MCP proxy packs (only if not already defined locally)
    for server_name in proxy_mgr.servers:
        if server_name not in namespace:
            namespace[server_name] = _create_mcp_proxy_pack(server_name)

    # Add proxy introspection pack (always available)
    if "proxy" not in namespace:
        namespace["proxy"] = _create_proxy_introspection_pack()

    # Cache result (simple LRU: keep last 10)
    if len(_namespace_cache) >= 10:
        # Remove oldest entry
        oldest_key = next(iter(_namespace_cache))
        del _namespace_cache[oldest_key]

    _namespace_cache[cache_key] = namespace
    return namespace
