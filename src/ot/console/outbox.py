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

from ot.console.models import queue_message_limit
from ot.paths import get_effective_cwd
from ot.runtime_meta import STARTED_AT, get_or_create_instance_id

if TYPE_CHECKING:
    from pathlib import Path

    from ot.console.models import BoundedPreview, MessageMetadata

PROTOCOL = "onetool.console"
PROTOCOL_VERSION = 1
OUTBOX_PATH = "/api/console/outbox"

ConsoleEventType = Literal["instance.snapshot", "console.message.created"]


@dataclass(frozen=True)
class OutboxEntry:
    """One retained Console outbox event."""

    sequence: int
    event: dict[str, Any]
    message_id: str | None = None


@dataclass
class ConsoleOutboxState:
    """Bounded at-least-once outbox for Console consumers."""

    instance_id: str | None = None
    sequence: int = 0
    last_evicted: int = 0
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
                self.last_evicted = 0
                self.entries.clear()
                self._last_snapshot = None

    def append(
        self,
        *,
        event_type: ConsoleEventType,
        payload: dict[str, Any],
        message_id: str | None = None,
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
            self.entries.append(
                OutboxEntry(
                    sequence=self.sequence,
                    event=event,
                    message_id=message_id,
                )
            )
            self._enforce_retention_locked()
            return dict(event)

    def poll(self, *, limit: int = 100, after: int | None = None) -> dict[str, Any]:
        """Return a stable batch without mutating retained events."""
        with self.lock:
            instance_id = self.instance_id or "mcp-uninitialized"
            cursor = max(0, 0 if after is None else after)
            batch_limit = max(1, min(500, limit))
            eligible = [entry for entry in self.entries if entry.sequence > cursor]
            selected = eligible[:batch_limit]
            next_cursor = selected[-1].sequence if selected else cursor
            # `oldest_retained` lets a consumer detect retention-driven loss:
            # the sequence of the oldest entry still retained, or one past the
            # most recently evicted sequence when the outbox is empty. A
            # consumer whose cursor is `c` has lost events whenever
            # `oldest_retained > c + 1`.
            oldest_retained = (
                self.entries[0].sequence if self.entries else self.last_evicted + 1
            )
            batch = {
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "instance_id": instance_id,
                "batch_id": token_hex(8),
                "cursor": cursor,
                "next_cursor": next_cursor,
                "oldest_retained": oldest_retained,
                "has_more": len(eligible) > len(selected),
                "created_at": _iso_now(),
            }
        batch["events"] = [_serialize_entry(entry) for entry in selected]
        return batch

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
            removed = [
                entry
                for entry in self.entries
                if entry.event.get("type") == "console.message.created"
                and entry.event.get("payload", {}).get("id") == message_id
            ]
            if removed:
                self.last_evicted = max(self.last_evicted, removed[-1].sequence)
            self.entries = deque(
                entry for entry in self.entries if entry not in removed
            )

    def clear(self) -> None:
        """Clear all retained events while preserving sequence monotonicity."""
        with self.lock:
            if self.entries:
                self.last_evicted = max(self.last_evicted, self.entries[-1].sequence)
            self.entries.clear()

    def _enforce_retention_locked(self) -> None:
        limit = queue_message_limit()
        while len(self.entries) > limit:
            evicted = self.entries.popleft()
            self.last_evicted = max(self.last_evicted, evicted.sequence)


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
) -> None:
    """Append an id-only `console.message.created` outbox entry."""
    instance_id = _runtime_instance_id()
    STATE.configure_instance(instance_id=instance_id)
    STATE.append(
        event_type="console.message.created",
        payload=_build_console_message_metadata_payload(metadata=metadata),
        message_id=metadata.id,
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
    result = _build_console_message_metadata_payload(metadata=metadata)
    if metadata.payload.mode == "inline":
        result["payload"]["content"] = _json_compatible(inline_payload)
    result["preview"] = preview.model_dump(mode="json") if preview else None
    return result


def _build_console_message_metadata_payload(
    *, metadata: MessageMetadata
) -> dict[str, Any]:
    """Return the body-free portion of a Console message wire payload."""
    payload = metadata.payload
    wire_payload: dict[str, Any] = {
        "mode": payload.mode,
        "mime_type": payload.mime_type,
        "size_bytes": payload.size_bytes,
        "language": payload.language,
    }
    if payload.mode == "file_ref":
        wire_payload["path"] = payload.path
    elif payload.mode == "file_diff_ref":
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
    }
    return result


def _serialize_entry(entry: OutboxEntry) -> dict[str, Any]:
    """Hydrate one retained id-only message entry for a poll response."""
    if entry.message_id is None:
        return entry.event
    from ot.console.storage import read_message_body

    try:
        message = read_message_body(message_id=entry.message_id)
    except FileNotFoundError:
        # Eviction/clear raced this poll between entry selection (under the
        # outbox lock) and hydration (outside it). Complete the body-free
        # metadata so the fallback still satisfies the protocol schema.
        event = dict(entry.event)
        payload = dict(event["payload"])
        wire_payload = dict(payload["payload"])
        if wire_payload.get("mode") == "inline":
            wire_payload["content"] = None
        payload["payload"] = wire_payload
        payload["preview"] = None
        event["payload"] = payload
        return event
    event = dict(entry.event)
    event["payload"] = build_console_message_payload(
        metadata=message.metadata,
        preview=message.preview,
        inline_payload=message.inline_payload,
    )
    return event


def poll_outbox(*, limit: int = 100, after: int | None = None) -> dict[str, Any]:
    """Return an outbox batch."""
    return STATE.poll(limit=limit, after=after)


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


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "OUTBOX_PATH",
    "PROTOCOL",
    "PROTOCOL_VERSION",
    "STATE",
    "build_console_message_payload",
    "build_instance_snapshot",
    "current_allowed_roots",
    "ensure_instance_snapshot",
    "poll_outbox",
    "publish_console_message",
]
