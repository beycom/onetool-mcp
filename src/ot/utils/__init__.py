"""OneTool utilities.

Provides shared utilities for internal tools:
- Text processing: truncate, format_error, run_command
- Batch processing: batch_execute, normalize_items, format_batch_results
- Caching: cache (TTL-based memoization)
- HTTP utilities: safe_request, api_headers, check_api_key
- Dependencies: check_cli, check_lib, ensure_cli, ensure_lib
- Factory: lazy_client, LazyClient

Extension tools (user-created in .onetool/tools/) can import directly from
ot.* modules for logging, config, and inter-tool calling.
"""

from ot.utils.batch import batch_execute, format_batch_results, normalize_items
from ot.utils.cache import CacheNamespace, cache
from ot.utils.deps import (
    Dependency,
    DepsCheckResult,
    check_cli,
    check_deps,
    check_lib,
    check_secret,
    ensure_cli,
    ensure_lib,
    requires_cli,
    requires_lib,
)
from ot.utils.exceptions import flatten_exception_group
from ot.utils.factory import LazyClient, lazy_client
from ot.utils.format import serialize_result
from ot.utils.http import api_headers, check_api_key, safe_request
from ot.utils.platform import get_install_hint
from ot.utils.sanitize import (
    sanitize_output,
    sanitize_tag_closes,
    sanitize_triggers,
    wrap_external_content,
)
from ot.utils.truncate import format_error, run_command, truncate

__all__ = [
    # Cache
    "CacheNamespace",
    "Dependency",
    # Dependencies
    "DepsCheckResult",
    # Factory
    "LazyClient",
    # HTTP
    "api_headers",
    # Batch processing
    "batch_execute",
    "cache",
    "check_api_key",
    "check_cli",
    "check_deps",
    "check_lib",
    "check_secret",
    "ensure_cli",
    "ensure_lib",
    # Existing utilities
    "flatten_exception_group",
    "format_batch_results",
    # Truncate
    "format_error",
    "get_install_hint",
    "lazy_client",
    "normalize_items",
    "requires_cli",
    "requires_lib",
    "run_command",
    "safe_request",
    # Sanitization
    "sanitize_output",
    "sanitize_tag_closes",
    "sanitize_triggers",
    "serialize_result",
    "truncate",
    "wrap_external_content",
]
