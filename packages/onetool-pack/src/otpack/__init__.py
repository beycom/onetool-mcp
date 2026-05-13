"""OneTool Pack — standalone infrastructure utilities for OneTool packs.

Provides logging, config, caching, HTTP helpers, paths, text formatting,
batch execution, dependency checks, and path security.

All symbols are importable directly from otpack:

    from otpack import LogSpan, get_tool_config, get_secret, Cache, truncate
    from otpack import resolve_cwd_path, validate_path, lazy_client
    from otpack import batch_execute, check_cli, ensure_lib, is_log_verbose
"""

from otpack.auth import (
    HmacAuthError,
    NonceCache,
    ensure_hmac_key,
    sign_http_message,
    verify_http_message,
)
from otpack.batch import (
    BatchEnvelope,
    BatchError,
    BatchMeta,
    BatchResultItem,
    batch_execute,
    batch_execute_enveloped,
    format_batch_results,
    normalize_items,
)
from otpack.cache import Cache, cache
from otpack.config import (
    configure_standalone,
    get_secret,
    get_tool_config,
    is_log_verbose,
)
from otpack.deps import (
    Dependency,
    DepsCheckResult,
    check_cli,
    check_lib,
    check_secret,
    ensure_cli,
    ensure_lib,
    requires_cli,
    requires_lib,
)
from otpack.factory import LazyClient, lazy_client
from otpack.http import (
    _format_http_error,
    api_headers,
    check_api_key,
    require_api_key,
    safe_request,
)
from otpack.logging import LogEntry, LogSpan
from otpack.paths import expand_path, get_effective_cwd, resolve_cwd_path
from otpack.pathsec import DEFAULT_EXCLUDE_PATTERNS, is_path_excluded, validate_path
from otpack.platform import get_install_hint
from otpack.state import get_state, set_state
from otpack.text import format_error, run_command, truncate

__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "BatchEnvelope",
    "BatchError",
    "BatchMeta",
    "BatchResultItem",
    "Cache",
    "Dependency",
    "DepsCheckResult",
    "HmacAuthError",
    "LazyClient",
    "LogEntry",
    "LogSpan",
    "NonceCache",
    "_format_http_error",
    "api_headers",
    "batch_execute",
    "batch_execute_enveloped",
    "cache",
    "check_api_key",
    "check_cli",
    "check_lib",
    "check_secret",
    "configure_standalone",
    "ensure_cli",
    "ensure_hmac_key",
    "ensure_lib",
    "expand_path",
    "format_batch_results",
    "format_error",
    "get_effective_cwd",
    "get_install_hint",
    "get_secret",
    "get_state",
    "get_tool_config",
    "is_log_verbose",
    "is_path_excluded",
    "lazy_client",
    "normalize_items",
    "require_api_key",
    "requires_cli",
    "requires_lib",
    "resolve_cwd_path",
    "run_command",
    "safe_request",
    "set_state",
    "sign_http_message",
    "truncate",
    "validate_path",
    "verify_http_message",
]
