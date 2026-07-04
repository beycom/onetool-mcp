"""Console pack: publish inline messages to a connected onetool-console.

Inline-only in 3.0: `console.show` accepts string/dict/list content bounded to
the configured inline payload limit; file-backed payload modes (`file`,
`image`, `file_diff`) ship with the full display pack in 3.1. Publishing never
requires a Console consumer to be connected — the outbox is retention-only
when nothing polls it.

Example:
    console.show(kind="text", content="build finished", metadata={"source": "ci"})
    console.list(limit=10)
    console.read(id="<message id from show>")
    console.clear()
"""

from __future__ import annotations

pack = "console"
doc_slug = "console"

__all__ = ["clear", "list", "read", "show"]

from typing import (  # noqa: UP035 - List avoids shadowing by the `list` tool below
    Any,
    List,
)

from ot.console.models import ConsoleKind, ShowRequest
from ot.console.state import STATE
from otpack import LogSpan


def show(
    *,
    kind: ConsoleKind,
    content: str | dict[str, Any] | List[Any],
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create one inline Console message and publish it to the outbox.

    Args:
        kind: Message kind: text, markdown, code, diff, json, mermaid, yaml, or table.
        content: Inline content (string, mapping, or list). Oversized content is
            truncated to the configured inline payload limit rather than erroring.
        metadata: Optional user-provided key-value metadata.

    Returns:
        Dict with stable message ID, kind, metadata, and payload reference.

    Example:
        console.show(kind="text", content="build finished")
    """
    with LogSpan(span="console.show", kind=kind):
        request = ShowRequest.model_validate(
            {"kind": kind, "metadata": metadata or {}, "content": content}
        )
        result = STATE.add_message(request=request)
        return result.model_dump(mode="json")


def list(
    *,
    limit: int = 100,
    offset: int = 0,
    kind: ConsoleKind | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """List retained Console message metadata, oldest-first, paginated.

    Args:
        limit: Page size from 1 to 500.
        offset: Zero-based page offset.
        kind: Optional message kind filter.
        source: Optional filter matching the `source` metadata key.

    Returns:
        Paginated metadata-only page of retained Console messages.

    Example:
        console.list(limit=10, kind="text")
    """
    with LogSpan(span="console.list", limit=limit, offset=offset):
        if limit < 1 or limit > 500:
            raise ValueError("console.list limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("console.list offset must be greater than or equal to 0")
        return STATE.list_messages(
            limit=limit, offset=offset, kind=kind, source=source
        ).model_dump(mode="json")


def read(*, id: str) -> dict[str, Any] | str:
    """Read one retained Console message's full payload by ID.

    Args:
        id: Stable Console message ID returned by `console.show`.

    Returns:
        Dict with metadata, bounded preview, and full retained inline content,
        or an error string if the message is not retained (already cleared or
        expired past the retention bound).

    Example:
        console.read(id="a1b2c3d4e5f6")
    """
    with LogSpan(span="console.read", id=id):
        result = STATE.payload_view(id=id)
        if result is None:
            return f"Error: console message not found: {id}"
        return result


def clear() -> dict[str, Any]:
    """Clear all retained Console messages for the current instance.

    Returns:
        Dict with cleared message count, current message count, and updated timestamp.

    Example:
        console.clear()
    """
    with LogSpan(span="console.clear"):
        cleared = STATE.clear_messages()
        status = STATE.status()
        return {
            "cleared": cleared,
            "message_count": status.message_count,
            "updated_at": status.updated_at.isoformat(),
        }
