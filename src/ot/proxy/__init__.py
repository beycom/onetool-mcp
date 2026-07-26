"""MCP Proxy module for OneTool.

Provides connectivity to external MCP servers that are proxied
through OneTool's single `run` tool interface.
"""

from ot.proxy.manager import (
    ProxyCapabilityUnsupported,
    ProxyManager,
    ProxyToolInfo,
    get_proxy_manager,
    reconnect_proxy_manager,
    reset_proxy_manager,
)

__all__ = [
    "ProxyCapabilityUnsupported",
    "ProxyManager",
    "ProxyToolInfo",
    "get_proxy_manager",
    "reconnect_proxy_manager",
    "reset_proxy_manager",
]
