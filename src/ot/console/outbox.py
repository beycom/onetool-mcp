"""MCP-owned Console outbox state and protocol helpers.

Instance snapshots publish `allowed_roots` (file pack allowed dirs plus cwd);
Console consumers validate `file_ref`/`file_diff_ref` paths against them.
Instance identity comes from `ot.runtime_meta`.

Note: the wire event type `console.message.created` and its envelope/payload
field names are frozen by protocol v1 (`openspec/specs/console-outbox/spec.md`).
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from secrets import token_hex
from threading import Lock
from typing import TYPE_CHECKING, Any, Literal

from ot.paths import get_effective_cwd
from ot.runtime_meta import STARTED_AT, get_or_create_instance_id

if TYPE_CHECKING:
    from pathlib import Path

    from ot.console.models import BoundedPreview, MessageMetadata

PROTOCOL = "onetool.console"
PROTOCOL_VERSION = 1
DEFAULT_RETENTION_LIMIT = 1000
MAX_RETENTION_LIMIT = 5000
OUTBOX_PATH = "/api/console/outbox"
OUTBOX_ACK_PATH = "/api/console/outbox/ack"

ConsoleEventType = Literal["instance.snapshot", "console.message.created"]


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
    _last_snapshot: tuple[str, int] | None = field(default=None, repr=False)

    def configure_instance(self, *, instance_id: str) -> None:
        """Attach the outbox to the current runtime instance."""
        with self.lock:
            if self.instance_id is None:
                self.instance_id = instance_id
            elif self.instance_id != instance_id:
                self.instance_id = instance_id
                self.sequence = 0
                self.acked_through = 0
                self.entries.clear()
                self._last_snapshot = None

    def append(
        self, *, event_type: ConsoleEventType, payload: dict[str, Any]
    ) -> dict[str, Any]:
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
            # `oldest_retained` lets a consumer detect retention-driven loss:
            # the sequence of the oldest entry still retained, or (when the
            # outbox holds no entries) `acked_through` as the empty-outbox
            # value. A consumer whose cursor is `c` has lost events whenever
            # `oldest_retained > c + 1` (the events `c+1 .. oldest_retained-1`
            # were evicted by bounded retention before it acknowledged them).
            oldest_retained = (
                self.entries[0].sequence if self.entries else self.acked_through
            )
            return {
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "instance_id": instance_id,
                "batch_id": token_hex(8),
                "cursor": cursor,
                "next_cursor": next_cursor,
                "oldest_retained": oldest_retained,
                "has_more": len(eligible) > len(selected),
                "events": [entry.event for entry in selected],
                "created_at": _iso_now(),
            }

    def ack(self, *, acked_through: int, instance_id: str) -> dict[str, Any]:
        """Record acknowledgement and drop acknowledged entries.

        Acknowledgement is keyed on `(instance_id, acked_through)` only; the
        poll batch identity (`batch_id`) is not part of the ack contract.
        """
        with self.lock:
            if self.instance_id is not None and instance_id != self.instance_id:
                raise ValueError(
                    "ack instance_id does not match current outbox instance"
                )
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

    def note_snapshot(self, *, status: str, message_count: int) -> bool:
        """Record an instance-snapshot fingerprint, returning whether it is new.

        Returns True (and updates the tracked fingerprint) only when no
        snapshot has been emitted yet for the current instance, or when
        `status`/`message_count` differ from the last emitted snapshot.
        Returns False when the fingerprint is unchanged, so callers can skip
        appending a redundant `instance.snapshot` event.
        """
        with self.lock:
            key = (status, message_count)
            if self._last_snapshot == key:
                return False
            self._last_snapshot = key
            return True

    def drop_message(self, *, message_id: str) -> None:
        """Drop retained `console.message.created` events for a removed Console message."""
        with self.lock:
            self.entries = deque(
                entry
                for entry in self.entries
                if not (
                    entry.event.get("type") == "console.message.created"
                    and entry.event.get("payload", {}).get("id") == message_id
                )
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
    """Append an instance snapshot, but only when it differs from the last one.

    `status`/`message_count` are compared against the last snapshot emitted
    for the current instance; an unchanged fingerprint is a no-op so that
    frequent callers (e.g. `console.status()`) don't flood the bounded
    outbox with redundant snapshots and evict real messages.
    """
    instance_id = _runtime_instance_id()
    STATE.configure_instance(instance_id=instance_id)
    if not STATE.note_snapshot(status=status, message_count=message_count):
        return
    STATE.append(
        event_type="instance.snapshot",
        payload=build_instance_snapshot(message_count=message_count, status=status),
    )


def publish_console_message(
    *,
    metadata: MessageMetadata,
    preview: BoundedPreview | None,
    inline_payload: object | None,
) -> None:
    """Append a `console.message.created` event for Console consumption."""
    instance_id = _runtime_instance_id()
    STATE.configure_instance(instance_id=instance_id)
    STATE.append(
        event_type="console.message.created",
        payload=build_console_message_payload(
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
        "allowed_roots": [str(path) for path in _snapshot_roots(cwd)],
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


def build_console_message_payload(
    *,
    metadata: MessageMetadata,
    preview: BoundedPreview | None,
    inline_payload: object | None,
) -> dict[str, Any]:
    """Return the public Console `console.message.created` payload."""
    payload = metadata.payload
    wire_payload: dict[str, Any] = {
        "mode": payload.mode,
        "mime_type": payload.mime_type,
        "size_bytes": payload.size_bytes,
        "language": payload.language,
    }
    if payload.mode == "inline":
        wire_payload["content"] = _json_compatible(inline_payload)
    elif payload.mode == "file_ref":
        wire_payload["path"] = payload.path
    else:
        if payload.path is not None:
            wire_payload["path"] = payload.path
        if payload.old_path is not None:
            wire_payload["old_path"] = payload.old_path
        if payload.new_path is not None:
            wire_payload["new_path"] = payload.new_path
    result: dict[str, Any] = {
        "id": metadata.id,
        "kind": metadata.kind,
        "metadata": dict(metadata.metadata),
        "created_at": metadata.created_at.isoformat(),
        "updated_at": metadata.updated_at.isoformat(),
        "payload": wire_payload,
        "preview": preview.model_dump(mode="json") if preview else None,
    }
    return result


def poll_outbox(*, limit: int = 100, after: int | None = None) -> dict[str, Any]:
    """Return an outbox batch."""
    return STATE.poll(limit=limit, after=after)


def ack_outbox(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Acknowledge an outbox batch payload."""
    if (
        payload.get("protocol") != PROTOCOL
        or payload.get("protocol_version") != PROTOCOL_VERSION
    ):
        raise ValueError("unsupported Console protocol identity")
    instance_id = payload.get("instance_id")
    acked_through = payload.get("acked_through")
    # `batch_id` is no longer part of the ack contract; accept and ignore it
    # for backward tolerance if a consumer still sends it.
    payload.pop("batch_id", None)
    if not isinstance(instance_id, str) or not isinstance(acked_through, int):
        raise ValueError("invalid outbox ack payload")
    return STATE.ack(acked_through=acked_through, instance_id=instance_id)


def _json_compatible(value: object) -> object:
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


def _runtime_instance_id() -> str:
    return get_or_create_instance_id()


def _snapshot_roots(cwd: Path) -> list[Path]:
    """Return workspace roots reported in instance snapshots.

    Publishes the file pack's configured `allowed_dirs` (realpath-resolved,
    relative entries resolved against the effective cwd) plus the cwd itself.
    Console consumers validate file-reference paths against these roots, so
    they must reflect the real file-access boundary. Falls back to `[cwd]`
    when the file pack has no configuration or config access fails.
    """
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in (*_file_pack_allowed_dirs(cwd), cwd.resolve()):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            roots.append(resolved)
    return roots or [cwd]


def _file_pack_allowed_dirs(cwd: Path) -> list[Path]:
    """Return the file pack's configured allowed directories, defensively."""
    try:
        from pathlib import Path as _Path

        from ot.config import get_tool_config

        raw = get_tool_config("file")
        allowed_dirs = raw.get("allowed_dirs") if isinstance(raw, dict) else None
        if not isinstance(allowed_dirs, list):
            return []
        result: list[Path] = []
        for entry in allowed_dirs:
            if not isinstance(entry, str) or not entry:
                continue
            candidate = _Path(entry).expanduser()
            if not candidate.is_absolute():
                candidate = cwd / candidate
            result.append(candidate)
        return result
    except Exception:
        return []


def current_allowed_roots() -> list[Path]:
    """Return the allowed roots currently published in instance snapshots."""
    return _snapshot_roots(get_effective_cwd().resolve())


def _repo_root(cwd: Path) -> Path:
    for parent in (cwd, *cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def _retention_limit() -> int:
    """Return the configured retention limit, defaulting defensively.

    Reads `config.console.max_queue_messages` from the typed config, falling
    back to `DEFAULT_RETENTION_LIMIT` if config access fails for any reason
    (e.g. in isolated unit tests that never load a config).
    """
    try:
        from ot.config import get_config

        console_config = getattr(get_config(), "console", None)
        max_queue_messages = getattr(console_config, "max_queue_messages", None)
        if not isinstance(max_queue_messages, int):
            return DEFAULT_RETENTION_LIMIT
        return max(1, min(MAX_RETENTION_LIMIT, max_queue_messages))
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
    "build_console_message_payload",
    "build_instance_snapshot",
    "current_allowed_roots",
    "ensure_instance_snapshot",
    "poll_outbox",
    "publish_console_message",
]
