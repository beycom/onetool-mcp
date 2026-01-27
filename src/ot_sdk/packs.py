"""Inter-tool communication utilities for OneTool SDK.

Provides functions for tools to call other packs without requiring
direct registry access.

Example:
    from ot_sdk import get_pack, call_tool

    # Get a pack and call functions directly
    brave = get_pack("brave")
    results = brave.search(query="python async")

    # Or call a tool directly by name
    results = call_tool("brave.search", query="python async")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def get_pack(name: str) -> Any:
    """Get a pack by name for calling its functions.

    Returns a pack object that supports attribute-style function calls.
    Works with both local packs and proxy packs.

    Args:
        name: Pack name (e.g., "brave", "web", "firecrawl")

    Returns:
        Pack object with callable functions as attributes

    Raises:
        ValueError: If pack is not found

    Example:
        brave = get_pack("brave")
        results = brave.search(query="python async")

        web = get_pack("web")
        content = web.fetch(url="https://example.com")
    """
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerPackProxy
    from ot.proxy import get_proxy_manager

    registry = load_tool_registry()
    proxy = get_proxy_manager()

    # Check local packs first
    if name in registry.packs:
        pack_funcs = registry.packs[name]
        if isinstance(pack_funcs, WorkerPackProxy):
            return pack_funcs
        # For dict-style packs, wrap in a simple object
        return _PackWrapper(pack_funcs)

    # Check proxy servers
    if name in proxy.servers:
        return _ProxyPackWrapper(name, proxy)

    # Not found
    local_packs = set(registry.packs.keys())
    proxy_packs = set(proxy.servers)
    all_packs = sorted(local_packs | proxy_packs)
    raise ValueError(f"Pack '{name}' not found. Available: {', '.join(all_packs)}")


def call_tool(name: str, **kwargs: Any) -> Any:
    """Call a tool by its full name.

    Convenience function for one-off tool calls without getting the pack first.

    Args:
        name: Full tool name in pack.function format (e.g., "brave.search")
        **kwargs: Keyword arguments to pass to the tool

    Returns:
        Tool result

    Raises:
        ValueError: If name format is invalid or tool not found

    Example:
        results = call_tool("brave.search", query="python async")
        content = call_tool("web.fetch", url="https://example.com")
    """
    if "." not in name:
        raise ValueError(
            f"Tool name must be in pack.function format (e.g., brave.search). Got: {name}"
        )

    pack_name, func_name = name.rsplit(".", 1)
    pack = get_pack(pack_name)
    func = getattr(pack, func_name, None)

    if func is None:
        raise ValueError(f"Function '{func_name}' not found in pack '{pack_name}'")

    return func(**kwargs)


class _PackWrapper:
    """Wrapper for dict-style packs to support attribute access."""

    def __init__(self, funcs: dict[str, Any]) -> None:
        self._funcs = funcs

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._funcs:
            raise AttributeError(
                f"Pack has no function '{name}'. Available: {', '.join(self._funcs.keys())}"
            )
        return self._funcs[name]

    def __dir__(self) -> list[str]:
        return list(self._funcs.keys())


class _ProxyPackWrapper:
    """Wrapper for proxy packs to support attribute access."""

    def __init__(self, server: str, proxy: Any) -> None:
        self._server = server
        self._proxy = proxy

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        # Get the tool from the proxy
        tools = self._proxy.list_tools(server=self._server)
        tool_names = {t.name for t in tools}

        if name not in tool_names:
            raise AttributeError(
                f"Proxy pack '{self._server}' has no function '{name}'. "
                f"Available: {', '.join(sorted(tool_names))}"
            )

        # Return a callable that invokes the proxy tool
        def call_proxy(**kwargs: Any) -> Any:
            return self._proxy.call_tool(self._server, name, kwargs)

        return call_proxy

    def __dir__(self) -> list[str]:
        tools = self._proxy.list_tools(server=self._server)
        return [t.name for t in tools]
