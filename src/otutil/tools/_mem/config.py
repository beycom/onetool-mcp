"""Pack configuration and path validation for mem."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ot.config.routing import DirectModelId, ReasoningEffort  # noqa: TC001
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

    model_config = ConfigDict(extra="forbid")

    model: DirectModelId | None = Field(
        default=None, description="Direct model override"
    )
    effort: ReasoningEffort | None = Field(
        default=None, description="Reasoning effort override"
    )
    db_path: str = Field(
        default="data/mem/default.db",
        description="Path to memory SQLite database (relative to .onetool/)",
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
    embeddings_enabled: bool = Field(
        default=False,
        description="Enable generation through the independent embeddings route",
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
