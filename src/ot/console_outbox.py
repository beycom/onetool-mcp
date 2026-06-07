"""MCP-owned Console outbox state and protocol helpers."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from secrets import token_hex
from threading import Lock
from typing import TYPE_CHECKING, Any, Literal

from ot.display.state import allowed_roots
from ot.paths import get_effective_cwd
from ot.runtime_meta import STARTED_AT

if TYPE_CHECKING:
    from ot.display.models import BoundedPreview, MessageMetadata

PROTOCOL = "onetool.console"
PROTOCOL_VERSION = 1
DEFAULT_RETENTION_LIMIT = 1000
MAX_RETENTION_LIMIT = 5000
OUTBOX_PATH = "/api/console/outbox"
OUTBOX_ACK_PATH = "/api/console/outbox/ack"

ConsoleEventType = Literal["instance.snapshot", "display.message.created"]


@dataclass(frozen=True)
class OutboxEntry:
    """One retained Console outbox event."""

    sequence: int
    event: dict[str, Any]


@dataclass
class ConsoleOutboxState:
    """Bounded at-least-once outbox for Console consumers."""

    instance_id: str | None = None
    sequence: int = 0
    acked_through: int = 0
    entries: deque[OutboxEntry] = field(default_factory=deque)
    lock: Lock = field(default_factory=Lock)

    def configure_instance(self, *, instance_id: str) -> None:
        """Attach the outbox to the current display/runtime instance."""
        with self.lock:
            if self.instance_id is None:
                self.instance_id = instance_id
            elif self.instance_id != instance_id:
                self.instance_id = instance_id
                self.sequence = 0
                self.acked_through = 0
                self.entries.clear()

    def append(self, *, event_type: ConsoleEventType, payload: dict[str, Any]) -> dict[str, Any]:
        """Append one protocol event and return it."""
        with self.lock:
            if self.instance_id is None:
                raise RuntimeError("Console outbox instance is not configured")
            self.sequence += 1
            event = {
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "id": token_hex(8),
                "instance_id": self.instance_id,
                "sequence": self.sequence,
                "type": event_type,
                "created_at": _iso_now(),
                "payload": payload,
            }
            self.entries.append(OutboxEntry(sequence=self.sequence, event=event))
            self._enforce_retention_locked()
            return dict(event)

    def poll(self, *, limit: int = 100, after: int | None = None) -> dict[str, Any]:
        """Return a stable batch without mutating retained events."""
        with self.lock:
            instance_id = self.instance_id or "mcp-uninitialized"
            cursor = max(0, self.acked_through if after is None else after)
            batch_limit = max(1, min(500, limit))
            eligible = [entry for entry in self.entries if entry.sequence > cursor]
            selected = eligible[:batch_limit]
            next_cursor = selected[-1].sequence if selected else cursor
            return {
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "instance_id": instance_id,
                "batch_id": token_hex(8),
                "cursor": cursor,
                "next_cursor": next_cursor,
                "has_more": len(eligible) > len(selected),
                "events": [entry.event for entry in selected],
                "created_at": _iso_now(),
            }

    def ack(self, *, batch_id: str, acked_through: int, instance_id: str) -> dict[str, Any]:
        """Record acknowledgement and drop acknowledged entries."""
        del batch_id
        with self.lock:
            if self.instance_id is not None and instance_id != self.instance_id:
                raise ValueError("ack instance_id does not match current outbox instance")
            if acked_through < self.acked_through:
                acked_through = self.acked_through
            self.acked_through = min(acked_through, self.sequence)
            while self.entries and self.entries[0].sequence <= self.acked_through:
                self.entries.popleft()
            return {
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "instance_id": self.instance_id or instance_id,
                "acked_through": self.acked_through,
                "retained": len(self.entries),
                "created_at": _iso_now(),
            }

    def drop_message(self, *, message_id: str) -> None:
        """Drop retained events for a display message removed from MCP retention."""
        with self.lock:
            self.entries = deque(
                entry
                for entry in self.entries
                if entry.event.get("payload", {}).get("id") != message_id
            )

    def clear(self) -> None:
        """Clear all retained events while preserving sequence monotonicity."""
        with self.lock:
            self.entries.clear()

    def _enforce_retention_locked(self) -> None:
        limit = _retention_limit()
        while len(self.entries) > limit:
            self.entries.popleft()


STATE = ConsoleOutboxState()


def ensure_instance_snapshot(*, message_count: int, status: str = "running") -> None:
    """Append a fresh instance snapshot for the current MCP process."""
    instance_id = _runtime_instance_id()
    STATE.configure_instance(instance_id=instance_id)
    STATE.append(
        event_type="instance.snapshot",
        payload=build_instance_snapshot(message_count=message_count, status=status),
    )


def publish_display_message(
    *,
    metadata: MessageMetadata,
    preview: BoundedPreview | None,
    inline_payload: object | None,
) -> None:
    """Append a display message event for Console consumption."""
    instance_id = _runtime_instance_id()
    STATE.configure_instance(instance_id=instance_id)
    STATE.append(
        event_type="display.message.created",
        payload=build_display_payload(
            metadata=metadata,
            preview=preview,
            inline_payload=inline_payload,
        ),
    )


def build_instance_snapshot(*, message_count: int, status: str) -> dict[str, Any]:
    """Return the public Console instance snapshot payload."""
    from ot.config.loader import get_loaded_config_path
    from ot.support import get_version

    config_path = get_loaded_config_path()
    config_dir = config_path.parent if config_path else None
    cwd = get_effective_cwd().resolve()
    return {
        "id": _runtime_instance_id(),
        "cwd": str(cwd),
        "repo_root": str(_repo_root(cwd)),
        "config_path": str(config_path) if config_path else None,
        "config_dir": str(config_dir) if config_dir else None,
        "allowed_roots": [str(path) for path in allowed_roots()],
        "status": status,
        "message_count": message_count,
        "started_at": STARTED_AT.isoformat(),
        "updated_at": _iso_now(),
        "runtime": {
            "name": "onetool-mcp",
            "version": get_version(),
            "python": True,
        },
    }


def build_display_payload(
    *,
    metadata: MessageMetadata,
    preview: BoundedPreview | None,
    inline_payload: object | None,
) -> dict[str, Any]:
    """Return the public Console display message payload."""
    payload = metadata.payload
    mode = _console_payload_mode(payload)
    result: dict[str, Any] = {
        "id": metadata.id,
        "kind": metadata.kind,
        "metadata": dict(metadata.metadata),
        "created_at": metadata.created_at.isoformat(),
        "updated_at": metadata.updated_at.isoformat(),
        "payload": {
            "mode": mode,
            "mime_type": payload.mime_type,
            "size_bytes": payload.size_bytes,
            "language": payload.language,
        },
        "preview": preview.model_dump(mode="json") if preview else None,
    }
    if mode == "inline":
        result["payload"]["content"] = _json_compatible(inline_payload)
    elif mode == "file_ref":
        result["payload"]["path"] = payload.path
    elif mode == "file_diff_ref":
        result["payload"]["path"] = payload.path
        result["payload"]["old_path"] = payload.old_path
        result["payload"]["new_path"] = payload.new_path
    return result


def poll_outbox(*, limit: int = 100, after: int | None = None) -> dict[str, Any]:
    """Return an outbox batch."""
    return STATE.poll(limit=limit, after=after)


def ack_outbox(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Acknowledge an outbox batch payload."""
    if payload.get("protocol") != PROTOCOL or payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported Console protocol identity")
    instance_id = payload.get("instance_id")
    batch_id = payload.get("batch_id")
    acked_through = payload.get("acked_through")
    if not isinstance(instance_id, str) or not isinstance(batch_id, str) or not isinstance(acked_through, int):
        raise ValueError("invalid outbox ack payload")
    return STATE.ack(batch_id=batch_id, acked_through=acked_through, instance_id=instance_id)


def _console_payload_mode(payload: Any) -> str:
    if payload.mode == "file":
        return "file_ref"
    if payload.mode == "file_diff":
        return "file_diff_ref"
    return "inline"


def _json_compatible(value: object) -> object:
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


def _runtime_instance_id() -> str:
    from ot.display.state import STATE as display_state

    return display_state.get_or_create_instance().id


def _repo_root(cwd: Any) -> Any:
    path = cwd
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return path


def _retention_limit() -> int:
    try:
        from ot.config import get_config

        return max(1, min(MAX_RETENTION_LIMIT, get_config().display.max_queue_messages))
    except Exception:
        return DEFAULT_RETENTION_LIMIT


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "OUTBOX_ACK_PATH",
    "OUTBOX_PATH",
    "PROTOCOL",
    "PROTOCOL_VERSION",
    "STATE",
    "ack_outbox",
    "build_display_payload",
    "build_instance_snapshot",
    "ensure_instance_snapshot",
    "poll_outbox",
    "publish_display_message",
]
