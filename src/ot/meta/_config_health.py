"""Configuration, status, and reload functions."""

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


def status() -> dict[str, Any]:
    """Report cheap runtime status for OneTool components.

    Returns:
        Dict with runtime, registry, proxy, config, storage, direct API, and warnings.

    Example:
        ot.status()
    """
    from ot.executor.tool_loader import load_tool_registry

    with log(span="ot.status") as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        cfg = get_config()
        enabled_servers = {
            name: server for name, server in cfg.servers.items() if server.enabled
        }

        tool_count = sum(len(funcs) for funcs in runner_registry.packs.values())
        warnings_out: list[str] = []

        server_statuses: dict[str, Any] = {}
        for server_name in enabled_servers:
            conn = proxy.get_connection(server_name)
            if conn:
                server_statuses[server_name] = "connected"
            else:
                error = proxy.get_error(server_name)
                server_statuses[server_name] = (
                    {"status": "disconnected", "error": error}
                    if error
                    else "disconnected"
                )

        proxy_ok = (
            all(
                state == "connected"
                if isinstance(state, str)
                else state.get("status") == "connected"
                for state in server_statuses.values()
            )
            or not server_statuses
        )
        if not proxy_ok:
            warnings_out.append(
                "One or more configured proxy servers are disconnected."
            )

        direct_status: dict[str, Any] = {
            "configured": cfg.direct.host.enabled,
            "status": "disabled",
        }
        server_module = sys.modules.get("ot.server")
        if cfg.direct.host.enabled:
            port = (
                getattr(server_module, "_direct_api_port", None)
                if server_module
                else None
            )
            direct_status["status"] = "ready" if port else "degraded"
            direct_status["port"] = port
            if not port:
                warnings_out.append(
                    "Direct API is enabled but no bound port is recorded."
                )

        registry_status = {
            "status": "ok",
            "pack_count": len(runner_registry.packs),
            "tool_count": tool_count,
        }
        proxy_status: dict[str, Any] = {
            "status": "ok" if proxy_ok else "degraded",
            "server_count": len(enabled_servers),
            "connected_count": sum(
                1 for state in server_statuses.values() if state == "connected"
            ),
            "background_connecting": proxy.is_connecting,
        }
        if server_statuses:
            proxy_status["servers"] = server_statuses

        config_path = None
        try:
            from ot.config.loader import get_loaded_config_path

            loaded_path = get_loaded_config_path()
            config_path = str(loaded_path) if loaded_path else None
        except Exception:
            pass

        result = {
            "version": __version__,
            "runtime": {
                "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "cwd": str(resolve_cwd_path(".")),
                "root_mcp": {"transport": "stdio"},
            },
            "config": {
                "path": config_path,
                "dir": str(cfg._config_dir),
                "include_count": len(cfg.include),
                "tools_dir_count": len(cfg.tools_dir),
            },
            "storage": {
                "log_dir": str(cfg.get_log_dir_path()),
                "stats_path": str(cfg.get_stats_file_path()),
                "stats_enabled": cfg.stats.enabled,
                "result_store": str(cfg.get_result_store_path()),
            },
            "registry": registry_status,
            "proxy": proxy_status,
            "direct_api": direct_status,
            "warnings": warnings_out,
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
        _ot_cache.clear()  # Clears TTL-cached data
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
