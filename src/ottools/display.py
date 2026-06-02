"""User-facing local display tools for rich artifacts."""

from __future__ import annotations

pack = "display"
__all__ = ["focus", "list", "read", "show", "status"]

from typing import Any, Literal

from otpack import LogSpan

from ot.display import (
    focus_message,
    get_message,
    get_status,
    list_messages,
    show_message,
)

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
ExpandMode = Literal["auto", "collapsed", "expanded"]


def status() -> dict[str, Any]:
    """Return display service and current instance metadata.

    Returns:
        Dict with status, mcp_instance_id, URL, message count, and timestamps.
    """
    with LogSpan(span="display.status"):
        return get_status().model_dump(mode="json")


def show(
    *,
    kind: DisplayKind,
    title: str | None = None,
    summary: str | None = None,
    source: str | None = None,
    expand: ExpandMode = "auto",
    content: str | dict[str, Any] | list[Any] | None = None,
    path: str | None = None,
    old_path: str | None = None,
    new_path: str | None = None,
    language: str | None = None,
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Create one typed user-visible display message.

    Args:
        kind: V1 kind: text, markdown, code, file, diff, file_diff, image, json,
            mermaid, yaml, or table.
        title: Optional display title.
        summary: Optional lightweight summary for timeline rows.
        source: Optional producer or workflow source label.
        expand: Initial browser expansion mode: auto, collapsed, or expanded.
        content: Inline content for text-like and structured kinds.
        path: Workspace-local path for file, image, or file_diff payloads.
        old_path: Workspace-local old path for file_diff payloads.
        new_path: Workspace-local new path for file_diff payloads.
        language: Optional code or highlighter language.
        mime_type: Optional MIME type.

    Returns:
        Dict with stable message ID, instance URL, and metadata only.
    """
    with LogSpan(span="display.show", kind=kind):
        return show_message(
            kind=kind,
            title=title,
            summary=summary,
            source=source,
            expand=expand,
            content=content,
            path=path,
            old_path=old_path,
            new_path=new_path,
            language=language,
            mime_type=mime_type,
        )


def read(*, id: str) -> dict[str, Any] | str:
    """Read one display message with metadata and bounded preview only.

    Args:
        id: Stable display message ID.

    Returns:
        Message metadata plus bounded preview, or an error string.
    """
    with LogSpan(span="display.read", id=id):
        result = get_message(id=id)
        if result is None:
            return f"Error: display message not found: {id}"
        return result.model_dump(mode="json")


def focus(*, id: str) -> dict[str, Any] | str:
    """Focus one display message in connected browser clients.

    Args:
        id: Stable display message ID.

    Returns:
        Focus delivery status, or an error string.
    """
    with LogSpan(span="display.focus", id=id):
        result = focus_message(id=id)
        if result is None:
            return f"Error: display message not found: {id}"
        return result.model_dump(mode="json")


def list(
    *,
    limit: int = 100,
    offset: int = 0,
    kind: DisplayKind | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """List display messages as paginated metadata only.

    Args:
        limit: Page size from 1 to 500.
        offset: Zero-based page offset.
        kind: Optional V1 kind filter.
        source: Optional source filter.

    Returns:
        Metadata-only page of display messages.
    """
    with LogSpan(span="display.list", limit=limit, offset=offset):
        bounded_limit = max(1, min(500, limit))
        bounded_offset = max(0, offset)
        return list_messages(
            limit=bounded_limit,
            offset=bounded_offset,
            kind=kind,
            source=source,
        ).model_dump(mode="json")
