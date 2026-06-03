"""User-facing local display tools for rich artifacts."""

from __future__ import annotations

pack = "display"
__all__ = ["focus", "list", "read", "seed_mock_messages", "show", "status"]

from pathlib import Path
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
        if limit < 1 or limit > 500:
            raise ValueError("display.list limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("display.list offset must be greater than or equal to 0")
        return list_messages(
            limit=limit,
            offset=offset,
            kind=kind,
            source=source,
        ).model_dump(mode="json")


def seed_mock_messages(*, bulk_count: int = 0) -> dict[str, Any]:
    """TEST ONLY: seed representative Display messages for UI development.

    Args:
        bulk_count: Optional number of extra lightweight text messages for volume testing.

    Returns:
        Metadata only: display URL, count, and created message IDs by kind.
    """
    with LogSpan(span="display.seed_mock_messages", bulk_count=bulk_count):
        ids_by_kind: dict[str, list[str]] = {}

        def add(kind: DisplayKind, **kwargs: Any) -> str:
            created = show(kind=kind, source="display.seed_mock_messages", **kwargs)
            message_id = str(created["id"])
            ids_by_kind.setdefault(kind, []).append(message_id)
            return message_id

        add("text", title="Short text", content="A short display message.")
        add("markdown", title="Markdown", content="# Display fixture\n\n- markdown\n- code\n- tables")
        add("code", title="Python code", language="python", content='def fixture() -> str:\n    return "display"\n')
        add("diff", title="Inline diff", content="--- a/example.txt\n+++ b/example.txt\n@@ -1 +1 @@\n-old\n+new\n")
        add("json", title="JSON", content={"ok": True, "items": [{"name": "alpha"}, {"name": "beta"}]})
        add("yaml", title="YAML", content="site_name: OneTool\nsite_description: Display fixture\nfeatures:\n  - timeline\n  - inspector\n")
        add("mermaid", title="Mermaid", content="flowchart LR\n  A[show] --> B[display]\n")
        add("table", title="Table", content=[{"row": index, "value": f"item-{index}"} for index in range(250)])

        for path in _fixture_file_paths():
            add("file", title=Path(path).name, path=path)

        image_path = _first_existing_path(["docs/assets/logo.png", "docs/assets/logo.svg", "tests/data/products-small.png"])
        if image_path is not None:
            add("image", title=Path(image_path).name, path=image_path)

        diff_pair = _first_existing_pair(
            [
                ("packages/onetool-display-ui/src/api/displayApi.ts", "packages/onetool-display-ui/src/lib/displayStore.ts"),
                ("src/ottools/display.py", "src/ot/display/service.py"),
            ]
        )
        if diff_pair is not None:
            old_path, new_path = diff_pair
            add("file_diff", title="Fixture diff", old_path=old_path, new_path=new_path)

        for index in range(max(0, min(2000, bulk_count))):
            add("text", title=f"Bulk {index + 1}", content=f"Bulk fixture message {index + 1}")

        status_result = status()
        return {
            "test_only": True,
            "url": status_result["url"],
            "count": sum(len(ids) for ids in ids_by_kind.values()),
            "ids_by_kind": ids_by_kind,
        }


def _fixture_file_paths() -> list[str]:
    candidates = [
        "README.md",
        "dev/agents/hints.md",
        "packages/onetool-display-ui/package.json",
        "mkdocs.yml",
        "packages/onetool-display-ui/scripts/build.mjs",
        "packages/onetool-display-ui/src/api/displayApi.ts",
        "src/ottools/display.py",
        "pyproject.toml",
    ]
    return [path for path in candidates if Path(path).is_file()]


def _first_existing_path(candidates: list[str]) -> str | None:
    return next((path for path in candidates if Path(path).is_file()), None)


def _first_existing_pair(candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    return next(
        ((old_path, new_path) for old_path, new_path in candidates if Path(old_path).is_file() and Path(new_path).is_file()),
        None,
    )
