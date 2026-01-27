"""OneTool SDK for external tool workers.

This package provides utilities for building persistent worker tools that run
in isolated subprocesses with their own dependencies.

Example tool:

    # /// script
    # requires-python = ">=3.11"
    # dependencies = ["httpx"]
    # ///

    from ot_sdk import worker_main, get_secret, log, http, cache

    def search(*, query: str) -> str:
        with log("my_tool.search", query=query) as span:
            api_key = get_secret("MY_API_KEY")
            result = http.get(f"https://api.example.com/search?q={query}")
            span.add(count=len(result))
            return result.text

    if __name__ == "__main__":
        worker_main()

New SDK utilities (v0.3+):

    # Inter-tool communication
    from ot_sdk import get_pack, call_tool
    brave = get_pack("brave")
    results = brave.search(query="test")

    # Batch processing
    from ot_sdk import batch_execute, normalize_items
    items = normalize_items(["a", ("b", "Label B")])
    results = batch_execute(my_func, items, max_workers=5)

    # HTTP utilities
    from ot_sdk import safe_request, api_headers, check_api_key
    headers = api_headers("MY_API_KEY")
    success, result = safe_request(lambda: client.get("/api", headers=headers))

    # Lazy client initialization
    from ot_sdk import lazy_client
    get_client = lazy_client(create_client_func)

    # Dependency declarations
    from ot_sdk import requires_cli, requires_lib, check_deps
    @requires_cli("rg", install="brew install ripgrep")
    def search_files(pattern: str) -> str: ...
"""

from ot_sdk.batch import batch_execute, format_batch_results, normalize_items
from ot_sdk.cache import cache
from ot_sdk.config import get_config, get_secret
from ot_sdk.deps import (
    DepsCheckResult,
    Dependency,
    check_cli,
    check_deps,
    check_lib,
    ensure_cli,
    ensure_lib,
    requires_cli,
    requires_lib,
)
from ot_sdk.factory import LazyClient, lazy_client
from ot_sdk.http import http
from ot_sdk.logging import log
from ot_sdk.packs import call_tool, get_pack
from ot_sdk.paths import (
    expand_path,
    get_config_path,
    get_ot_dir,
    get_project_path,
    resolve_cwd_path,
    resolve_ot_path,
    resolve_path,
)
from ot_sdk.request import api_headers, check_api_key, safe_request
from ot_sdk.utils import format_error, run_command, truncate
from ot_sdk.worker import worker_main

__all__ = [
    # Batch processing
    "batch_execute",
    "format_batch_results",
    "normalize_items",
    # Caching
    "cache",
    # Configuration
    "expand_path",
    "format_error",
    "get_config",
    "get_config_path",
    "get_ot_dir",
    "get_project_path",
    "get_secret",
    # Dependencies
    "check_cli",
    "check_deps",
    "check_lib",
    "DepsCheckResult",
    "Dependency",
    "ensure_cli",
    "ensure_lib",
    "requires_cli",
    "requires_lib",
    # Factory
    "lazy_client",
    "LazyClient",
    # HTTP
    "api_headers",
    "check_api_key",
    "http",
    "safe_request",
    # Logging
    "log",
    # Packs
    "call_tool",
    "get_pack",
    # Paths
    "resolve_cwd_path",
    "resolve_ot_path",
    "resolve_path",
    # Utils
    "run_command",
    "truncate",
    "worker_main",
]
