"""OneTool Pack — standalone infrastructure utilities for OneTool packs.

Provides logging, config, caching, HTTP helpers, paths, text formatting,
batch execution, dependency checks, path security, and embedding
infrastructure (tokenization, serialization, RRF fusion, EmbeddingClient).

All symbols are importable directly from otpack:

    from otpack import LogSpan, get_tool_config, get_secret, Cache, truncate
    from otpack import resolve_cwd_path, validate_path, lazy_client
    from otpack import batch_execute, check_cli, ensure_lib, is_log_verbose
"""

from otpack.auth import (
    HmacAuthError,
    NonceCache,
    ensure_hmac_key,
    ensure_hmac_key_file,
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
    validate_batch_retry_controls,
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
from otpack.embedding import (
    MODEL_NATIVE_DIMS,
    TOKEN_SAFETY_MARGIN,
    EmbeddingClient,
    chunk_text_by_tokens,
    cosine_similarity_blobs,
    deserialize_embedding,
    dimensions_param,
    get_tiktoken_encoding,
    rrf_merge,
    serialize_embedding,
)
from otpack.factory import LazyClient, lazy_client
from otpack.http import (
    _format_http_error,
    api_headers,
    check_api_key,
    create_json_http_client,
    require_api_key,
    safe_request,
)
from otpack.logging import LogEntry, LogSpan
from otpack.paths import (
    expand_path,
    get_effective_cwd,
    get_project_artifact_dir,
    get_project_state_dir,
    resolve_cwd_path,
)
from otpack.pathsec import DEFAULT_EXCLUDE_PATTERNS, is_path_excluded, validate_path
from otpack.platform import get_install_hint
from otpack.text import (
    extract_structured_data,
    format_error,
    format_sources,
    parse_frontmatter,
    run_command,
    truncate,
)
from otpack.validate import validate_choice, validate_int_range

__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "MODEL_NATIVE_DIMS",
    "TOKEN_SAFETY_MARGIN",
    "BatchEnvelope",
    "BatchError",
    "BatchMeta",
    "BatchResultItem",
    "Cache",
    "Dependency",
    "DepsCheckResult",
    "EmbeddingClient",
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
    "chunk_text_by_tokens",
    "configure_standalone",
    "cosine_similarity_blobs",
    "create_json_http_client",
    "deserialize_embedding",
    "dimensions_param",
    "ensure_cli",
    "ensure_hmac_key",
    "ensure_hmac_key_file",
    "ensure_lib",
    "expand_path",
    "extract_structured_data",
    "format_batch_results",
    "format_error",
    "format_sources",
    "get_effective_cwd",
    "get_install_hint",
    "get_project_artifact_dir",
    "get_project_state_dir",
    "get_secret",
    "get_tiktoken_encoding",
    "get_tool_config",
    "is_log_verbose",
    "is_path_excluded",
    "lazy_client",
    "normalize_items",
    "parse_frontmatter",
    "require_api_key",
    "requires_cli",
    "requires_lib",
    "resolve_cwd_path",
    "rrf_merge",
    "run_command",
    "safe_request",
    "serialize_embedding",
    "sign_http_message",
    "truncate",
    "validate_batch_retry_controls",
    "validate_choice",
    "validate_int_range",
    "validate_path",
    "verify_http_message",
]
