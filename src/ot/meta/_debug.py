"""Debug and system information for ot.debug()."""

from __future__ import annotations

import getpass
import hashlib
import os
import platform
import sys
import time
from typing import Any

from ot import __version__
from ot.config import get_config
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path

log = LogSpan

# Track when module was first loaded (OneTool start time)
_MODULE_LOAD_TIME = time.time()


def _get_version_info() -> dict[str, Any]:
    """Get version information from package metadata."""
    return {"version": __version__}


def _get_paths_info() -> dict[str, Any]:
    """Get all relevant path information."""
    from pathlib import Path

    install_path = Path(__file__).parent.parent.parent.resolve()
    cfg = get_config()

    paths: dict[str, Any] = {
        "install": str(install_path),
        "cwd": str(resolve_cwd_path(".")),
        "python": sys.executable,
    }

    try:
        paths["config_file"] = str(cfg._config_dir / "onetool.yaml")
        paths["config_dir"] = str(cfg._config_dir)
    except AttributeError:
        pass

    paths["log_dir"] = str(cfg.get_log_dir_path())

    if cfg.stats.enabled:
        paths["stats_file"] = str(cfg.get_stats_file_path())

    paths["result_store"] = str(cfg.get_result_store_path())

    return paths


def _get_config_info(verbose: bool = False) -> dict[str, Any]:
    """Get configuration summary."""
    from ot.executor.tool_loader import load_tool_registry

    cfg = get_config()
    registry = load_tool_registry()

    info: dict[str, Any] = {
        "version": cfg.version,
        "servers": list(cfg.servers.keys()),
        "packs_loaded": len(registry.packs),
        "aliases": len(cfg.alias) if cfg.alias else 0,
        "snippets": len(cfg.snippets) if cfg.snippets else 0,
    }

    if verbose:
        info["includes"] = cfg.include
        info["tools_dir"] = cfg.tools_dir
        info["stats_enabled"] = cfg.stats.enabled
        info["log_verbose"] = cfg.log_verbose

    return info


def _get_python_info() -> dict[str, Any]:
    """Get Python environment information."""
    return {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "implementation": sys.implementation.name,
        "platform": sys.platform,
        "executable": sys.executable,
    }


def _get_system_info() -> dict[str, Any]:
    """Get OS/system information."""
    info = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "user": getpass.getuser(),
        "pid": os.getpid(),
    }

    # Add memory usage if psutil available
    try:
        import psutil  # type: ignore[import-untyped]

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        info["memory"] = {
            "rss_mb": round(mem_info.rss / 1024 / 1024, 2),
            "vms_mb": round(mem_info.vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2),
        }
    except ImportError:
        pass

    return info


def _get_runtime_info() -> dict[str, Any]:
    """Get current runtime state."""
    from datetime import UTC, datetime

    from ot.executor.tool_loader import load_tool_registry
    from ot.logging.config import get_runtime_log_identity
    from ot.proxy import get_proxy_manager

    registry = load_tool_registry()
    proxy = get_proxy_manager()
    cfg = get_config()

    # Count local tools
    tool_count = sum(len(funcs) for funcs in registry.packs.values())

    # Count proxy connections
    connected = sum(1 for name in cfg.servers if proxy.get_connection(name))
    disconnected = len(cfg.servers) - connected

    # Timing information
    current_time = time.time()
    uptime_seconds = current_time - _MODULE_LOAD_TIME
    start_time = datetime.fromtimestamp(_MODULE_LOAD_TIME, tz=UTC)

    return {
        **get_runtime_log_identity(),
        "packs_loaded": len(registry.packs),
        "tools_local": tool_count,
        "tools_proxied": proxy.tool_count,
        "servers_configured": len(cfg.servers),
        "servers_connected": connected,
        "servers_disconnected": disconnected,
        "start_time": start_time.isoformat(),
        "uptime_seconds": round(uptime_seconds, 2),
    }


def _get_prompts_info() -> dict[str, Any]:
    """Get prompt source diagnostics and critical rule checks."""
    from ot.prompts import _get_template_prompts_path, get_prompts

    cfg = get_config()
    source = "inline" if cfg.prompts is not None else "file"
    path = None
    if cfg.prompts is None:
        candidate = resolve_cwd_path("config/prompts.yaml")
        path_obj = candidate if candidate.exists() else _get_template_prompts_path()
        path = str(path_obj)

    prompts = get_prompts(inline_prompts=cfg.prompts)
    run_prompt = prompts.tools.get("run")
    run_desc = run_prompt.description if run_prompt else ""
    instructions = prompts.instructions
    combined = f"{instructions}\n\n{run_desc or ''}"
    digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    checks = {
        "has_run_contract": "Mode by shape:" in (run_desc or ""),
        "has_canonical_trigger": "__onetool" in combined,
        "has_snippet_colon": ":name" in combined or ":snippet" in combined,
        "has_direct_tool_intent": "use ot pack.tool" in combined,
        "has_mcp_preference": "run(command=" in combined,
        "has_natural_language_mode": "natural-language intent" in (run_desc or ""),
        "has_keyword_only_repair": "keyword-only tools" in (run_desc or ""),
    }
    return {
        "source": source,
        "path": path,
        "sha256": digest,
        "instructions_excerpt": instructions.strip()[:500],
        "run_description_excerpt": (run_desc or "").strip()[:500],
        "checks": checks,
    }


def debug(
    *,
    verbose: bool = False,
    env_vars: bool = False,
    dependencies: bool = False,
    prompts: bool = False,
) -> dict[str, Any]:
    """Get comprehensive debug information about this OneTool installation.

    Essential for multi-version development - clearly identifies which
    version is running and where it's configured.

    Args:
        verbose: Include detailed configuration information
        env_vars: Include relevant environment variables
        dependencies: Include dependency versions
        prompts: Include prompt source diagnostics and critical rule checks

    Returns:
        Structured debug information with sections:
        - version: Package version
        - paths: All relevant file paths
        - config: Configuration summary
        - python: Python environment details
        - system: OS/platform information
        - runtime: Current runtime state (packs, servers, tools, timing)

    Example:
        ot.debug()
        ot.debug(verbose=True, env_vars=True)
    """
    with log(span="ot.debug", verbose=verbose, prompts=prompts) as s:
        result: dict[str, Any] = {
            "version": _get_version_info(),
            "paths": _get_paths_info(),
            "config": _get_config_info(verbose=verbose),
            "python": _get_python_info(),
            "system": _get_system_info(),
            "runtime": _get_runtime_info(),
        }

        if env_vars:
            # Include relevant environment variables
            result["env"] = {
                "OT_CWD": os.getenv("OT_CWD"),
            }

        if dependencies:
            # Include dependency versions
            from importlib.metadata import PackageNotFoundError
            from importlib.metadata import version as get_version

            deps = {}
            for pkg in ["fastmcp", "pydantic", "pyyaml", "loguru", "requests", "openai"]:
                try:
                    deps[pkg] = get_version(pkg)
                except PackageNotFoundError:
                    deps[pkg] = "not installed"
            result["dependencies"] = deps

        if prompts:
            result["prompts"] = _get_prompts_info()

        version_str = result["version"].get("version", "unknown")
        s.add("version", version_str)

        return result
