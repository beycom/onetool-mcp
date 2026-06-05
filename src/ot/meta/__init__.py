"""OneTool core introspection tools (ot pack).

Provides tool discovery and management under the unified `ot` pack.
These are core introspection functions, not external tools, so they
live in the core package rather than tools_dir.

Functions:
    ot.tools() - List tools
    ot.tool_info() - Detailed info for a tool
    ot.packs() - List packs
    ot.pack_info() - Detailed info for a pack
    ot.aliases() - List alias definitions
    ot.snippets() - List snippet definitions
    ot.snippet_info() - Detailed info for a snippet
    ot.config() - Show configuration summary
    ot.status() - Check runtime status
    ot.stats() - Get runtime statistics
    ot.result() - Query stored large output results
    ot.reload() - Force configuration reload
"""

from __future__ import annotations

import time
from typing import Any

from ot import __version__
from ot.logging import LogSpan
from ot.meta._config_health import config, reload, status
from ot.meta._constants import PACK_NAME, resolve_ot_path
from ot.meta._debug import debug
from ot.meta._discovery import pack_info, packs, servers, tool_info, tools
from ot.meta._help import help
from ot.meta._help_formatting import (
    _format_general_help,
    _format_search_results,
    _format_tool_help,
    _fuzzy_match,
    _get_doc_url,
)
from ot.meta._introspection import aliases, snippet_info, snippets
from ot.meta._runtime import connect_admin, meta, set_meta
from ot.meta._server_mgmt import security, server, skills
from ot.meta._stats import result, stats
from ot.meta._tool_discovery import (
    _build_proxy_tool_info,
    _parse_input_schema,
    _schema_to_signature,
    _truncate,
)

# Track when module was first loaded (OneTool start time)
_MODULE_LOAD_TIME = time.time()

# Alias for cleaner logging calls in this module
log = LogSpan

__all__ = [
    "PACK_NAME",
    "_build_proxy_tool_info",
    "_format_general_help",
    "_format_search_results",
    "_format_tool_help",
    "_fuzzy_match",
    "_get_doc_url",
    "_parse_input_schema",
    "_schema_to_signature",
    "_truncate",
    "aliases",
    "config",
    "connect_admin",
    "debug",
    "get_ot_pack_functions",
    "help",
    "meta",
    "pack_info",
    "packs",
    "reload",
    "resolve_ot_path",
    "result",
    "security",
    "server",
    "servers",
    "set_meta",
    "skills",
    "snippet_info",
    "snippets",
    "stats",
    "status",
    "tool_info",
    "tools",
    "version",
]


def version() -> str:
    """Return OneTool version string.

    Returns:
        Version string (e.g., "1.0.0")

    Example:
        ot.version()
    """
    return __version__


def get_ot_pack_functions() -> dict[str, Any]:
    """Get all ot pack functions for registration.

    Returns:
        Dict mapping function names to callables
    """
    return {
        "tools": tools,
        "tool_info": tool_info,
        "packs": packs,
        "pack_info": pack_info,
        "server": server,
        "servers": servers,
        "aliases": aliases,
        "snippets": snippets,
        "snippet_info": snippet_info,
        "skills": skills,
        "config": config,
        "connect_admin": connect_admin,
        "debug": debug,
        "help": help,
        "meta": meta,
        "result": result,
        "security": security,
        "stats": stats,
        "status": status,
        "set_meta": set_meta,
        "reload": reload,
        "version": version,
    }
