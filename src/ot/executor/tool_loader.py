"""Tool loading and discovery for command execution.

Handles:
- Loading tool functions from config-defined tool files
- Caching based on file modification times
- Pack extraction from tool modules
- PEP 723 detection for routing to worker processes

Used by the runner to make tools available during code execution.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.executor.pep723 import ToolFileInfo, categorize_tools
from ot.executor.worker_proxy import create_worker_proxy
from ot.paths import get_effective_cwd


def _get_bundled_tools_dir() -> Path | None:
    """Get the bundled tools directory from the ottools package.

    Returns:
        Path to ottools package directory, or None if not found.
    """
    try:
        import ottools

        return Path(ottools.__file__).parent
    except (ImportError, AttributeError):
        return None


def _get_domain_tool_dirs() -> list[Path]:
    """Discover tool dirs from installed domain extras. Silently skips if not installed.

    Returns:
        List of paths to domain tool directories (otdev, otutil).
    """
    dirs = []
    for pkg in ("otdev.tools", "otutil.tools"):
        try:
            mod = importlib.import_module(pkg)
            if mod.__file__:
                dirs.append(Path(mod.__file__).parent)
        except ImportError:
            pass
    return dirs


if TYPE_CHECKING:
    from ot.config import OneToolConfig


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
    extension_tools: list[ToolFileInfo] = field(
        default_factory=list
    )  # User extension tools (non-internal inprocess)
    pack_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    doc_slugs: dict[str, str] = field(default_factory=dict)


# Module cache: stores (LoadedTools, mtime_dict, last_validated) for each tools_dir
# Uses OrderedDict for LRU eviction with bounded size
_MODULE_CACHE_MAXSIZE = 16
_module_cache: OrderedDict[Path, tuple[LoadedTools, dict[str, float], float]] = OrderedDict()

# TTL for skipping per-file mtime checks when the cache was recently validated
_CACHE_TTL = 1.0  # seconds


def _cache_get(key: Path) -> tuple[LoadedTools, dict[str, float], float] | None:
    """Get from cache with LRU update."""
    if key in _module_cache:
        _module_cache.move_to_end(key)
        return _module_cache[key]
    return None


def _cache_set(key: Path, value: tuple[LoadedTools, dict[str, float], float]) -> None:
    """Set in cache with LRU eviction."""
    if key in _module_cache:
        _module_cache.move_to_end(key)
    _module_cache[key] = value
    while len(_module_cache) > _MODULE_CACHE_MAXSIZE:
        _module_cache.popitem(last=False)


def _get_tool_files(
    tools_dir: Path | None, config: OneToolConfig | None
) -> tuple[set[Path], set[Path], Path]:
    """Resolve tool files from config, bundled package, or directory.

    Always includes bundled tools from ottools package, plus any
    additional tools from config or explicit tools_dir.

    Args:
        tools_dir: Explicit tools directory path.
        config: Loaded configuration (may be None).

    Returns:
        Tuple of (all tool file paths, internal tool paths, cache key).
    """
    tool_files: list[Path] = []
    internal_files: set[Path] = set()

    # Always include bundled tools from ottools package
    bundled_dir = _get_bundled_tools_dir()
    if bundled_dir and bundled_dir.exists():
        bundled_files = [f for f in bundled_dir.glob("*.py") if f.name != "__init__.py"]
        tool_files.extend(bundled_files)
        # Mark bundled tools as internal (shipped with OneTool)
        internal_files = {f.resolve() for f in bundled_files if f.exists()}
        logger.debug(f"Found {len(bundled_files)} bundled tools from {bundled_dir}")

    # Include domain extra tools (otdev, otutil) if installed
    for extra_dir in _get_domain_tool_dirs():
        if extra_dir.exists():
            extra_files = [f for f in extra_dir.glob("*.py") if f.name != "__init__.py"]
            tool_files.extend(extra_files)
            internal_files |= {f.resolve() for f in extra_files if f.exists()}
            logger.debug(f"Found {len(extra_files)} domain tools from {extra_dir}")

    # Add config-specified tools (these are extension tools, not internal)
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
        return set(), set(), Path("__no_tools__")

    current_files = {f.resolve() for f in tool_files if f.exists()}
    return current_files, internal_files, cache_key


def _check_cache(cache_key: Path, current_files: set[Path]) -> LoadedTools | None:
    """Return cached registry if valid, None if stale or missing.

    Skips per-file stat calls if the cache was validated within _CACHE_TTL seconds.

    Args:
        cache_key: Key for cache lookup.
        current_files: Set of current tool file paths.

    Returns:
        Cached LoadedTools if valid, None otherwise.
    """
    cached = _cache_get(cache_key)
    if cached is None:
        return None

    cached_registry, cached_mtimes, last_validated = cached
    cached_files = {Path(f) for f in cached_mtimes}

    if current_files != cached_files:
        return None

    now = time.time()
    if now - last_validated < _CACHE_TTL:
        # Recently validated — skip per-file stat syscalls
        return cached_registry

    for py_file in current_files:
        try:
            if py_file.stat().st_mtime != cached_mtimes.get(str(py_file), 0):
                return None
        except OSError:
            return None

    # Update last_validated timestamp
    _cache_set(cache_key, (cached_registry, cached_mtimes, now))
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
        worker_tools: List of tool file info for extension tools.
        config_dict: Configuration as dict.
        secrets: Secrets dict.
        packs: Packs dict to populate.
        mtimes: Modification times dict to populate.

    Returns:
        Tuple of (functions dict, loaded extension tools list).
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
                f"Loaded extension tool {py_file.stem} with {len(tool_info.functions)} functions"
            )

        except Exception as e:
            logger.warning(f"Failed to load extension tool {py_file.stem}: {e}")

    return functions, loaded_workers


def _load_inprocess_tools(
    inprocess_tools: list[ToolFileInfo],
    packs: dict[str, dict[str, Any]],
    mtimes: dict[str, float],
) -> tuple[dict[str, Any], dict[str, tuple[str, ...]], dict[str, str]]:
    """Load regular Python tools via importlib.

    Args:
        inprocess_tools: List of tool file info for in-process tools.
        packs: Packs dict to populate.
        mtimes: Modification times dict to populate.

    Returns:
        Functions dict with loaded tools.
    """
    functions: dict[str, Any] = {}
    pack_aliases: dict[str, tuple[str, ...]] = {}
    doc_slugs: dict[str, str] = {}

    for tool_info in inprocess_tools:
        py_file = tool_info.path
        # Include parent dir to reduce sys.modules key collisions between tool packages
        module_name = f"ot_tool.{py_file.parent.name}.{py_file.stem}"

        try:
            mtimes[str(py_file)] = py_file.stat().st_mtime

            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            pack = getattr(module, "pack", None)
            aliases = getattr(module, "pack_aliases", ())
            if pack and aliases:
                pack_aliases[pack] = tuple(str(alias) for alias in aliases)
            doc_slug = getattr(module, "doc_slug", None)
            if pack and doc_slug:
                doc_slugs[pack] = str(doc_slug)

            register_services = getattr(module, "register_services", None)
            if callable(register_services):
                from ot.services import get_services

                register_services(get_services())
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

    return functions, pack_aliases, doc_slugs


def load_tool_registry(tools_dir: Path | None = None) -> LoadedTools:
    """Load all tool functions from config tool files with pack support.

    Uses caching based on file modification times to avoid redundant loading.
    Reads `pack` module variable from each tool file to group functions.

    Tool loading strategy:
    - Internal tools (bundled with OneTool from ottools package): Run in-process
      via importlib. These tools have no PEP 723 headers and use ot.* imports.
    - Extension tools (user-created without PEP 723 headers): Run in-process
      with full ot.* access (logging, config, inter-tool calling).
    - Isolated tools (user-created with PEP 723 headers): Run in worker
      subprocesses with isolated dependencies. Fully standalone, no ot imports.

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
    current_files, internal_files, cache_key = _get_tool_files(tools_dir, config)

    if not current_files:
        return LoadedTools(functions={}, packs={})

    cached = _check_cache(cache_key, current_files)
    if cached is not None:
        return cached

    logger.debug(f"Loading tools from {cache_key} ({len(current_files)} files)")

    packs: dict[str, dict[str, Any]] = {}
    mtimes: dict[str, float] = {}

    # Categorize tools: internal (bundled) vs extension (user-created)
    # Internal tools run in-process, extension tools with PEP 723 use workers
    worker_tools, inprocess_tools = categorize_tools(
        list(current_files), internal_files
    )

    secrets = get_secrets()
    config_dict = config.model_dump() if config else {}

    # Inject path context for isolated worker tools
    config_dict["_project_path"] = str(get_effective_cwd())
    if config and config._config_dir:
        config_dict["_config_dir"] = str(config._config_dir)

    worker_funcs, worker_tools_list = _load_worker_tools(
        worker_tools, config_dict, secrets, packs, mtimes
    )
    inprocess_funcs, pack_aliases, doc_slugs = _load_inprocess_tools(
        inprocess_tools, packs, mtimes
    )

    functions = {**worker_funcs, **inprocess_funcs}

    # Register the core 'ot' pack from meta.py (not loaded from tools_dir)
    ot_funcs = _register_ot_pack(packs)
    functions.update(ot_funcs)

    registry = LoadedTools(
        functions=functions,
        packs=packs,
        worker_tools=worker_tools_list,
        extension_tools=[t for t in inprocess_tools if not t.is_internal],
        pack_aliases=pack_aliases,
        doc_slugs=doc_slugs,
    )
    _cache_set(cache_key, (registry, mtimes, time.time()))

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
    from ot.services import OutputPolicy, get_services

    ot_functions = get_ot_pack_functions()
    packs[PACK_NAME] = ot_functions
    get_services().register_output_policy(
        lambda tool_name: OutputPolicy(allow_deflect=False)
        if tool_name in {"ot.result", "ot.help", "ot.tool_info"}
        else None
    )

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


def reset() -> None:
    """Clear tool loader module cache for reload.

    Use this as part of the config reload flow to force tools to be
    reloaded from disk on next access. Also clears the namespace cache
    so stale proxy objects are released.
    """
    from ot.executor import pack_proxy

    _module_cache.clear()
    pack_proxy.reset()
