"""OneTool utilities.

Provides shared utilities for internal tools:
- Text processing: truncate, format_error, run_command
- Batch processing: batch_execute, normalize_items, format_batch_results
- Caching: cache (TTL-based memoization)
- HTTP utilities: safe_request, api_headers, check_api_key
- Dependencies: check_cli, check_lib, ensure_cli, ensure_lib
- Factory: lazy_client, LazyClient
- Path security: validate_path, is_path_excluded

Extension tools (user-created in .onetool/tools/) can import directly from
ot.* modules for logging, config, and inter-tool calling.
"""

from ot.utils.async_bridge import run_coro_sync
from ot.utils.batch import (
    BatchEnvelope,
    BatchError,
    BatchMeta,
    BatchResultItem,
    batch_execute,
    batch_execute_enveloped,
    format_batch_results,
    normalize_items,
)
from ot.utils.cache import Cache, cache
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
from ot.utils.duration import parse_duration
from ot.utils.exceptions import flatten_exception_group
from ot.utils.factory import LazyClient, lazy_client
from ot.utils.format import serialize_result
from ot.utils.http import api_headers, check_api_key, require_api_key, safe_request
from ot.utils.pathsec import DEFAULT_EXCLUDE_PATTERNS, is_path_excluded, validate_path
from ot.utils.platform import get_install_hint
from ot.utils.sanitize import (
    sanitize_output,
    sanitize_tag_closes,
    sanitize_triggers,
    wrap_external_content,
)
from ot.utils.sqlite_pool import SqlitePool, open_db_connection
from ot.utils.truncate import format_error, run_command, truncate

__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "BatchEnvelope",
    "BatchError",
    "BatchMeta",
    "BatchResultItem",
    "Cache",
    "Dependency",
    "DepsCheckResult",
    "LazyClient",
    "SqlitePool",
    "api_headers",
    "batch_execute",
    "batch_execute_enveloped",
    "cache",
    "check_api_key",
    "check_cli",
    "check_deps",
    "check_lib",
    "check_secret",
    "ensure_cli",
    "ensure_lib",
    "flatten_exception_group",
    "format_batch_results",
    "format_error",
    "get_install_hint",
    "is_path_excluded",
    "lazy_client",
    "normalize_items",
    "open_db_connection",
    "parse_duration",
    "require_api_key",
    "requires_cli",
    "requires_lib",
    "run_command",
    "run_coro_sync",
    "safe_request",
    "sanitize_output",
    "sanitize_tag_closes",
    "sanitize_triggers",
    "serialize_result",
    "truncate",
    "validate_path",
    "wrap_external_content",
]
