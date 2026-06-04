"""Models for the local display service."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves this runtime type.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DisplayKind = Literal[
    "text",
    "markdown",
    "code",
    "file",
    "diff",
    "file_diff",
    "image",
    "json",
    "mermaid",
    "yaml",
    "table",
]

PayloadMode = Literal["inline", "file", "file_diff"]


class PayloadReference(BaseModel):
    """Reference to display payload content."""

    model_config = ConfigDict(extra="forbid")

    mode: PayloadMode
    size_bytes: int = Field(ge=0)
    path: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    mime_type: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def validate_path_for_file_modes(self) -> PayloadReference:
        """Require paths for file-backed payload references."""
        if self.mode == "file" and not self.path:
            raise ValueError("file payload references require path")
        if self.mode == "file_diff" and not (self.path or (self.old_path and self.new_path)):
            raise ValueError("file_diff payload references require path or old_path and new_path")
        return self


class BoundedPreview(BaseModel):
    """Bounded model-visible preview for a display payload."""

    model_config = ConfigDict(extra="forbid")

    text: str
    truncated: bool
    size_bytes: int = Field(ge=0)
    limit_bytes: int = Field(ge=1)


class MessageMetadata(BaseModel):
    """Metadata row for one display message."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: DisplayKind
    metadata: dict[str, str] = Field(default_factory=dict)
    preview_lines: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    payload: PayloadReference
    status: Literal["ready", "preview_unavailable"] = "ready"


class DisplayMessage(BaseModel):
    """Stored display message with optional bounded preview."""

    model_config = ConfigDict(extra="forbid")

    metadata: MessageMetadata
    preview: BoundedPreview | None = None
    inline_payload: Any | None = None


class InstanceMetadata(BaseModel):
    """Metadata for a running MCP process display instance."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["running"]
    mcp_instance_id: str
    message_count: int = Field(ge=0)
    started_at: datetime
    updated_at: datetime


class FocusResult(BaseModel):
    """Result from a focus request."""

    model_config = ConfigDict(extra="forbid")

    id: str
    delivered: bool
    queued: bool


class MessageRead(BaseModel):
    """Metadata-only read response with bounded preview."""

    model_config = ConfigDict(extra="forbid")

    metadata: MessageMetadata
    preview: BoundedPreview | None = None


class MessageList(BaseModel):
    """Paginated metadata-only list response."""

    model_config = ConfigDict(extra="forbid")

    items: list[MessageMetadata]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ShowRequest(BaseModel):
    """Validated request to create a display message."""

    model_config = ConfigDict(extra="forbid")

    kind: DisplayKind
    metadata: dict[str, str] = Field(default_factory=dict)
    content: str | dict[str, Any] | list[Any] | None = None
    path: str | None = None
    old_path: str | None = None
    new_path: str | None = None

    @field_validator("path", "old_path", "new_path")
    @classmethod
    def reject_url_paths(cls, value: str | None) -> str | None:
        """Reject remote and file URL payload paths."""
        if value is None:
            return None
        lowered = value.lower()
        if "://" in lowered or lowered.startswith("file:"):
            raise ValueError("display paths must be local workspace paths, not URLs")
        return value

    @model_validator(mode="after")
    def validate_kind_payload(self) -> ShowRequest:
        """Require the expected payload fields for each V1 kind."""
        if self.kind in {"text", "markdown", "code", "diff", "json", "mermaid", "yaml", "table"}:
            if self.content is None:
                raise ValueError(f"{self.kind} messages require content")
        elif self.kind in {"file", "image"}:
            if not self.path:
                raise ValueError(f"{self.kind} messages require path")
        elif self.kind == "file_diff" and not (self.path or (self.old_path and self.new_path)):
            raise ValueError("file_diff messages require path or old_path and new_path")
        return self
