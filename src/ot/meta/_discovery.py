"""Tool, pack, and server discovery functions."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.logging import LogSpan
from ot.meta._constants import safe_server_name as _safe_server_name
from ot.meta._tool_discovery import _build_proxy_tool_info, _build_tool_info
from ot.proxy import get_proxy_manager

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel, ServerInfoLevel

log = LogSpan


_VALID_INFO_LEVELS = {"min", "default", "full"}
_VALID_SERVER_INFO_LEVELS = {"min", "default", "full", "resources", "prompts"}


def _alias_to_full(registry: Any) -> dict[str, str]:
    """Build alias → canonical pack mapping from loaded pack metadata."""
    result: dict[str, str] = {}
    for pack, aliases in getattr(registry, "pack_aliases", {}).items():
        for alias in aliases:
            result[alias] = pack
    return result


def _resolve_pack_alias(value: str, registry: Any) -> str:
    """Resolve a pack alias in a pack or tool pattern."""
    if not value:
        return value
    aliases = _alias_to_full(registry)
    if "." in value:
        prefix, _, suffix = value.partition(".")
        return f"{aliases.get(prefix, prefix)}.{suffix}"
    return aliases.get(value, value)


def tools(
    *,
    pattern: str = "",
    info: InfoLevel = "default",
) -> list[dict[str, Any] | str]:
    """List all available tools with optional filtering.

    Lists registered local tools and proxied MCP server tools.
    Use pattern for substring filtering.

    Args:
        pattern: Filter tools by name pattern (case-insensitive substring match)
        info: Output verbosity level - "min" (names only), "default" (name +
              description truncated to 200 chars, default), or "full" (name +
              full description + source)

    Returns:
        List of tool names (info="min") or tool dicts (info="default"/"full")

    Example:
        ot.tools()
        ot.tools(pattern="search")
        ot.tools(pattern="brave.")
        ot.tools(info="min")
        ot.tools(pattern="brave.search", info="full")
    """
    if info not in _VALID_INFO_LEVELS:
        raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

    from ot.executor.tool_loader import load_tool_registry

    with log(span="ot.tools", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        resolved_pattern = _resolve_pack_alias(pattern, runner_registry) if pattern else pattern
        resolved_lower = resolved_pattern.lower() if resolved_pattern else ""

        tools_list: list[dict[str, Any] | str] = []

        # Local tools from registry
        from ot.executor.worker_proxy import WorkerPackProxy

        for pack_name, pack_funcs in runner_registry.packs.items():
            # Handle both dict and WorkerPackProxy
            if isinstance(pack_funcs, WorkerPackProxy):
                func_names = list(pack_funcs.functions)
                func_items = [(n, getattr(pack_funcs, n)) for n in func_names]
            else:
                func_items = list(pack_funcs.items())

            for func_name, func in func_items:
                full_name = f"{pack_name}.{func_name}"

                if resolved_lower and resolved_lower not in full_name.lower():
                    continue

                tools_list.append(_build_tool_info(full_name, func, "local", info))

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            safe_server = _safe_server_name(proxy_tool.server)
            tool_name = f"{safe_server}.{proxy_tool.name}"

            if resolved_lower and resolved_lower not in tool_name.lower():
                continue

            tools_list.append(
                _build_proxy_tool_info(
                    tool_name,
                    proxy_tool.description or "",
                    proxy_tool.input_schema,
                    f"mcp:{proxy_tool.server}",
                    info,
                )
            )

        # Sort by name (handle both str and dict)
        tools_list.sort(key=lambda t: t if isinstance(t, str) else t["name"])
        s.add("count", len(tools_list))
        return tools_list


def tool_info(
    *,
    name: str = "",
    pattern: str = "",
    info: InfoLevel = "default",
) -> dict[str, Any] | list[dict[str, Any]]:
    """Get detailed info for one or more tools.

    Returns signature, args, description, and source. Use name= for exact match
    (returns dict), pattern= for substring match (returns list of dicts).

    Args:
        name: Exact tool name (e.g., "brave.search"). Returns a single dict.
        pattern: Substring filter for tool names. Returns a list of dicts.
        info: Output verbosity level - "min" (name + signature + args), "default"
              (+ description truncated + source, default), or "full" (everything)

    Returns:
        Single dict if name= provided, list of dicts if pattern= provided

    Example:
        ot.tool_info(name="brave.search")
        ot.tool_info(pattern="brave")
        ot.tool_info(name="ot.tools", info="full")
    """
    from ot.executor.tool_loader import load_tool_registry

    if info not in _VALID_INFO_LEVELS:
        raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

    with log(span="ot.tool_info", name=name or None, pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        filter_pattern = name or pattern
        if filter_pattern:
            filter_pattern = _resolve_pack_alias(filter_pattern, runner_registry)
        filter_lower = filter_pattern.lower() if filter_pattern else ""

        results: list[dict[str, Any]] = []
        # Unfiltered set of every tool full name — needed for did-you-mean on an
        # exact-name miss, since `results` is empty by construction in that case.
        all_full_names: list[str] = []

        # Local tools
        from ot.executor.worker_proxy import WorkerPackProxy

        for pack_name, pack_funcs in runner_registry.packs.items():
            if isinstance(pack_funcs, WorkerPackProxy):
                func_names = list(pack_funcs.functions)
                func_items = [(n, getattr(pack_funcs, n)) for n in func_names]
            else:
                func_items = list(pack_funcs.items())

            for func_name, func in func_items:
                full_name = f"{pack_name}.{func_name}"
                all_full_names.append(full_name)

                if filter_lower and filter_lower not in full_name.lower():
                    continue

                entry = _build_tool_info(full_name, func, "local", info, detail=True)
                if isinstance(entry, dict):
                    results.append(entry)

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            safe_server = _safe_server_name(proxy_tool.server)
            tool_name = f"{safe_server}.{proxy_tool.name}"
            all_full_names.append(tool_name)

            if filter_lower and filter_lower not in tool_name.lower():
                continue

            entry = _build_proxy_tool_info(
                tool_name,
                proxy_tool.description or "",
                proxy_tool.input_schema,
                f"mcp:{proxy_tool.server}",
                info,
                detail=True,
            )
            if isinstance(entry, dict):
                results.append(entry)

        results.sort(key=lambda t: t["name"])
        s.add("count", len(results))

        # Exact name match returns single dict
        if name:
            for result in results:
                if result["name"] == filter_pattern:
                    return result
            # Miss: return an actionable error with fuzzy suggestions instead of {}.
            from ot.meta._help_formatting import _fuzzy_match

            return {
                "error": f"Tool '{filter_pattern}' not found.",
                "did_you_mean": _fuzzy_match(filter_pattern, all_full_names)[:5],
            }

        return results


def packs(
    *,
    pattern: str = "",
    info: InfoLevel = "default",
) -> list[dict[str, Any] | str]:
    """List all packs with optional filtering.

    Lists all available packs (local and proxy).
    Use pattern for substring filtering.

    Args:
        pattern: Filter packs by name pattern (case-insensitive substring)
        info: Output verbosity level - "min" (names only), "default" (name +
              description, default), or "full" (name + source + description +
              tool_names)

    Returns:
        List of pack names (info="min") or pack dicts (info="default"/"full")

    Example:
        ot.packs()
        ot.packs(pattern="brav")
        ot.packs(info="min")
        ot.packs(info="full")
    """
    if info not in _VALID_INFO_LEVELS:
        raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

    from ot.executor.tool_loader import load_tool_registry
    from ot.prompts import PromptsError, get_prompts

    with log(span="ot.packs", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Collect all packs
        local_packs = set(runner_registry.packs.keys())
        proxy_packs = set(proxy.servers)
        all_pack_names = sorted(local_packs | proxy_packs)

        # Filter by pattern (resolve short alias)
        resolved_pat = _resolve_pack_alias(pattern, runner_registry) if pattern else pattern
        if resolved_pat:
            all_pack_names = [p for p in all_pack_names if resolved_pat.lower() in p.lower()]

        # info="min" - just names
        if info == "min":
            s.add("count", len(all_pack_names))
            return all_pack_names  # type: ignore[return-value]

        # Load prompts for descriptions
        try:
            prompts_config = get_prompts()
            packs_descriptions = prompts_config.packs
        except PromptsError:
            packs_descriptions = {}

        packs_list: list[dict[str, Any] | str] = []

        for pack_name in all_pack_names:
            is_local = pack_name in local_packs
            source = "local" if is_local else "mcp"

            # Get description from prompts.yaml packs section, fall back to module docstring
            description = packs_descriptions.get(pack_name, "")
            if not description and is_local:
                description = _get_pack_module_description(runner_registry, pack_name)

            aliases = getattr(runner_registry, "pack_aliases", {}).get(pack_name, ())
            # Join all aliases (most packs have one) so multi-alias packs like
            # whiteboard (wb, excalidraw) surface every short name they answer to.
            short = ", ".join(aliases) if aliases else None

            if info == "default":
                entry: dict[str, Any] = {"name": pack_name, "description": description or "(no description)"}
                if short:
                    entry["short"] = short
                packs_list.append(entry)
            else:
                # info == "full"
                tool_names = _get_pack_tool_names(runner_registry, proxy, pack_name, is_local)
                full_entry: dict[str, Any] = {
                    "name": pack_name,
                    "source": source,
                    "description": description or "(no description)",
                    "tool_names": tool_names,
                }
                if short:
                    full_entry["short"] = short
                packs_list.append(full_entry)

        s.add("count", len(packs_list))
        return packs_list


def pack_info(
    *,
    name: str = "",
    info: InfoLevel = "default",
) -> dict[str, Any]:
    """Get detailed info for a single pack.

    Returns source, description, instructions, and tool names.

    Args:
        name: Pack name (e.g., "brave", "file")
        info: Output verbosity level - "min" (name + source + tool_names),
              "default" (+ description + instructions, default), or "full"
              (same as default)

    Returns:
        Pack info dict

    Example:
        ot.pack_info(name="brave")
        ot.pack_info(name="excel", info="full")
    """
    if info not in _VALID_INFO_LEVELS:
        raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

    from ot.executor.tool_loader import load_tool_registry
    from ot.prompts import PromptsError, get_pack_instructions, get_prompts

    with log(span="ot.pack_info", name=name or None, info=info) as s:
        runner_registry = load_tool_registry()
        name = _resolve_pack_alias(name, runner_registry) if name else name
        proxy = get_proxy_manager()
        cfg = get_config()

        local_packs = set(runner_registry.packs.keys())
        proxy_packs = set(proxy.servers)

        if name not in local_packs and name not in proxy_packs:
            s.add("found", False)
            return {"error": f"Pack '{name}' not found. Use ot.packs() to list available packs."}

        is_local = name in local_packs
        source = "local" if is_local else "mcp"
        tool_names = _get_pack_tool_names(runner_registry, proxy, name, is_local)

        s.add("found", True)
        s.add("tool_count", len(tool_names))

        if info == "min":
            return {"name": name, "source": source, "tool_names": tool_names}

        # default and full — include description and instructions
        try:
            prompts_config = get_prompts()
            packs_descriptions = prompts_config.packs
            instructions = get_pack_instructions(prompts_config, name)
        except PromptsError:
            packs_descriptions = {}
            instructions = None

        # Check server config for instructions (proxy packs)
        if not instructions and not is_local and name in cfg.servers:
            server_cfg = cfg.servers[name]
            instructions = server_cfg.instructions or None

        description = packs_descriptions.get(name, "")
        if not description and is_local:
            description = _get_pack_module_description(runner_registry, name)

        return {
            "name": name,
            "source": source,
            "description": description or "(no description)",
            "instructions": instructions or "",
            "tool_names": tool_names,
        }


def _get_pack_module_description(runner_registry: Any, pack_name: str) -> str:
    """Get description from the pack module docstring first line."""
    from ot.executor.worker_proxy import WorkerPackProxy

    pack_funcs = runner_registry.packs.get(pack_name)
    if not pack_funcs:
        return ""

    # Try to get module docstring from the first function's module
    if isinstance(pack_funcs, WorkerPackProxy):
        return ""

    func = next(iter(pack_funcs.values()), None)
    if func is None:
        return ""

    module = getattr(func, "__module__", None)
    if module:
        mod = sys.modules.get(module)
        if mod and mod.__doc__:
            return mod.__doc__.strip().split("\n")[0].strip()

    return ""


def _get_pack_tool_names(
    runner_registry: Any, proxy: Any, pack_name: str, is_local: bool
) -> list[str]:
    """Get list of tool names for a pack."""
    from ot.executor.worker_proxy import WorkerPackProxy

    if is_local:
        pack_funcs = runner_registry.packs[pack_name]
        if isinstance(pack_funcs, WorkerPackProxy):
            return sorted(f"{pack_name}.{n}" for n in pack_funcs.functions)
        return sorted(f"{pack_name}.{n}" for n in pack_funcs)
    else:
        proxy_tools = proxy.list_tools(server=pack_name)
        return sorted(f"{pack_name}.{t.name}" for t in proxy_tools)


def servers(
    *,
    pattern: str = "",
    info: ServerInfoLevel = "default",
) -> list[dict[str, Any] | str]:
    """List configured MCP proxy servers with optional filtering.

    Shows all MCP servers configured in servers.yaml, including their
    connection status and instructions.

    Args:
        pattern: Filter servers by name pattern (case-insensitive substring)
        info: Output verbosity level:
            - "min": names only
            - "default": name + status + enabled + [call_as] + [tool_count] (default)
            - "full": structured dicts with source and tools list
            - "resources": list resources per server
            - "prompts": list prompts per server

    Returns:
        List of server names (info="min") or server dicts/strings

    Example:
        ot.servers()
        ot.servers(pattern="github")
        ot.servers(info="full")
        ot.servers(info="resources")
        ot.servers(pattern="chrome_devtools", info="prompts")
    """
    if info not in _VALID_SERVER_INFO_LEVELS:
        raise ValueError(
            f"info={info!r} is not valid. Use 'min', 'default', 'full', 'resources', or 'prompts'."
        )

    proxy = get_proxy_manager()
    cfg = get_config()

    with log(span="ot.servers", pattern=pattern or None, info=info) as s:
        # Get all configured servers
        all_server_names = sorted(cfg.servers.keys())

        # Filter by pattern
        if pattern:
            all_server_names = [
                name for name in all_server_names if pattern.lower() in name.lower()
            ]

        # info="min" - just names
        if info == "min":
            s.add("count", len(all_server_names))
            return all_server_names  # type: ignore[return-value]

        # info="full" - structured dicts (guidance lives in ot.help())
        if info == "full":
            results: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                server_cfg = cfg.servers[server_name]
                conn = proxy.get_connection(server_name)
                status = "connected" if conn else "disconnected"
                safe_name = _safe_server_name(server_name)
                proxy_tools = proxy.list_tools(server=server_name) if conn else []

                entry: dict[str, Any] = {
                    "name": server_name,
                    "status": status,
                    "enabled": server_cfg.enabled,
                    "source": getattr(server_cfg, "source", None),
                }
                if safe_name != server_name:
                    entry["call_as"] = safe_name
                if conn:
                    entry["tool_count"] = len(proxy_tools)
                    entry["tools"] = sorted(
                        f"{safe_name}.{t.name}" for t in proxy_tools
                    )
                else:
                    entry["tool_count"] = 0
                    entry["tools"] = []
                    error = proxy.get_error(server_name)
                    if error:
                        entry["error"] = error

                results.append(entry)

            s.add("count", len(results))
            return results

        # info="resources" - list resources per server
        if info == "resources":
            results_resources: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                conn = proxy.get_connection(server_name)
                if not conn:
                    results_resources.append({
                        "server": server_name,
                        "status": "disconnected",
                        "resources": [],
                    })
                    continue

                try:
                    resources = proxy.list_resources_sync(server_name, timeout=10.0)

                    results_resources.append({
                        "server": server_name,
                        "status": "connected",
                        "resource_count": len(resources),
                        "resources": resources,
                    })
                except Exception as e:
                    results_resources.append({
                        "server": server_name,
                        "status": "error",
                        "error": str(e),
                        "resources": [],
                    })

            s.add("count", len(results_resources))
            return results_resources

        # info="prompts" - list prompts per server
        if info == "prompts":
            results_prompts: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                conn = proxy.get_connection(server_name)
                if not conn:
                    results_prompts.append({
                        "server": server_name,
                        "status": "disconnected",
                        "prompts": [],
                    })
                    continue

                try:
                    prompts = proxy.list_prompts_sync(server_name, timeout=10.0)

                    results_prompts.append({
                        "server": server_name,
                        "status": "connected",
                        "prompt_count": len(prompts),
                        "prompts": prompts,
                    })
                except Exception as e:
                    results_prompts.append({
                        "server": server_name,
                        "status": "error",
                        "error": str(e),
                        "prompts": [],
                    })

            s.add("count", len(results_prompts))
            return results_prompts

        # info="default" - operational dashboard
        servers_list: list[dict[str, Any] | str] = []

        for server_name in all_server_names:
            server_cfg = cfg.servers[server_name]
            conn = proxy.get_connection(server_name)
            status = "connected" if conn else "disconnected"
            safe_name = _safe_server_name(server_name)

            server_info: dict[str, Any] = {
                "name": server_name,
                "status": status,
                "enabled": server_cfg.enabled,
            }
            # call_as only when the Python identifier differs from the config key
            if safe_name != server_name:
                server_info["call_as"] = safe_name
            # tool_count only when connected
            if conn:
                server_info["tool_count"] = len(proxy.list_tools(server=server_name))
            else:
                error = proxy.get_error(server_name)
                if error:
                    server_info["error"] = error
            servers_list.append(server_info)

        s.add("count", len(servers_list))
        return servers_list
