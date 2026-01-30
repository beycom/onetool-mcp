"""OneTool SDK for extension tool workers.

This package is for USER-CREATED EXTENSION TOOLS that run in isolated
subprocesses with their own dependencies. Extension tools use PEP 723
inline script metadata and the worker pattern.

For INTERNAL TOOLS (shipped with OneTool), use ot.* imports directly:
    from ot.config import get_secret, get_tool_config
    from ot.utils import truncate, batch_execute, safe_request

Extension tool example:

    # /// script
    # requires-python = ">=3.11"
    # dependencies = ["httpx"]
    # ///

    pack = "my_extension"

    from ot_sdk import worker_main, get_secret, log, http, cache

    def search(*, query: str) -> str:
        with log("my_extension.search", query=query) as span:
            api_key = get_secret("MY_API_KEY")
            result = http.get(f"https://api.example.com/search?q={query}")
            span.add(count=len(result))
            return result.text

    if __name__ == "__main__":
        worker_main()

SDK utilities for extensions:

    # Inter-tool communication
    from ot_sdk import get_pack, call_tool
    brave = get_pack("brave")
    results = brave.search(query="test")

    # Batch processing (re-exported from ot.utils)
    from ot_sdk import batch_execute, normalize_items
    items = normalize_items(["a", ("b", "Label B")])
    results = batch_execute(my_func, items, max_workers=5)

    # HTTP utilities
    from ot_sdk import safe_request, api_headers, check_api_key
    headers = api_headers("MY_API_KEY")
    success, result = safe_request(lambda: client.get("/api", headers=headers))

    # Lazy client initialization (re-exported from ot.utils)
    from ot_sdk import lazy_client
    get_client = lazy_client(create_client_func)

    # Dependency declarations (re-exported from ot.utils)
    from ot_sdk import requires_cli, requires_lib
    @requires_cli("rg", install="brew install ripgrep")
    def search_files(pattern: str) -> str: ...
"""

# Re-export context-agnostic utilities from ot.utils
# These work the same in both in-process and worker contexts
from ot.utils import (
    Dependency,
    DepsCheckResult,
    LazyClient,
    batch_execute,
    cache,
    check_cli,
    check_deps,
    check_lib,
    ensure_cli,
    ensure_lib,
    format_batch_results,
    format_error,
    lazy_client,
    normalize_items,
    requires_cli,
    requires_lib,
    run_command,
    truncate,
)

# Extension-specific utilities (worker subprocess communication)
# These use JSON-RPC to communicate with the main onetool process
from ot_sdk.config import get_config, get_secret
from ot_sdk.http import http
from ot_sdk.logging import log
from ot_sdk.packs import call_tool, get_pack
from ot_sdk.paths import (
    expand_path,
    get_ot_dir,
    resolve_cwd_path,
    resolve_ot_path,
    resolve_path,
)

# api_headers/check_api_key use ot_sdk.config.get_secret (JSON-RPC for workers)
from ot_sdk.request import api_headers, check_api_key, safe_request
from ot_sdk.worker import worker_main

__all__ = [
    "Dependency",
    "DepsCheckResult",
    "LazyClient",
    # HTTP (extension-specific for api_headers)
    "api_headers",
    # Batch processing (from ot.utils)
    "batch_execute",
    # Caching (from ot.utils)
    "cache",
    # Packs (extension-specific)
    "call_tool",
    "check_api_key",
    # Dependencies (from ot.utils - decorators and check functions)
    "check_cli",
    "check_deps",
    "check_lib",
    "ensure_cli",
    "ensure_lib",
    # Configuration (extension-specific via JSON-RPC)
    "expand_path",
    "format_batch_results",
    "format_error",
    "get_config",
    "get_ot_dir",
    "get_pack",
    "get_secret",
    "http",
    # Factory (from ot.utils)
    "lazy_client",
    # Logging (extension-specific)
    "log",
    "normalize_items",
    "requires_cli",
    "requires_lib",
    # Paths (extension-specific)
    "resolve_cwd_path",
    "resolve_ot_path",
    "resolve_path",
    # Utils (from ot.utils)
    "run_command",
    "safe_request",
    "truncate",
    # Worker (extension-specific)
    "worker_main",
]
