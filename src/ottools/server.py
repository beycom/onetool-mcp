"""Runtime server management for OneTool proxy servers.

Provides list/status (read-only) plus enable/disable/restart helpers used by
other surfaces.

Enable/disable are in-memory only — state resets on server restart. Restart
re-reads the named server's entry from config on disk so "edit servers.yaml,
then restart" applies the new settings.
"""

from __future__ import annotations

import threading
from typing import Any

from ot.config.loader import (
    get_config,
    get_loaded_config_path,
    get_loaded_secrets_path,
    load_config,
)
from ot.logging import LogSpan
from ot.proxy import get_proxy_manager

__all__ = ["disable", "enable", "restart", "server", "status"]

_SERVER_MUTATION_LOCK = threading.RLock()


def _get_server_info(server_name: str) -> dict[str, Any]:
    """Get connection info for a named server."""
    proxy = get_proxy_manager()
    conn = proxy.get_connection(server_name)
    connected = conn is not None
    tool_count = len(proxy.list_tools(server=server_name)) if connected else 0

    return {
        "name": server_name,
        "connected": connected,
        "tool_count": tool_count,
    }


def _format_server_row(
    name: str, enabled: bool, connected: bool, tool_count: int
) -> str:
    status_str = "connected" if connected else "disconnected"
    enabled_str = "enabled" if enabled else "disabled"
    tool_str = f" ({tool_count} tools)" if connected else ""
    return f"  {name}: {enabled_str}, {status_str}{tool_str}"


def _unknown_error(name: str, configured: dict[str, Any]) -> str:
    available = ", ".join(sorted(configured.keys()))
    return f"Error: Unknown server '{name}'. Configured servers: {available}"


def _get_env() -> tuple[dict[str, Any], Any]:
    cfg = get_config()
    if not cfg.servers:
        raise ValueError("No servers configured. Add servers to servers.yaml.")
    return cfg.servers, get_proxy_manager()


def _read_server_from_disk(name: str) -> tuple[bool, Any]:
    """Re-read the named server's entry from config on disk.

    Returns (reloaded, entry): reloaded is False when no config path is known
    (fall back to the cached entry); entry is None when the server no longer
    exists on disk. The global config singleton is not replaced — the caller
    swaps the single entry into the shared servers dict.

    Raises:
        FileNotFoundError, ValueError: If the config file is missing or invalid.
    """
    config_path = get_loaded_config_path()
    if config_path is None:
        return False, None
    fresh = load_config(config_path, secrets_path=get_loaded_secrets_path())
    return True, (fresh.servers or {}).get(name)


def server(*, status: str | None = None) -> str:
    """Read-only server view for the ot pack.

    Without arguments, list all configured servers and status.
    With status=, show details for a named server.

    Args:
        status: Show detailed status for a named server

    Returns:
        Status report
    """
    with LogSpan(span="server.view", status=status) as s:
        try:
            configured, proxy = _get_env()
        except ValueError as e:
            return str(e)

        if status is None:
            lines = [f"Servers ({len(configured)} configured):"]
            for srv_name in sorted(configured.keys()):
                srv_cfg = configured[srv_name]
                info = _get_server_info(srv_name)
                lines.append(
                    _format_server_row(
                        srv_name, srv_cfg.enabled, info["connected"], info["tool_count"]
                    )
                )
            s.add(count=len(configured))
            return "\n".join(lines)

        if status not in configured:
            return _unknown_error(status, configured)

        srv_cfg = configured[status]
        info = _get_server_info(status)
        connected_str = "connected" if info["connected"] else "disconnected"
        enabled_str = "enabled" if srv_cfg.enabled else "disabled"
        lines = [
            f"Server: {status}",
            f"  State: {enabled_str}, {connected_str}",
        ]
        if info["connected"]:
            lines.append(f"  Tools: {info['tool_count']}")
        if err := proxy.get_error(status):
            lines.append(f"  Last error: {err}")
        s.add(server=status, connected=info["connected"])
        return "\n".join(lines)


def status(*, name: str) -> str:
    """Show detailed status for a named server."""
    return server(status=name)


def enable(*, name: str) -> str:
    """Enable a disabled server and connect it."""
    with LogSpan(span="server.enable", name=name) as s, _SERVER_MUTATION_LOCK:
        try:
            configured, proxy = _get_env()
        except ValueError as e:
            return str(e)

        if name not in configured:
            return _unknown_error(name, configured)

        srv_cfg = configured[name]
        if srv_cfg.enabled:
            info = _get_server_info(name)
            if info["connected"]:
                s.add(noop=True, connected=True)
                return (
                    f"Server '{name}' is already enabled and connected "
                    f"({info['tool_count']} tools)."
                )

        srv_cfg.enabled = True
        proxy.connect_additional_sync(name, srv_cfg)
        info = _get_server_info(name)
        connected_str = "connected" if info["connected"] else "connection failed"
        tool_str = f" ({info['tool_count']} tools)" if info["connected"] else ""
        s.add(connected=info["connected"])
        return f"Server '{name}' enabled — {connected_str}{tool_str}."


def disable(*, name: str) -> str:
    """Disable an enabled server and disconnect it."""
    with LogSpan(span="server.disable", name=name) as s, _SERVER_MUTATION_LOCK:
        try:
            configured, proxy = _get_env()
        except ValueError as e:
            return str(e)

        if name not in configured:
            return _unknown_error(name, configured)

        srv_cfg = configured[name]
        if not srv_cfg.enabled:
            s.add(noop=True)
            return f"Server '{name}' is already disabled."

        srv_cfg.enabled = False
        proxy.disconnect_server_sync(name)
        return f"Server '{name}' disabled."


def restart(*, name: str) -> str:
    """Disconnect and reconnect a server with its current on-disk config."""
    with LogSpan(span="server.restart", name=name) as s, _SERVER_MUTATION_LOCK:
        try:
            configured, proxy = _get_env()
        except ValueError as e:
            return str(e)

        if name not in configured:
            return _unknown_error(name, configured)

        try:
            reloaded, fresh_cfg = _read_server_from_disk(name)
        except (FileNotFoundError, ValueError) as e:
            return f"Error: could not re-read config for restart: {e}"

        if reloaded:
            if fresh_cfg is None:
                return (
                    f"Error: server '{name}' no longer exists in config on disk. "
                    "Run ot.reload() to sync runtime state."
                )
            # Swap into the shared config dict so downstream consumers (e.g.
            # the execution-namespace fingerprint) see the fresh tool_prefix.
            configured[name] = fresh_cfg
            srv_cfg = fresh_cfg
        else:
            srv_cfg = configured[name]

        if not srv_cfg.enabled:
            srv_cfg.enabled = True

        proxy.disconnect_server_sync(name)
        proxy.connect_additional_sync(name, srv_cfg)

        info = _get_server_info(name)
        connected_str = "connected" if info["connected"] else "connection failed"
        tool_str = f" ({info['tool_count']} tools)" if info["connected"] else ""
        s.add(connected=info["connected"])
        return f"Server '{name}' restarted — {connected_str}{tool_str}."
