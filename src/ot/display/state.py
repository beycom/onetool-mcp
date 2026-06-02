"""In-memory state for the local display service."""

from __future__ import annotations

import json
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import unified_diff
from threading import Lock
from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import uuid4

from ot.display.models import (
    BoundedPreview,
    DisplayMessage,
    FocusResult,
    InstanceMetadata,
    MessageList,
    MessageMetadata,
    MessageRead,
    PayloadReference,
    ShowRequest,
)
from ot.paths import get_effective_cwd

if TYPE_CHECKING:
    from pathlib import Path

MAX_MESSAGES = 1000
PREVIEW_LIMIT_BYTES = 64 * 1024
MAX_INLINE_LIST_ITEMS = 500
MAX_DIFF_INPUT_BYTES = 1 * 1024 * 1024


@dataclass
class DisplayInstance:
    """State for one running MCP process."""

    id: str
    token: str
    started_at: datetime
    updated_at: datetime
    messages: OrderedDict[str, DisplayMessage] = field(default_factory=OrderedDict)
    focus_target: str | None = None
    event_queue: deque[dict[str, str]] = field(default_factory=deque)
    has_event_client: bool = False


class DisplayState:
    """Process-local display state."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._instance: DisplayInstance | None = None

    def get_or_create_instance(self) -> DisplayInstance:
        """Return the current process instance, creating it if needed."""
        with self._lock:
            if self._instance is None:
                now = _utcnow()
                self._instance = DisplayInstance(
                    id=f"mcp-{uuid4().hex}",
                    token=uuid4().hex,
                    started_at=now,
                    updated_at=now,
                )
            return self._instance

    def status(self, *, base_url: str) -> InstanceMetadata:
        """Return current instance metadata."""
        instance = self.get_or_create_instance()
        with self._lock:
            return _instance_metadata(instance, base_url=base_url)

    def add_message(self, *, request: ShowRequest) -> MessageMetadata:
        """Add a validated display message to the current instance."""
        instance = self.get_or_create_instance()
        now = _utcnow()
        message_id = f"msg-{uuid4().hex}"
        payload, preview, inline_payload = _build_payload(request)
        metadata = MessageMetadata(
            id=message_id,
            kind=request.kind,
            title=request.title,
            summary=request.summary or _default_summary(preview),
            source=request.source,
            expand=request.expand,
            preview_lines=_preview_line_count(preview),
            created_at=now,
            updated_at=now,
            payload=payload,
        )
        message = DisplayMessage(
            metadata=metadata,
            preview=preview,
            inline_payload=inline_payload,
        )
        with self._lock:
            instance.messages[message_id] = message
            while len(instance.messages) > MAX_MESSAGES:
                instance.messages.popitem(last=False)
            instance.updated_at = now
            instance.event_queue.append({"type": "message", "id": message_id})
        return metadata

    def read_message(self, *, id: str) -> MessageRead | None:
        """Read one message by ID from the current instance."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
            if message is None:
                return None
            return MessageRead(metadata=message.metadata, preview=message.preview)

    def payload_view(self, *, id: str, base_url: str) -> dict[str, object] | None:
        """Return a browser-only payload view for lazy row expansion."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
            if message is None:
                return None
            metadata = message.metadata
            payload = metadata.payload
            token = instance.token
            instance_id = instance.id
        result: dict[str, object] = {
            "metadata": metadata.model_dump(mode="json"),
            "preview": message.preview.model_dump(mode="json") if message.preview else None,
        }
        if payload.mode == "inline":
            result["content"] = _bounded_inline_payload(message.inline_payload)
        elif payload.path is not None:
            encoded_path = quote(payload.path)
            result["file_url"] = (
                f"{base_url}/api/instances/{instance_id}/preview"
                f"?token={token}&path={encoded_path}"
            )
            result["open_url"] = (
                f"{base_url}/api/instances/{instance_id}/open"
                f"?token={token}"
            )
            if metadata.kind == "image":
                result["image_url"] = (
                    f"{base_url}/api/instances/{instance_id}/asset"
                    f"?token={token}&path={encoded_path}"
                )
        return result

    def list_messages(
        self,
        *,
        limit: int,
        offset: int,
        kind: str | None = None,
        source: str | None = None,
    ) -> MessageList:
        """List message metadata with optional lightweight filters."""
        instance = self.get_or_create_instance()
        with self._lock:
            items = [message.metadata for message in instance.messages.values()]
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if source is not None:
            items = [item for item in items if item.source == source]
        return MessageList(
            items=items[offset : offset + limit],
            total=len(items),
            offset=offset,
            limit=limit,
        )

    def focus(self, *, id: str) -> FocusResult | None:
        """Queue or deliver a focus event for one message."""
        instance = self.get_or_create_instance()
        with self._lock:
            if id not in instance.messages:
                return None
            instance.focus_target = id
            instance.updated_at = _utcnow()
            delivered = instance.has_event_client
            instance.event_queue.append({"type": "focus", "id": id})
            return FocusResult(id=id, delivered=delivered, queued=not delivered)

    def poll_events(self, *, instance_id: str, token: str) -> list[dict[str, str]] | None:
        """Return queued events for an authorized instance."""
        instance = self.get_or_create_instance()
        with self._lock:
            if instance.id != instance_id or instance.token != token:
                return None
            instance.has_event_client = True
            events = list(instance.event_queue)
            instance.event_queue.clear()
            if instance.focus_target is not None:
                events.append({"type": "focus", "id": instance.focus_target})
            return events

    def authorize(self, *, instance_id: str, token: str | None) -> bool:
        """Return whether an instance route token is valid."""
        instance = self.get_or_create_instance()
        return instance.id == instance_id and token == instance.token


STATE = DisplayState()


def allowed_roots() -> list[Path]:
    """Return workspace roots allowed for display file preview."""
    return [get_effective_cwd().resolve()]


def resolve_allowed_path(path: str) -> Path:
    """Resolve a user path and reject paths outside allowed roots."""
    candidate = (get_effective_cwd() / path).resolve()
    if any(candidate == root or root in candidate.parents for root in allowed_roots()):
        return candidate
    raise PermissionError("path is outside allowed workspace roots")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _instance_metadata(instance: DisplayInstance, *, base_url: str) -> InstanceMetadata:
    return InstanceMetadata(
        status="running",
        mcp_instance_id=instance.id,
        url=f"{base_url}/instances/{instance.id}?token={instance.token}",
        message_count=len(instance.messages),
        started_at=instance.started_at,
        updated_at=instance.updated_at,
    )


def _build_payload(
    request: ShowRequest,
) -> tuple[PayloadReference, BoundedPreview | None, object | None]:
    if request.kind in {"file", "image"}:
        path = resolve_allowed_path(request.path or "")
        size = path.stat().st_size
        preview = _file_preview(path) if request.kind == "file" else None
        return (
            PayloadReference(
                mode="file",
                path=str(path),
                size_bytes=size,
                mime_type=request.mime_type,
                language=request.language,
            ),
            preview,
            None,
        )
    if request.kind == "file_diff":
        if request.path:
            path = resolve_allowed_path(request.path)
            size = path.stat().st_size
            data = _read_bounded_file(path, limit=PREVIEW_LIMIT_BYTES)
            preview = BoundedPreview(
                text=data.decode("utf-8", errors="replace"),
                truncated=size > PREVIEW_LIMIT_BYTES,
                size_bytes=size,
                limit_bytes=PREVIEW_LIMIT_BYTES,
            )
            return (
                PayloadReference(mode="file_diff", path=str(path), size_bytes=size),
                preview,
                None,
            )
        old_path = resolve_allowed_path(request.old_path or "")
        new_path = resolve_allowed_path(request.new_path or "")
        diff_text = _file_diff(old_path, new_path)
        encoded = diff_text.encode("utf-8")
        return (
            PayloadReference(
                mode="inline",
                path=f"{old_path}..{new_path}",
                size_bytes=len(encoded),
                language="diff",
            ),
            BoundedPreview(
                text=encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace"),
                truncated=len(encoded) > PREVIEW_LIMIT_BYTES,
                size_bytes=len(encoded),
                limit_bytes=PREVIEW_LIMIT_BYTES,
            ),
            diff_text,
        )
    text = _content_to_text(request.content)
    encoded = text.encode("utf-8")
    preview = BoundedPreview(
        text=encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace"),
        truncated=len(encoded) > PREVIEW_LIMIT_BYTES,
        size_bytes=len(encoded),
        limit_bytes=PREVIEW_LIMIT_BYTES,
    )
    return (
        PayloadReference(
            mode="inline",
            size_bytes=len(encoded),
            mime_type=request.mime_type,
            language=request.language,
        ),
        preview,
        _bounded_inline_payload(request.content),
    )


def _file_preview(path: Path) -> BoundedPreview:
    size = path.stat().st_size
    head = _read_bounded_file(path, limit=PREVIEW_LIMIT_BYTES)
    return BoundedPreview(
        text=head.decode("utf-8", errors="replace"),
        truncated=size > PREVIEW_LIMIT_BYTES,
        size_bytes=size,
        limit_bytes=PREVIEW_LIMIT_BYTES,
    )


def _content_to_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, indent=2, sort_keys=True)


def _preview_line_count(preview: BoundedPreview | None) -> int:
    if preview is None or preview.text == "":
        return 0
    return preview.text.count("\n") + 1


def _bounded_inline_payload(content: object) -> object:
    if isinstance(content, list):
        return content[:MAX_INLINE_LIST_ITEMS]
    if isinstance(content, str):
        encoded = content.encode("utf-8")
        if len(encoded) <= PREVIEW_LIMIT_BYTES:
            return content
        return encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace")
    if isinstance(content, dict):
        text = json.dumps(content, indent=2, sort_keys=True)
        encoded = text.encode("utf-8")
        if len(encoded) <= PREVIEW_LIMIT_BYTES:
            return content
        return {
            "truncated": True,
            "preview": encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace"),
            "size_bytes": len(encoded),
            "limit_bytes": PREVIEW_LIMIT_BYTES,
        }
    return content


def _file_diff(old_path: Path, new_path: Path) -> str:
    old_size = old_path.stat().st_size
    new_size = new_path.stat().st_size
    if old_size > MAX_DIFF_INPUT_BYTES or new_size > MAX_DIFF_INPUT_BYTES:
        return (
            f"Diff preview skipped: input file exceeds {MAX_DIFF_INPUT_BYTES} byte limit.\n"
            f"old={old_path} ({old_size} bytes)\n"
            f"new={new_path} ({new_size} bytes)"
        )
    old_lines = old_path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = new_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(
        unified_diff(
            old_lines,
            new_lines,
            fromfile=str(old_path),
            tofile=str(new_path),
            lineterm="",
        )
    )


def _read_bounded_file(path: Path, *, limit: int) -> bytes:
    with path.open("rb") as stream:
        return stream.read(limit)


def _default_summary(preview: BoundedPreview | None) -> str | None:
    if preview is None:
        return None
    first_line = preview.text.strip().splitlines()
    if not first_line:
        return None
    return first_line[0][:160]
