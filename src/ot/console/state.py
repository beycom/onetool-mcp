"""Process-local, in-memory state for the inline-only Console message store.

Slim subset of the `feature/display` branch's full `DisplayState` (581 lines):
no disk cache, no file/diff previews, no path resolution, no browser
focus/event-polling plumbing. Just message id generation, bounded retention,
bounded inline payload truncation, and the Console outbox publish hooks.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from secrets import token_hex
from threading import Lock

from ot.console.models import (
    BoundedPreview,
    ConsoleMessage,
    InstanceMetadata,
    MessageList,
    MessageMetadata,
    MessageRead,
    PayloadReference,
    ShowRequest,
)
from ot.runtime_meta import STARTED_AT, get_or_create_instance_id

DEFAULT_MAX_MESSAGE_RECORDS = 1000
MAX_MESSAGE_RECORDS_CEILING = 5000
PREVIEW_LIMIT_BYTES = 64 * 1024
MAX_INLINE_LIST_ITEMS = 500
MESSAGE_ID_HEX_CHARS = 12


@dataclass
class ConsoleInstance:
    """State for one running MCP process."""

    id: str
    started_at: datetime
    updated_at: datetime
    messages: OrderedDict[str, ConsoleMessage] = field(default_factory=OrderedDict)
    message_ids: list[str] = field(default_factory=list)
    message_id_set: set[str] = field(default_factory=set)


class ConsoleState:
    """Process-local Console message state (inline-only, bounded, in-memory)."""

    def __init__(self, *, max_records: int | None = None) -> None:
        self._lock = Lock()
        self._instance: ConsoleInstance | None = None
        self._max_records_override = max_records

    def get_or_create_instance(self) -> ConsoleInstance:
        """Return the current process instance, creating it if needed."""
        with self._lock:
            if self._instance is None:
                self._instance = ConsoleInstance(
                    id=get_or_create_instance_id(),
                    started_at=STARTED_AT,
                    updated_at=_utcnow(),
                )
            return self._instance

    def status(self) -> InstanceMetadata:
        """Return current instance metadata."""
        instance = self.get_or_create_instance()
        with self._lock:
            metadata = _instance_metadata(instance)
        _ensure_console_snapshot(message_count=metadata.message_count)
        return metadata

    def add_message(self, *, request: ShowRequest) -> MessageMetadata:
        """Add a validated inline Console message to the current instance."""
        instance = self.get_or_create_instance()
        now = _utcnow()
        payload, preview, inline_payload = _build_payload(request)
        expired_ids: list[str] = []
        with self._lock:
            message_id = _new_message_id(instance.message_id_set)
            metadata = MessageMetadata(
                id=message_id,
                kind=request.kind,
                metadata=dict(request.metadata),
                preview_lines=_preview_line_count(preview),
                created_at=now,
                updated_at=now,
                payload=payload,
            )
            message = ConsoleMessage(
                metadata=metadata,
                preview=preview,
                inline_payload=inline_payload,
            )
            instance.messages[message_id] = message
            instance.message_ids.append(message_id)
            instance.message_id_set.add(message_id)
            max_records = self._max_records()
            while len(instance.message_ids) > max_records:
                expired_id = instance.message_ids.pop(0)
                instance.messages.pop(expired_id, None)
                instance.message_id_set.discard(expired_id)
                expired_ids.append(expired_id)
            instance.updated_at = now
        _publish_console_message(
            metadata=metadata, preview=preview, inline_payload=inline_payload
        )
        for expired_id in expired_ids:
            _drop_console_message(message_id=expired_id)
        return metadata

    def read_message(self, *, id: str) -> MessageRead | None:
        """Read one message's metadata and preview by ID."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
        if message is None:
            return None
        return MessageRead(metadata=message.metadata, preview=message.preview)

    def payload_view(self, *, id: str) -> dict[str, object] | None:
        """Return the full retained inline payload for one message."""
        instance = self.get_or_create_instance()
        with self._lock:
            message = instance.messages.get(id)
        if message is None:
            return None
        return {
            "metadata": message.metadata.model_dump(mode="json"),
            "preview": message.preview.model_dump(mode="json")
            if message.preview
            else None,
            "content": _bounded_inline_payload(message.inline_payload),
        }

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
            items = [
                instance.messages[message_id].metadata
                for message_id in instance.message_ids
            ]
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if source is not None:
            items = [item for item in items if item.metadata.get("source") == source]
        page_offset = (
            _tail_offset(total=len(items), limit=limit, offset=offset)
            if tail
            else offset
        )
        return MessageList(
            items=items[page_offset : page_offset + limit],
            total=len(items),
            offset=page_offset,
            limit=limit,
        )

    def clear_messages(self) -> int:
        """Clear all messages for the current Console instance."""
        instance = self.get_or_create_instance()
        with self._lock:
            cleared = len(instance.message_ids)
            instance.messages.clear()
            instance.message_ids.clear()
            instance.message_id_set.clear()
            instance.updated_at = _utcnow()
        _clear_console_outbox()
        return cleared

    def _max_records(self) -> int:
        if self._max_records_override is not None:
            return self._max_records_override
        return _max_message_records()


STATE = ConsoleState()


def _new_message_id(existing_ids: set[str]) -> str:
    """Return a short unique Console message ID for one process instance."""
    while True:
        message_id = token_hex(MESSAGE_ID_HEX_CHARS // 2)
        if message_id not in existing_ids:
            return message_id


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _tail_offset(*, total: int, limit: int, offset: int) -> int:
    """Return an offset from the end while preserving ascending item order."""
    return max(0, total - limit - offset)


def _max_message_records() -> int:
    """Return configured MCP-side Console message queue retention.

    Reads `config.console.max_queue_messages` from the typed config, falling
    back to `DEFAULT_MAX_MESSAGE_RECORDS` if config access fails for any
    reason (e.g. in isolated unit tests that never load a config).
    """
    try:
        from ot.config import get_config

        console_config = getattr(get_config(), "console", None)
        max_queue_messages = getattr(console_config, "max_queue_messages", None)
        if not isinstance(max_queue_messages, int):
            return DEFAULT_MAX_MESSAGE_RECORDS
        return max(1, min(MAX_MESSAGE_RECORDS_CEILING, max_queue_messages))
    except Exception:
        return DEFAULT_MAX_MESSAGE_RECORDS


def _instance_metadata(instance: ConsoleInstance) -> InstanceMetadata:
    return InstanceMetadata(
        status="running",
        mcp_instance_id=instance.id,
        message_count=len(instance.message_ids),
        started_at=instance.started_at,
        updated_at=instance.updated_at,
    )


def _build_payload(
    request: ShowRequest,
) -> tuple[PayloadReference, BoundedPreview, object]:
    text = _content_to_text(request.content)
    encoded = text.encode("utf-8")
    preview = BoundedPreview(
        text=encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace"),
        truncated=len(encoded) > PREVIEW_LIMIT_BYTES,
        size_bytes=len(encoded),
        limit_bytes=PREVIEW_LIMIT_BYTES,
    )
    return (
        PayloadReference(mode="inline", size_bytes=len(encoded)),
        preview,
        _bounded_inline_payload(request.content),
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
        sliced = content[:MAX_INLINE_LIST_ITEMS]
        text = json.dumps(sliced, indent=2, sort_keys=True)
        encoded = text.encode("utf-8")
        if len(encoded) <= PREVIEW_LIMIT_BYTES:
            return sliced
        return {
            "truncated": True,
            "preview": encoded[:PREVIEW_LIMIT_BYTES].decode("utf-8", errors="replace"),
            "size_bytes": len(encoded),
            "limit_bytes": PREVIEW_LIMIT_BYTES,
        }
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


def _ensure_console_snapshot(*, message_count: int) -> None:
    try:
        from ot.console.outbox import ensure_instance_snapshot

        ensure_instance_snapshot(message_count=message_count)
    except Exception:
        return


def _publish_console_message(
    *,
    metadata: MessageMetadata,
    preview: BoundedPreview | None,
    inline_payload: object | None,
) -> None:
    try:
        from ot.console.outbox import publish_console_message

        publish_console_message(
            metadata=metadata, preview=preview, inline_payload=inline_payload
        )
    except Exception:
        return


def _drop_console_message(*, message_id: str) -> None:
    try:
        from ot.console.outbox import STATE as console_outbox

        console_outbox.drop_message(message_id=message_id)
    except Exception:
        return


def _clear_console_outbox() -> None:
    try:
        from ot.console.outbox import STATE as console_outbox

        console_outbox.clear()
    except Exception:
        return


__all__ = [
    "DEFAULT_MAX_MESSAGE_RECORDS",
    "MAX_INLINE_LIST_ITEMS",
    "MAX_MESSAGE_RECORDS_CEILING",
    "PREVIEW_LIMIT_BYTES",
    "STATE",
    "ConsoleInstance",
    "ConsoleState",
]
