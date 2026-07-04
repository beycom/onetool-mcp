"""Pack configuration and path validation for mem."""
from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ot.logging.redact import SECRET_PATTERNS as _BUILTIN_REDACTION_PATTERNS
from otpack import DEFAULT_EXCLUDE_PATTERNS, get_tool_config, validate_path

if TYPE_CHECKING:
    from pathlib import Path

_builtins_list = builtins.list

VALID_CATEGORIES = {"rule", "context", "decision", "mistake", "discovery", "note"}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    db_path: str = Field(
        default="data/mem/default.db",
        description="Path to memory SQLite database (relative to .onetool/)",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL for embeddings (empty = inherit from top-level llm config)",
    )
    dimensions: int = Field(
        default=1536,
        description="Embedding dimensions (must match model)",
    )
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default maximum search results",
    )
    search_extract: int = Field(
        default=200,
        ge=0,
        description="Character limit for content extract in search results (0 = full content)",
    )
    redaction_enabled: bool = Field(
        default=True,
        description="Enable secret/PII redaction on write",
    )
    redaction_patterns: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns for redaction (beyond built-in defaults)",
    )
    tags_whitelist: list[str] = Field(
        default_factory=list,
        description="Allowed tag prefixes (empty = no restriction). Supports wildcard: 'project/*'",
    )
    decay_half_life_days: int = Field(
        default=30,
        ge=1,
        description="Half-life in days for importance decay",
    )
    allowed_file_dirs: list[str] = Field(
        default_factory=list,
        description="Allowed directories for file read/write (empty = cwd only)",
    )
    exclude_file_patterns: list[str] = Field(
        default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy(),
        description="Path patterns to exclude from file operations",
    )
    max_embedding_tokens: int = Field(
        default=8191,
        ge=1,
        description="Max tokens for embedding input (text-embedding-3-small limit: 8191)",
    )
    embeddings_enabled: bool = Field(
        default=False,
        description="Enable embedding generation for semantic search (requires OPENAI_API_KEY)",
    )
    embeddings_async: bool = Field(
        default=True,
        description="Generate embeddings asynchronously (write returns immediately)",
    )


def _get_config() -> Config:
    """Get mem pack configuration."""
    return get_tool_config("mem", Config)


def _validate_file_path(
    path: str, *, must_exist: bool = True
) -> tuple[Path | None, str | None]:
    """Validate path for mem tool file operations."""
    cfg = _get_config()
    return validate_path(
        path,
        must_exist=must_exist,
        allowed_dirs=cfg.allowed_file_dirs or None,
        exclude_patterns=cfg.exclude_file_patterns,
    )


__all__ = [
    "VALID_CATEGORIES",
    "_BUILTIN_REDACTION_PATTERNS",
    "Config",
    "_builtins_list",
    "_get_config",
    "_validate_file_path",
]
