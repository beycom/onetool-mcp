"""Models for Console metadata, disk-backed bodies, and wire payloads.

Inline payloads carry bounded content on the wire; file-backed payload modes
(`file_ref`, `file_diff_ref`) carry only paths plus size/mime/language so the
Console fetches content on demand through its own file APIs (protocol v1
reserved these modes from the start).

Note: the wire event type `console.message.created` and its payload field
names are frozen by protocol v1 (`openspec/specs/console-outbox/spec.md`).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves this runtime type.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ConsoleKind = Literal[
    "text",
    "markdown",
    "code",
    "diff",
    "json",
    "mermaid",
    "yaml",
    "table",
    "file",
    "image",
]

PayloadMode = Literal["inline", "file_ref", "file_diff_ref"]


class PayloadReference(BaseModel):
    """Reference to Console message payload content."""

    model_config = ConfigDict(extra="forbid")

    mode: PayloadMode
    size_bytes: int = Field(ge=0)
    mime_type: str | None = None
    language: str | None = None
    path: str | None = None
    old_path: str | None = None
    new_path: str | None = None


class BoundedPreview(BaseModel):
    """Bounded model-visible preview for a Console message payload."""

    model_config = ConfigDict(extra="forbid")

    text: str
    truncated: bool
    size_bytes: int = Field(ge=0)
    limit_bytes: int = Field(ge=1)


class MessageMetadata(BaseModel):
    """Metadata row for one Console message."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: ConsoleKind
    metadata: dict[str, str] = Field(default_factory=dict)
    preview_lines: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    payload: PayloadReference
    status: Literal["ready"] = "ready"


class ConsoleMessage(BaseModel):
    """Disk-backed Console message body with its JSON-safe metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    metadata: MessageMetadata
    preview: BoundedPreview | None = None
    inline_payload: Any | None = None


class InstanceMetadata(BaseModel):
    """Metadata for a running MCP process Console instance."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["running"]
    mcp_instance_id: str
    message_count: int = Field(ge=0)
    started_at: datetime
    updated_at: datetime


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
    """Validated request to create an inline Console message."""

    model_config = ConfigDict(extra="forbid")

    kind: ConsoleKind
    metadata: dict[str, str] = Field(default_factory=dict)
    content: str | dict[str, Any] | list[Any]
