"""Configuration, health, and reload functions."""

from __future__ import annotations

import sys
from typing import Any

from ot import __version__
from ot.config import get_config
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path
from ot.proxy import get_proxy_manager

log = LogSpan


def config() -> dict[str, Any]:
    """Show key configuration values.

    Returns tools_dir, include, aliases, snippets, and server names.

    Returns:
        Dict with configuration summary

    Example:
        ot.config()
    """
    with log(span="ot.config") as s:
        cfg = get_config()

        result: dict[str, Any] = {
            "tools_dir": cfg.tools_dir,
            "include": cfg.include,
            "aliases": dict(cfg.alias) if cfg.alias else {},
            "snippets": {
                name: {"description": snippet.description}
                for name, snippet in cfg.snippets.items()
            }
            if cfg.snippets
            else {},
            "servers": list(cfg.servers.keys()) if cfg.servers else [],
        }

        s.add("toolsDirCount", len(result["tools_dir"]))
        s.add("includeCount", len(result["include"]))
        s.add("aliasCount", len(result["aliases"]))
        s.add("snippetCount", len(result["snippets"]))
        s.add("serverCount", len(result["servers"]))

        return result


def health() -> dict[str, Any]:
    """Check health of OneTool components.

    Returns:
        Dict with component status for registry and proxy

    Example:
        ot.health()
    """
    from ot.executor.tool_loader import load_tool_registry

    with log(span="ot.health") as s:
        from ot.executor.worker_proxy import WorkerPackProxy

        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        cfg = get_config()

        # Count functions, handling both dict and WorkerPackProxy
        tool_count = 0
        for funcs in runner_registry.packs.values():
            if isinstance(funcs, WorkerPackProxy):
                tool_count += len(funcs.functions)
            else:
                tool_count += len(funcs)
        registry_status = {
            "status": "ok",
            "tool_count": tool_count,
        }

        server_statuses: dict[str, Any] = {}
        for server_name in cfg.servers:
            conn = proxy.get_connection(server_name)
            if conn:
                server_statuses[server_name] = "connected"
            else:
                error = proxy.get_error(server_name)
                server_statuses[server_name] = {"status": "disconnected", "error": error} if error else "disconnected"

        proxy_status: dict[str, Any] = {
            "status": "ok"
            if all(
                (s == "connected" if isinstance(s, str) else s.get("status") == "connected")
                for s in server_statuses.values()
            )
            or not server_statuses
            else "degraded",
            "server_count": len(cfg.servers),
        }
        if server_statuses:
            proxy_status["servers"] = server_statuses

        result = {
            "version": __version__,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "cwd": str(resolve_cwd_path(".")),
            "registry": registry_status,
            "proxy": proxy_status,
        }

        s.add("registryOk", registry_status["status"] == "ok")
        s.add("proxyOk", proxy_status["status"] == "ok")

        return result


def reload() -> str:
    """Force reload of all configuration.

    Clears all cached state and reloads from disk:
    - Configuration (onetool.yaml and includes)
    - Secrets (secrets.yaml)
    - Tool registry (tool files from tools_dir)
    - Prompts
    - Skills index (bundled skill content)
    - Execution namespace cache (pack proxies)
    - MCP proxy connections
    - Parameter resolution caches
    - Security validation caches

    Use after modifying config files, adding/removing tools, or
    changing secrets during a session.

    Returns:
        Status message confirming reload

    Example:
        ot.reload()
    """
    with log(span="ot.reload") as s:
        # Import modules
        import ot.config
        import ot.executor.pack_proxy
        import ot.executor.param_resolver
        import ot.executor.tool_loader
        import ot.executor.validator
        import ot.prompts
        import ot.proxy
        import ot.registry
        from ot.services import get_services, reset_services
        from ot.utils.cache import cache as _ot_cache

        # Clear in dependency order (config first, others depend on it)
        reset_services()
        ot.executor.tool_loader.reset()
        ot.executor.tool_loader.load_tool_registry()
        services = get_services()
        services.run_reload_hooks()
        reset_services()

        ot.config.reset()  # Clears both config and secrets
        ot.prompts.reset()
        _ot_cache.clear()  # Clears skills index and other TTL-cached data
        ot.registry.reset()
        ot.executor.tool_loader.reset()
        ot.executor.validator.reset()
        ot.executor.pack_proxy.reset()  # Releases stale namespace/proxy references

        # Clear param resolver cache
        ot.executor.param_resolver.get_tool_param_names.cache_clear()
        ot.executor.param_resolver._mcp_param_cache.clear()

        tool_modules_cleared = ot.executor.tool_loader.clear_reloadable_tool_modules()
        s.add("toolModulesCleared", tool_modules_cleared)

        # Reload config to validate and report stats
        cfg = get_config()

        # Reconnect MCP proxy servers with fresh config
        ot.proxy.reconnect_proxy_manager()
        s.add("aliasCount", len(cfg.alias) if cfg.alias else 0)
        s.add("snippetCount", len(cfg.snippets) if cfg.snippets else 0)
        s.add("serverCount", len(cfg.servers) if cfg.servers else 0)

        return "OK: Configuration reloaded"
