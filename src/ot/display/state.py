"""Process-local state for the local display service."""

from __future__ import annotations

import json
import shutil
from collections import OrderedDict, deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import unified_diff
from secrets import token_hex
from threading import Lock
from typing import TYPE_CHECKING
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
from ot.paths import get_effective_cwd, get_project_state_dir
from ot.utils.session import get_session_dir

if TYPE_CHECKING:
    from pathlib import Path

HOT_MESSAGE_WINDOW = 1000
MAX_MESSAGE_RECORDS = 5000
MAX_EVENT_QUEUE = 1000
PREVIEW_LIMIT_BYTES = 64 * 1024
MAX_INLINE_LIST_ITEMS = 500
MAX_DIFF_INPUT_BYTES = 1 * 1024 * 1024
MESSAGE_ID_HEX_CHARS = 12


@dataclass
class DisplayInstance:
    """State for one running MCP process."""

    id: str
    token: str
    started_at: datetime
    updated_at: datetime
    messages: OrderedDict[str, DisplayMessage] = field(default_factory=OrderedDict)
    message_ids: list[str] = field(default_factory=list)
    message_id_set: set[str] = field(default_factory=set)
    cache_dir: Path | None = None
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
                instance_id = f"mcp-{uuid4().hex}"
                self._instance = DisplayInstance(
                    id=instance_id,
                    token=uuid4().hex,
                    started_at=now,
                    updated_at=now,
                    cache_dir=_cache_dir_for_instance(instance_id),
                )
            return self._instance

    def status(self) -> InstanceMetadata:
        """Return current instance metadata."""
        instance = self.get_or_create_instance()
        with self._lock:
            return _instance_metadata(instance)

    def add_message(self, *, request: ShowRequest) -> MessageMetadata:
        """Add a validated display message to the current instance."""
        instance = self.get_or_create_instance()
        now = _utcnow()
        payload, preview, inline_payload = _build_payload(request)
        expired_ids: list[str] = []
        with self._lock:
            message_id = _new_message_id(instance.message_id_set)
            metadata = MessageMetadata(
                id=message_id,
                kind=request.kind,
                metadata=_message_metadata(request=request),
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
            _write_cached_message(instance, message)
            instance.messages[message_id] = message
            instance.message_ids.append(message_id)
            instance.message_id_set.add(message_id)
            while len(instance.messages) > HOT_MESSAGE_WINDOW:
                instance.messages.popitem(last=False)
            max_message_records = _max_message_records()
            while len(instance.message_ids) > max_message_records:
                expired_id = instance.message_ids.pop(0)
                instance.messages.pop(expired_id, None)
                instance.message_id_set.discard(expired_id)
                expired_ids.append(expired_id)
            instance.updated_at = now
            _append_event(instance, {"type": "message", "id": message_id})
        for expired_id in expired_ids:
            _delete_cached_message(instance, expired_id)
        return metadata

    def read_message(self, *, id: str) -> MessageRead | None:
        """Read one message by ID from the current instance."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
            known_id = id in instance.message_id_set
        if message is None and known_id:
            message = _read_cached_message(instance, id)
        if message is None:
            return None
        return MessageRead(metadata=message.metadata, preview=message.preview)

    def payload_view(self, *, id: str) -> dict[str, object] | None:
        """Return a browser-only payload view for lazy row expansion."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
            known_id = id in instance.message_id_set
        if message is None and known_id:
            message = _read_cached_message(instance, id)
        if message is None:
            return None
        metadata = message.metadata
        payload = metadata.payload
        result: dict[str, object] = {
            "metadata": metadata.model_dump(mode="json"),
            "preview": message.preview.model_dump(mode="json") if message.preview else None,
        }
        if payload.mode == "inline" or payload.path is None:
            result["content"] = _bounded_inline_payload(message.inline_payload)
        elif payload.path is not None:
            result["file_url"] = f"/api/admin/display/preview?path={payload.path}"
            result["open_url"] = "/api/admin/display/open"
            if metadata.kind == "image":
                result["image_url"] = f"/api/admin/display/asset?path={payload.path}"
        return result

    def list_messages(
        self,
        *,
        limit: int,
        offset: int,
        tail: bool = False,
        kind: str | None = None,
        source: str | None = None,
    ) -> MessageList:
        """List message metadata with optional lightweight filters."""
        instance = self.get_or_create_instance()
        with self._lock:
            message_ids = list(instance.message_ids)
            hot_metadata = {
                message_id: message.metadata
                for message_id, message in instance.messages.items()
            }
        if kind is None and source is None:
            page_offset = _tail_offset(total=len(message_ids), limit=limit, offset=offset) if tail else offset
            page_ids = message_ids[page_offset : page_offset + limit]
            items = [
                metadata
                for message_id in page_ids
                if (metadata := hot_metadata.get(message_id) or _read_cached_metadata(instance, message_id)) is not None
            ]
            total = len(message_ids)
            return MessageList(
                items=items,
                total=total,
                offset=page_offset,
                limit=limit,
            )
        items = [
            metadata
            for message_id in message_ids
            if (metadata := hot_metadata.get(message_id) or _read_cached_metadata(instance, message_id)) is not None
        ]
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if source is not None:
            items = [item for item in items if item.metadata.get("source") == source]
        page_offset = _tail_offset(total=len(items), limit=limit, offset=offset) if tail else offset
        return MessageList(
            items=items[page_offset : page_offset + limit],
            total=len(items),
            offset=page_offset,
            limit=limit,
        )

    def focus(self, *, id: str) -> FocusResult | None:
        """Queue or deliver a focus event for one message."""
        instance = self.get_or_create_instance()
        with self._lock:
            if id not in instance.message_id_set:
                return None
            instance.focus_target = id
            instance.updated_at = _utcnow()
            delivered = instance.has_event_client
            _append_event(instance, {"type": "focus", "id": id})
            return FocusResult(id=id, delivered=delivered, queued=not delivered)

    def clear_messages(self) -> int:
        """Clear all messages for the current display instance."""
        instance = self.get_or_create_instance()
        cache_dir: Path | None
        with self._lock:
            cleared = len(instance.message_ids)
            cache_dir = instance.cache_dir
            instance.messages.clear()
            instance.message_ids.clear()
            instance.message_id_set.clear()
            instance.focus_target = None
            instance.event_queue.clear()
            instance.updated_at = _utcnow()
            _append_event(instance, {"type": "message", "id": ""})
        if cache_dir is not None:
            shutil.rmtree(cache_dir, ignore_errors=True)
        return cleared

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

    def poll_current_events(self) -> list[dict[str, str]]:
        """Return queued events for the current signed Direct API caller."""
        instance = self.get_or_create_instance()
        with self._lock:
            instance.has_event_client = True
            events = list(instance.event_queue)
            instance.event_queue.clear()
            if instance.focus_target is not None:
                events.append({"type": "focus", "id": instance.focus_target})
            return events

    def resolve_browser_instance(self, *, browser_instance_id: str) -> tuple[str, str] | None:
        """Resolve a full or short browser instance ID to API credentials."""
        instance = self.get_or_create_instance()
        with self._lock:
            if browser_instance_id == instance.id or browser_instance_id == short_instance_id(instance.id):
                return instance.id, instance.token
            return None

    def authorize(self, *, instance_id: str, token: str | None) -> bool:
        """Return whether an instance route token is valid."""
        instance = self.get_or_create_instance()
        return instance.id == instance_id and token == instance.token


STATE = DisplayState()


def _new_message_id(existing_ids: set[str]) -> str:
    """Return a short unique display message ID for one process instance."""
    while True:
        message_id = token_hex(MESSAGE_ID_HEX_CHARS // 2)
        if message_id not in existing_ids:
            return message_id


def allowed_roots() -> list[Path]:
    """Return workspace roots allowed for display file preview."""
    return [get_effective_cwd().resolve(), (get_session_dir() / "images").resolve()]


def resolve_allowed_path(path: str) -> Path:
    """Resolve a user path and reject paths outside allowed roots."""
    candidate = (get_effective_cwd() / path).resolve()
    if any(candidate == root or root in candidate.parents for root in allowed_roots()):
        return candidate
    raise PermissionError("path is outside allowed workspace roots")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _tail_offset(*, total: int, limit: int, offset: int) -> int:
    """Return an offset from the end while preserving ascending item order."""
    return max(0, total - limit - offset)


def _append_event(instance: DisplayInstance, event: dict[str, str]) -> None:
    """Append an event while bounding disconnected-client memory growth."""
    if event["type"] == "message" and instance.event_queue and instance.event_queue[-1]["type"] == "message":
        instance.event_queue[-1] = event
        return
    instance.event_queue.append(event)
    while len(instance.event_queue) > MAX_EVENT_QUEUE:
        instance.event_queue.popleft()


def _max_message_records() -> int:
    """Return configured MCP-side display queue retention."""
    try:
        from ot.config import get_config

        return max(1, min(MAX_MESSAGE_RECORDS, get_config().display.max_queue_messages))
    except Exception:
        return MAX_MESSAGE_RECORDS


def _instance_metadata(instance: DisplayInstance) -> InstanceMetadata:
    return InstanceMetadata(
        status="running",
        mcp_instance_id=instance.id,
        message_count=len(instance.message_ids),
        started_at=instance.started_at,
        updated_at=instance.updated_at,
    )


def short_instance_id(instance_id: str) -> str:
    """Return the compact browser route ID for a display instance."""
    return instance_id.removeprefix("mcp-")[:16]


def _cache_dir_for_instance(instance_id: str) -> Path:
    return get_project_state_dir("display") / "instances" / instance_id / "messages"


def _cache_path(instance: DisplayInstance, message_id: str) -> Path:
    cache_dir = instance.cache_dir or _cache_dir_for_instance(instance.id)
    return cache_dir / f"{message_id}.json"


def _write_cached_message(instance: DisplayInstance, message: DisplayMessage) -> None:
    path = _cache_path(instance, message.metadata.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(message.model_dump_json(), encoding="utf-8")
    temp_path.replace(path)


def _delete_cached_message(instance: DisplayInstance, message_id: str) -> None:
    with suppress(FileNotFoundError):
        _cache_path(instance, message_id).unlink()


def _read_cached_message(instance: DisplayInstance, message_id: str) -> DisplayMessage | None:
    path = _cache_path(instance, message_id)
    if not path.is_file():
        return None
    return DisplayMessage.model_validate_json(path.read_text(encoding="utf-8"))


def _read_cached_metadata(instance: DisplayInstance, message_id: str) -> MessageMetadata | None:
    message = _read_cached_message(instance, message_id)
    if message is None:
        return None
    return message.metadata


def _build_payload(
    request: ShowRequest,
) -> tuple[PayloadReference, BoundedPreview | None, object | None]:
    if request.kind in {"file", "image"}:
        path = _resolve_existing_payload_path(request.path or "", kind=request.kind)
        size = path.stat().st_size
        preview = _file_preview(path) if request.kind == "file" else None
        return (
            PayloadReference(
                mode="file",
                path=str(path),
                size_bytes=size,
            ),
            preview,
            None,
        )
    if request.kind == "file_diff":
        if request.path:
            path = _resolve_existing_payload_path(request.path, kind=request.kind)
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
        old_path = _resolve_existing_payload_path(request.old_path or "", kind=request.kind)
        new_path = _resolve_existing_payload_path(request.new_path or "", kind=request.kind)
        diff_text = _file_diff(old_path, new_path)
        encoded = diff_text.encode("utf-8")
        return (
            PayloadReference(
                mode="file_diff",
                old_path=str(old_path),
                new_path=str(new_path),
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
        ),
        preview,
        _bounded_inline_payload(request.content),
    )


def _resolve_existing_payload_path(path: str, *, kind: str) -> Path:
    resolved = resolve_allowed_path(path)
    if not resolved.is_file():
        raise ValueError(f"{kind} path not found: {path}")
    return resolved


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


def _message_metadata(*, request: ShowRequest) -> dict[str, str]:
    return dict(request.metadata)
