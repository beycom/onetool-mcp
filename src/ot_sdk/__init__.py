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
"""

from ot_sdk.cache import cache
from ot_sdk.config import get_config, get_secret
from ot_sdk.http import http
from ot_sdk.logging import log
from ot_sdk.paths import (
    expand_path,
    get_config_path,
    get_ot_dir,
    get_project_path,
    resolve_cwd_path,
    resolve_ot_path,
    resolve_path,
)
from ot_sdk.utils import format_error, run_command, truncate
from ot_sdk.worker import worker_main

__all__ = [
    "cache",
    "expand_path",
    "format_error",
    "get_config",
    "get_config_path",
    "get_ot_dir",
    "get_project_path",
    "get_secret",
    "http",
    "log",
    "resolve_cwd_path",
    "resolve_ot_path",
    "resolve_path",
    "run_command",
    "truncate",
    "worker_main",
]
