"""Public helpers used by the display tool pack."""

from __future__ import annotations

from typing import Any

from ot.display.models import (
    FocusResult,
    InstanceMetadata,
    MessageList,
    MessageRead,
    ShowRequest,
)
from ot.display.server import ensure_server
from ot.display.state import STATE


def clear_messages() -> dict[str, Any]:
    """Clear all messages for the current display instance."""
    base_url = ensure_server()
    cleared = STATE.clear_messages()
    status = STATE.status(base_url=base_url)
    return {
        "cleared": cleared,
        "url": status.url,
        "message_count": status.message_count,
        "updated_at": status.updated_at.isoformat(),
    }


def get_status() -> InstanceMetadata:
    """Return display service and current instance metadata."""
    return STATE.status(base_url=ensure_server())


def show_message(
    *,
    kind: str,
    metadata: dict[str, str] | None = None,
    content: str | dict[str, Any] | list[Any] | None = None,
    path: str | None = None,
    old_path: str | None = None,
    new_path: str | None = None,
) -> dict[str, Any]:
    """Create one display message and return its stable ID."""
    request = ShowRequest.model_validate(
        {
            "kind": kind,
            "metadata": metadata or {},
            "content": content,
            "path": path,
            "old_path": old_path,
            "new_path": new_path,
        }
    )
    ensure_server()
    message = STATE.add_message(request=request)
    status = get_status()
    return {
        "id": message.id,
        "kind": message.kind,
        "path": message.payload.path,
        "url": status.url,
        "metadata": message.model_dump(mode="json"),
    }


def get_message(*, id: str) -> MessageRead | None:
    """Read one display message with bounded preview only."""
    ensure_server()
    return STATE.read_message(id=id)


def focus_message(*, id: str) -> FocusResult | None:
    """Focus a display message in connected clients."""
    ensure_server()
    return STATE.focus(id=id)


def list_messages(
    *,
    limit: int = 100,
    offset: int = 0,
    tail: bool = False,
    kind: str | None = None,
    source: str | None = None,
) -> MessageList:
    """List display message metadata only."""
    ensure_server()
    return STATE.list_messages(limit=limit, offset=offset, tail=tail, kind=kind, source=source)


def get_payload_view(*, id: str) -> dict[str, object] | None:
    """Return browser-only lazy payload details for one message."""
    base_url = ensure_server()
    return STATE.payload_view(id=id, base_url=base_url)
