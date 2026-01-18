"""MCP Proxy module for OneTool.

Provides connectivity to external MCP servers that are proxied
through OneTool's single `run` tool interface.
"""

from ot.proxy.manager import (
    ProxyManager,
    ProxyToolInfo,
    get_proxy_manager,
    reset_proxy_manager,
)

__all__ = [
    "ProxyManager",
    "ProxyToolInfo",
    "get_proxy_manager",
    "reset_proxy_manager",
]
