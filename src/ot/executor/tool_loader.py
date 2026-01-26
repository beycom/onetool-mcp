"""Tool loading and discovery for command execution.

Handles:
- Loading tool functions from config-defined tool files
- Caching based on file modification times
- Pack extraction from tool modules
- PEP 723 detection for routing to worker processes

Used by the runner to make tools available during code execution.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.executor.pep723 import ToolFileInfo, categorize_tools
from ot.executor.worker_proxy import create_worker_proxy
from ot.paths import get_effective_cwd


def _get_bundled_tools_dir() -> Path | None:
    """Get the bundled tools directory from the ot_tools package.

    Returns:
        Path to ot_tools package directory, or None if not found.
    """
    try:
        import ot_tools

        return Path(ot_tools.__file__).parent
    except (ImportError, AttributeError):
        return None

if TYPE_CHECKING:
    from ot.config.loader import OneToolConfig


@dataclass
class LoadedTools:
    """Registry of loaded tool functions with pack support.

    The functions dict uses full pack-qualified names as keys (e.g., "brave.search")
    to avoid collisions when multiple packs have functions with the same name.
    The packs dict provides grouped access by pack.
    """

    functions: dict[str, Any]  # Full name -> callable (e.g., "brave.search" -> func)
    packs: dict[str, dict[str, Any]]  # Nested: pack -> {name -> callable}
    worker_tools: list[ToolFileInfo] = field(
        default_factory=list
    )  # Tools using workers


# Module cache: stores (LoadedTools, mtime_dict) for each tools_dir
_module_cache: dict[Path, tuple[LoadedTools, dict[str, float]]] = {}


def _get_tool_files(
    tools_dir: Path | None, config: OneToolConfig | None
) -> tuple[set[Path], Path]:
    """Resolve tool files from config, bundled package, or directory.

    Always includes bundled tools from ot_tools package, plus any
    additional tools from config or explicit tools_dir.

    Args:
        tools_dir: Explicit tools directory path.
        config: Loaded configuration (may be None).

    Returns:
        Tuple of (set of resolved file paths, cache key).
    """
    tool_files: list[Path] = []

    # Always include bundled tools from ot_tools package
    bundled_dir = _get_bundled_tools_dir()
    if bundled_dir and bundled_dir.exists():
        bundled_files = [
            f for f in bundled_dir.glob("*.py")
            if f.name != "__init__.py"
        ]
        tool_files.extend(bundled_files)
        logger.debug(f"Found {len(bundled_files)} bundled tools from {bundled_dir}")

    # Add config-specified tools
    config_tool_files = config.get_tool_files() if config else []
    if config_tool_files:
        tool_files.extend(config_tool_files)
        cache_key = Path("__config__")
    elif tools_dir is not None:
        # Explicit tools_dir provided - use it
        if tools_dir.exists():
            tools_dir = tools_dir.resolve()
            tool_files.extend(tools_dir.glob("*.py"))
        cache_key = tools_dir
    else:
        cache_key = Path("__bundled__")

    if not tool_files:
        return set(), Path("__no_tools__")

    current_files = {f.resolve() for f in tool_files if f.exists()}
    return current_files, cache_key


def _check_cache(cache_key: Path, current_files: set[Path]) -> LoadedTools | None:
    """Return cached registry if valid, None if stale or missing.

    Args:
        cache_key: Key for cache lookup.
        current_files: Set of current tool file paths.

    Returns:
        Cached LoadedTools if valid, None otherwise.
    """
    if cache_key not in _module_cache:
        return None

    cached_registry, cached_mtimes = _module_cache[cache_key]
    cached_files = {Path(f) for f in cached_mtimes}

    if current_files != cached_files:
        return None

    for py_file in current_files:
        try:
            if py_file.stat().st_mtime != cached_mtimes.get(str(py_file), 0):
                return None
        except OSError:
            return None

    return cached_registry


def _load_worker_tools(
    worker_tools: list[ToolFileInfo],
    config_dict: dict[str, Any],
    secrets: dict[str, Any],
    packs: dict[str, dict[str, Any]],
    mtimes: dict[str, float],
) -> tuple[dict[str, Any], list[ToolFileInfo]]:
    """Load PEP 723 tools via worker proxies.

    Args:
        worker_tools: List of tool file info for worker tools.
        config_dict: Configuration as dict.
        secrets: Secrets dict.
        packs: Packs dict to populate.
        mtimes: Modification times dict to populate.

    Returns:
        Tuple of (functions dict, loaded worker tools list).
    """
    functions: dict[str, Any] = {}
    loaded_workers: list[ToolFileInfo] = []

    for tool_info in worker_tools:
        py_file = tool_info.path
        try:
            mtimes[str(py_file)] = py_file.stat().st_mtime

            pack = tool_info.pack
            if pack and pack in packs:
                logger.warning(
                    f"Pack collision: '{pack}' already defined, "
                    f"merging functions from {py_file.stem}"
                )

            proxy = create_worker_proxy(
                tool_path=py_file,
                functions=tool_info.functions,
                config=config_dict,
                secrets=secrets,
            )

            if pack:
                if pack not in packs:
                    packs[pack] = {}
                packs[pack] = proxy  # type: ignore[assignment]
                for func_name in tool_info.functions:
                    full_name = f"{pack}.{func_name}"
                    functions[full_name] = getattr(proxy, func_name)
            else:
                for func_name in tool_info.functions:
                    functions[func_name] = getattr(proxy, func_name)

            loaded_workers.append(tool_info)
            logger.debug(
                f"Loaded worker tool {py_file.stem} with {len(tool_info.functions)} functions"
            )

        except Exception as e:
            logger.warning(f"Failed to load worker tool {py_file.stem}: {e}")

    return functions, loaded_workers


def _load_inprocess_tools(
    inprocess_tools: list[ToolFileInfo],
    packs: dict[str, dict[str, Any]],
    mtimes: dict[str, float],
) -> dict[str, Any]:
    """Load regular Python tools via importlib.

    Args:
        inprocess_tools: List of tool file info for in-process tools.
        packs: Packs dict to populate.
        mtimes: Modification times dict to populate.

    Returns:
        Functions dict with loaded tools.
    """
    functions: dict[str, Any] = {}

    for tool_info in inprocess_tools:
        py_file = tool_info.path
        module_name = f"tools.{py_file.stem}"

        try:
            mtimes[str(py_file)] = py_file.stat().st_mtime

            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            pack = getattr(module, "pack", None)
            if pack and pack in packs:
                logger.warning(
                    f"Pack collision: '{pack}' already defined, "
                    f"merging functions from {py_file.stem}"
                )

            export_names = getattr(module, "__all__", None)
            if export_names is None:
                export_names = [n for n in dir(module) if not n.startswith("_")]

            for name in export_names:
                obj = getattr(module, name, None)
                if obj is not None and callable(obj) and not isinstance(obj, type):
                    if pack:
                        if pack not in packs:
                            packs[pack] = {}
                        packs[pack][name] = obj
                        full_name = f"{pack}.{name}"
                        functions[full_name] = obj
                    else:
                        functions[name] = obj

        except Exception as e:
            logger.warning(f"Failed to load tool module {py_file.stem}: {e}")

    return functions


def load_tool_registry(tools_dir: Path | None = None) -> LoadedTools:
    """Load all tool functions from config tool files with pack support.

    Uses caching based on file modification times to avoid redundant loading.
    Reads `pack` module variable from each tool file to group functions.
    Detects PEP 723 headers to route tools to worker processes.

    The core 'ot' pack (from meta.py) is always registered regardless of config.

    Args:
        tools_dir: Explicit path to tools directory. If not provided,
                   tool files are loaded from config. If neither is available,
                   only the core 'ot' pack will be available.

    Returns:
        LoadedTools with functions dict (pack-qualified keys) and packs dict.
    """
    from ot.config.loader import get_config
    from ot.config.secrets import get_secrets

    config = get_config()
    current_files, cache_key = _get_tool_files(tools_dir, config)

    if not current_files:
        return LoadedTools(functions={}, packs={})

    cached = _check_cache(cache_key, current_files)
    if cached is not None:
        return cached

    logger.debug(f"Loading tools from {cache_key} ({len(current_files)} files)")

    packs: dict[str, dict[str, Any]] = {}
    mtimes: dict[str, float] = {}

    worker_tools, inprocess_tools = categorize_tools(list(current_files))

    secrets_path = config.get_secrets_file_path() if config else None
    secrets = get_secrets(secrets_path)
    config_dict = config.model_dump() if config else {}

    # Inject path context for worker tools (used by ot_sdk path functions)
    config_dict["_project_path"] = str(get_effective_cwd())
    if config and config._config_dir:
        config_dict["_config_dir"] = str(config._config_dir)

    worker_funcs, worker_tools_list = _load_worker_tools(
        worker_tools, config_dict, secrets, packs, mtimes
    )
    inprocess_funcs = _load_inprocess_tools(inprocess_tools, packs, mtimes)

    functions = {**worker_funcs, **inprocess_funcs}

    # Register the core 'ot' pack from meta.py (not loaded from tools_dir)
    ot_funcs = _register_ot_pack(packs)
    functions.update(ot_funcs)

    registry = LoadedTools(
        functions=functions, packs=packs, worker_tools=worker_tools_list
    )
    _module_cache[cache_key] = (registry, mtimes)

    return registry


def _register_ot_pack(packs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Register the core 'ot' pack from ot.meta module.

    The 'ot' pack provides introspection functions (tools, packs, config, etc.)
    and is always available regardless of tools_dir configuration.

    Args:
        packs: Packs dict to add 'ot' pack to.

    Returns:
        Functions dict with ot.* entries.
    """
    from ot.meta import PACK_NAME, get_ot_pack_functions

    ot_functions = get_ot_pack_functions()
    packs[PACK_NAME] = ot_functions

    # Build full function names
    return {f"{PACK_NAME}.{name}": func for name, func in ot_functions.items()}


def load_tool_functions(tools_dir: Path | None = None) -> dict[str, Any]:
    """Load all tool functions from the tools directory.

    Uses caching based on file modification times to avoid redundant loading.

    Args:
        tools_dir: Explicit path to tools directory. If not provided,
                   tool files are loaded from config.

    Returns:
        Dictionary mapping function names to callable functions.
    """
    return load_tool_registry(tools_dir).functions
