"""Models and configuration for handoff runtime state."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from importlib import resources
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal[
    "submitted",
    "running",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
    "abandoned",
    "cleared",
]
TERMINAL_STATUSES: set[str] = {
    "completed",
    "failed",
    "cancelled",
    "abandoned",
    "cleared",
}

def default_worker_prompt() -> str:
    """Load the bundled default handoff worker prompt."""
    return resources.files("ot.handoff").joinpath(
        "default_worker_prompt.md"
    ).read_text(encoding="utf-8")


class StrictConfig(BaseModel):
    """Base model that rejects unsupported config values."""

    model_config = ConfigDict(extra="forbid")


class AppServerConfig(StrictConfig):
    """Codex app-server command and readiness settings."""

    command: str = Field(
        default="codex app-server --listen stdio://",
        description="Codex app-server command. Must use stdio transport.",
    )
    startup_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=120,
        description="Seconds to wait for Codex app-server startup.",
    )
    ready_check_cache_seconds: int = Field(
        default=30,
        ge=0,
        le=3600,
        description="Seconds to cache app-server/direct API readiness checks.",
    )


class DefaultsConfig(StrictConfig):
    """Default worker model and prompt settings."""

    model: str = Field(default="gpt-5.3-codex", description="Default Codex model.")
    reasoning_effort: str = Field(
        default="low", description="Default reasoning effort."
    )
    timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Default worker task timeout in seconds.",
    )
    worker_prompt: str = Field(
        default_factory=default_worker_prompt,
        description="Worker prompt template supporting {task} and {context}.",
    )


class LimitsConfig(StrictConfig):
    """Runtime bounds for latency and memory protection."""

    max_workers: int = Field(
        default=1, ge=1, le=8, description="Concurrent workers."
    )
    max_queue_depth: int = Field(
        default=10, ge=1, le=100, description="Outstanding tasks."
    )
    max_check_wait_seconds: int = Field(
        default=10,
        ge=0,
        le=120,
        description="Maximum blocking check wait.",
    )
    max_raw_log_bytes: int = Field(
        default=200_000,
        ge=0,
        le=10_000_000,
        description="Maximum raw app-server event bytes retained per task.",
    )
    max_remaining_ids_returned: int = Field(
        default=20,
        ge=0,
        le=500,
        description="Maximum outstanding ids returned by check.",
    )


class RuntimeConfig(StrictConfig):
    """Runtime file locations under OneTool-owned storage."""

    state_path: str = Field(
        default="runtime/handoff/state.json", description="State JSON path."
    )
    index_path: str = Field(
        default="runtime/handoff/index.jsonl", description="Index JSONL path."
    )
    result_dir: str = Field(
        default="runtime/handoff/results", description="Result directory."
    )
    raw_log_dir: str = Field(
        default="runtime/handoff/raw", description="Raw log directory."
    )
    raw_log_enabled: bool = Field(
        default=True, description="Whether raw logs are retained."
    )
    raw_log_flush: Literal["on_completion"] = Field(
        default="on_completion",
        description="Raw log flush mode. Only on_completion is supported.",
    )
    dedupe_window_seconds: int = Field(
        default=30,
        ge=0,
        le=3600,
        description="Duplicate outstanding submission suppression window.",
    )


class CleanupConfig(StrictConfig):
    """Age-based runtime cleanup settings."""

    enabled: bool = Field(
        default=True, description="Enable cleanup during runtime initialization."
    )
    max_age_days: int = Field(
        default=14, ge=1, le=3650, description="Terminal artifact max age."
    )


class Config(StrictConfig):
    """Handoff pack configuration."""

    enabled: bool = Field(default=True, description="Enable the handoff pack.")
    app_server: AppServerConfig = Field(default_factory=AppServerConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)


@dataclass
class HandoffPaths:
    """Resolved runtime paths."""

    state_path: Path
    index_path: Path
    result_dir: Path
    raw_log_dir: Path


@dataclass
class TaskRecord:
    """In-memory and persisted handoff task state."""

    id: str
    task: str
    context: str
    model: str
    reasoning_effort: str
    timeout_seconds: int
    prompt: str
    cwd: str
    dedupe_key: str
    status: TaskStatus = "submitted"
    summary: str = ""
    result_path: str | None = None
    raw_log_path: str | None = None
    runner_id: str | None = None
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    checked_at: float | None = None

    @property
    def terminal(self) -> bool:
        """Whether this task has a terminal status."""
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> dict[str, Any]:
        """Serialize the record to JSON-compatible data."""
        return {
            "id": self.id,
            "task": self.task,
            "context": self.context,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds,
            "prompt": self.prompt,
            "cwd": self.cwd,
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "summary": self.summary,
            "result_path": self.result_path,
            "raw_log_path": self.raw_log_path,
            "runner_id": self.runner_id,
            "error": self.error,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "checked_at": self.checked_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        """Load a record from persisted JSON-compatible data."""
        return cls(**data)


def make_dedupe_key(
    *, task: str, context: str, model: str, reasoning_effort: str
) -> str:
    """Return a stable dedupe key for an outstanding submission."""
    joined = "\0".join([task.strip(), context.strip(), model, reasoning_effort])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
