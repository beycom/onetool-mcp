"""Namespace proxy creation for dot notation access.

Creates proxy objects that allow:
- brave.web_search(query="test") - namespace access to tool functions
- context7.resolve_library_id() - MCP proxy access
- proxy.list_servers() - introspection of MCP servers

Used by the runner to build the execution namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ot.executor.tool_loader import LoadedTools


def _create_namespace_proxy(ns_name: str, ns_funcs: dict[str, Any]) -> Any:
    """Create a namespace proxy instance for dot notation access.

    Returns an object that allows ns.func() syntax where func is looked up
    from ns_funcs dict.
    """

    class NamespaceProxy:
        """Proxy object that provides dot notation access to namespaced functions."""

        def __getattr__(self, name: str) -> Any:
            if name in ns_funcs:
                return ns_funcs[name]
            available = ", ".join(sorted(ns_funcs.keys()))
            raise AttributeError(
                f"Function '{name}' not found in namespace '{ns_name}'. "
                f"Available: {available}"
            )

    return NamespaceProxy()


def _create_mcp_proxy_namespace(server_name: str) -> Any:
    """Create a namespace proxy for an MCP server.

    Allows calling proxied MCP tools using dot notation:
    - context7.resolve_library_id(library_name="next.js")

    Args:
        server_name: Name of the MCP server.

    Returns:
        Object with __getattr__ that routes to proxy manager.
    """
    from ot.proxy import get_proxy_manager

    class McpProxyNamespace:
        """Proxy object that routes tool calls to an MCP server."""

        def __getattr__(self, tool_name: str) -> Any:
            def call_proxy_tool(**kwargs: Any) -> str:
                proxy = get_proxy_manager()
                return proxy.call_tool_sync(server_name, tool_name, kwargs)

            return call_proxy_tool

    return McpProxyNamespace()


def _create_proxy_introspection_namespace() -> Any:
    """Create the 'proxy' namespace for introspection.

    Provides:
    - proxy.list_servers() - List all configured MCP servers with status
    - proxy.list_tools(server="name") - List tools available on a server

    Returns:
        Object with introspection methods.
    """
    from ot.proxy import get_proxy_manager

    class ProxyIntrospectionNamespace:
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

    return ProxyIntrospectionNamespace()


def build_execution_namespace(
    registry: LoadedTools,
) -> dict[str, Any]:
    """Build execution namespace with namespace proxies for dot notation access.

    Provides dot notation access to tools:
    - brave.web_search(query="test")  # namespace access
    - context7.resolve_library_id()   # MCP proxy access

    Args:
        registry: LoadedTools registry with functions and namespaces

    Returns:
        Dict suitable for use as exec() globals
    """
    from ot.executor.worker_proxy import WorkerNamespaceProxy
    from ot.proxy import get_proxy_manager

    namespace: dict[str, Any] = {}

    # Add namespace proxies for dot notation
    for ns_name, ns_funcs in registry.namespaces.items():
        if isinstance(ns_funcs, WorkerNamespaceProxy):
            # Worker tools already have a proxy - use directly
            namespace[ns_name] = ns_funcs
        else:
            namespace[ns_name] = _create_namespace_proxy(ns_name, ns_funcs)

    # Add MCP proxy namespaces (only if not already defined locally)
    proxy_mgr = get_proxy_manager()
    for server_name in proxy_mgr.servers:
        if server_name not in namespace:
            namespace[server_name] = _create_mcp_proxy_namespace(server_name)

    # Add proxy introspection namespace (always available)
    if "proxy" not in namespace:
        namespace["proxy"] = _create_proxy_introspection_namespace()

    return namespace
