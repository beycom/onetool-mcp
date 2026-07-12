"""Console pack: publish messages to a connected onetool-console.

`console.show` publishes bounded inline content. `console.display` routes
verbose or visual tool output to the Console and returns a one-line digest
receipt instead of the content — use it to keep large results out of the
model context. Path-based display publishes file references (`file_ref`,
`file_diff_ref`); the Console fetches file content on demand, at any size.
Publishing never requires a Console consumer to be connected — the outbox is
retention-only when nothing polls it.

Example:
    console.display(ground.search(q="mcp features", count=20))
    console.display(path="/repo/diagrams/architecture.svg")
    console.show(kind="text", content="build finished", metadata={"source": "ci"})
    console.list(limit=10)
    console.read(id="<message id from show>")
    console.clear()
"""

from __future__ import annotations

pack = "console"
doc_slug = "console"

__all__ = ["clear", "display", "list", "read", "show"]

from pathlib import Path
from typing import (  # noqa: UP035 - List avoids shadowing by the `list` tool below
    TYPE_CHECKING,
    Any,
    List,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

from pydantic import ValidationError

from ot.console.models import ConsoleKind, ShowRequest
from ot.console.state import (
    STATE,
    detect_language,
    is_textual_file,
    read_bounded_text,
)
from otpack import LogSpan

RECEIPT_MAX_CHARS = 240
_DIGEST_VALUE_MAX_CHARS = 80

_IMAGE_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
_TABLE_KEY_OVERLAP = 0.8


def show(
    *,
    kind: ConsoleKind,
    content: str | dict[str, Any] | List[Any],
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create one inline Console message and publish it to the outbox.

    Args:
        kind: Message kind: text, markdown, code, diff, json, mermaid, yaml, table,
            file, or image. The file and image kinds are normally produced via
            `display(path=...)`, which publishes a file reference instead.
        content: Inline content (string, mapping, or list). Oversized content is
            truncated to the configured inline payload limit rather than erroring.
        metadata: Optional user-provided key-value metadata.

    Returns:
        Dict with stable message ID, kind, metadata, and payload reference.

    Example:
        console.show(kind="text", content="build finished")
    """
    with LogSpan(span="console.show", kind=kind):
        try:
            request = ShowRequest.model_validate(
                {"kind": kind, "metadata": metadata or {}, "content": content}
            )
        except ValidationError as e:
            first: Mapping[str, Any] = e.errors()[0] if e.errors() else {}
            field = ".".join(str(p) for p in first.get("loc", ())) or "arguments"
            raise ValueError(f"console.show: invalid {field}: {first.get('msg', e)}") from e
        result = STATE.add_message(request=request)
        return result.model_dump(mode="json")


def display(
    content: Any = None,
    /,
    *,
    path: str | None = None,
    old_path: str | None = None,
    new_path: str | None = None,
    kind: ConsoleKind | None = None,
    title: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Publish tool output or a file to the Console; return a one-line receipt.

    Routes verbose or visual output to the connected onetool-console instead
    of returning it into the model context. The receipt carries the message id
    (readable back via `console.read`) and a structural digest. Exactly one
    input form is accepted: a positional value, `path`, or `old_path` with
    `new_path`.

    File references are live views: the Console reads the file at view time.
    Content that must be preserved as-it-was (e.g. localhist diffs) should be
    displayed as an inline value instead of a path.

    Args:
        content: Any evaluated value (positional): tool results, dicts, lists,
            or strings. Kind is inferred (table/json/markdown/text) unless set.
        path: Absolute path to display as a file reference (no content leaves
            the machine; the Console fetches it on demand at any size).
        old_path: Absolute path of the old file for a diff reference.
        new_path: Absolute path of the new file for a diff reference.
        kind: Explicit message kind, overriding inference.
        title: Shorthand for metadata["title"].
        metadata: Optional string key-value metadata.

    Returns:
        One-line string receipt, e.g.
        `console[a3f2c19e04d1] table: 20 items (title, url, snippet)`.

    Example:
        console.display(ground.search(q="mcp features", count=20))
        r = webfetch.fetch(url); console.display(r, kind="markdown"); r[:500]
        console.display(ot.servers())
        console.display(path="/repo/diagrams/architecture.svg")
    """
    with LogSpan(span="console.display", kind=kind):
        forms = [content is not None, path is not None, old_path is not None or new_path is not None]
        if sum(forms) != 1:
            raise ValueError(
                "console.display accepts exactly one input form: a positional "
                "value, path=..., or old_path=... with new_path=..."
            )
        meta = dict(metadata or {})
        if title is not None:
            meta["title"] = title
        if content is not None:
            return _display_value(content, kind=kind, metadata=meta)
        if path is not None:
            return _display_path(path, kind=kind, metadata=meta)
        if old_path is None or new_path is None:
            raise ValueError(
                "console.display diff form requires both old_path and new_path"
            )
        return _display_diff(old_path, new_path, kind=kind, metadata=meta)


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


def _display_value(
    content: Any, *, kind: ConsoleKind | None, metadata: dict[str, str]
) -> str:
    resolved_kind = kind or _infer_value_kind(content)
    request = ShowRequest.model_validate(
        {"kind": resolved_kind, "metadata": metadata, "content": _coerce_content(content)}
    )
    result = STATE.add_message(request=request)
    digest = _value_digest(content, kind=resolved_kind)
    return _finish_receipt(result.id, resolved_kind, digest)


def _display_path(
    path: str, *, kind: ConsoleKind | None, metadata: dict[str, str]
) -> str:
    target = _resolve_readable(path)
    resolved_kind = kind or _infer_path_kind(target)
    if not _within_allowed_roots(target):
        return _display_outside_root_fallback(
            target, kind=resolved_kind, metadata=metadata
        )
    result = STATE.add_file_message(
        kind=resolved_kind, metadata=metadata, path=str(target)
    )
    digest = (
        f"{target} ({_human_size(target.stat().st_size)}"
        f"{_language_suffix(target)})"
    )
    return _finish_receipt(result.id, resolved_kind, digest)


def _display_diff(
    old_path: str, new_path: str, *, kind: ConsoleKind | None, metadata: dict[str, str]
) -> str:
    old_target = _resolve_readable(old_path)
    new_target = _resolve_readable(new_path)
    resolved_kind = kind or "diff"
    if not (_within_allowed_roots(old_target) and _within_allowed_roots(new_target)):
        return _display_inline_diff_fallback(old_target, new_target, metadata=metadata)
    result = STATE.add_file_message(
        kind=resolved_kind,
        metadata=metadata,
        old_path=str(old_target),
        new_path=str(new_target),
    )
    digest = (
        f"old={old_target} new={new_target} "
        f"({_human_size(old_target.stat().st_size)} → "
        f"{_human_size(new_target.stat().st_size)})"
    )
    return _finish_receipt(result.id, resolved_kind, digest)


def _display_outside_root_fallback(
    target: Path, *, kind: ConsoleKind, metadata: dict[str, str]
) -> str:
    if not is_textual_file(target):
        raise ValueError(
            f"console.display: {target} is outside the allowed roots and not "
            "textual; cannot fall back to inline publication"
        )
    fallback_meta = {**metadata, "fallback": "outside-allowed-roots"}
    inline_kind: ConsoleKind = kind if kind not in ("file", "image") else "text"
    request = ShowRequest.model_validate(
        {
            "kind": inline_kind,
            "metadata": fallback_meta,
            "content": read_bounded_text(target),
        }
    )
    result = STATE.add_message(request=request)
    digest = f"{target} published inline (outside allowed roots)"
    return _finish_receipt(result.id, inline_kind, digest)


def _display_inline_diff_fallback(
    old_target: Path, new_target: Path, *, metadata: dict[str, str]
) -> str:
    import difflib

    diff_text = "".join(
        difflib.unified_diff(
            read_bounded_text(old_target).splitlines(keepends=True),
            read_bounded_text(new_target).splitlines(keepends=True),
            fromfile=str(old_target),
            tofile=str(new_target),
        )
    )
    fallback_meta = {**metadata, "fallback": "outside-allowed-roots"}
    request = ShowRequest.model_validate(
        {"kind": "diff", "metadata": fallback_meta, "content": diff_text}
    )
    result = STATE.add_message(request=request)
    digest = (
        f"old={old_target} new={new_target} published inline (outside allowed roots)"
    )
    return _finish_receipt(result.id, "diff", digest)


def _resolve_readable(path: str) -> Path:
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError(f"console.display path must be absolute: {path}")
    try:
        target = target.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"console.display: file not found: {path}") from error
    if not target.is_file():
        raise ValueError(f"console.display: not a regular file: {path}")
    try:
        with target.open("rb") as handle:
            handle.read(1)
    except OSError as error:
        raise ValueError(f"console.display: file not readable: {path}") from error
    return target


def _within_allowed_roots(target: Path) -> bool:
    try:
        from ot.console.outbox import current_allowed_roots

        roots = current_allowed_roots()
    except Exception:
        return False
    return any(target.is_relative_to(root) for root in roots)


def _transport_disabled() -> bool:
    """Return True only when config affirmatively disables the direct host."""
    try:
        from ot.config import get_config

        direct = getattr(get_config(), "direct", None)
        host = getattr(direct, "host", None)
        enabled = getattr(host, "enabled", None)
        return enabled is False
    except Exception:
        return False


def _finish_receipt(message_id: str, kind: str, digest: str) -> str:
    receipt = f"console[{message_id}] {kind}: {digest}"
    if len(receipt) > RECEIPT_MAX_CHARS:
        receipt = receipt[: RECEIPT_MAX_CHARS - 1] + "…"
    if _transport_disabled():
        preview = STATE.read_message(id=message_id)
        preview_text = preview.preview.text if preview and preview.preview else ""
        return (
            "console disabled (direct.host.enabled is false) — showing bounded "
            f"preview:\n{preview_text}"
        )
    return receipt


def _coerce_content(content: Any) -> Any:
    if isinstance(content, (str, dict)):
        return content
    if isinstance(content, List):
        return content
    return str(content)


def _infer_value_kind(content: Any) -> ConsoleKind:
    if isinstance(content, List) and content and _is_uniform_records(content):
        return "table"
    if isinstance(content, (dict, List)):
        return "json"
    text = content if isinstance(content, str) else str(content)
    return "markdown" if _looks_like_markdown(text) else "text"


def _is_uniform_records(items: List[Any]) -> bool:
    if not all(isinstance(item, dict) for item in items):
        return False
    base = set(items[0].keys())
    if not base:
        return False
    return all(
        len(base & set(item.keys())) / len(base) >= _TABLE_KEY_OVERLAP
        for item in items
    )


def _looks_like_markdown(text: str) -> bool:
    if "```" in text or "](" in text:
        return True
    return any(
        line.startswith(("# ", "## ", "### ", "- ", "* ", "> "))
        for line in text.splitlines()[:10]
    )


def _infer_path_kind(target: Path) -> ConsoleKind:
    suffix = target.suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix == ".md":
        return "markdown"
    if suffix in (".diff", ".patch"):
        return "diff"
    if suffix == ".json":
        return "json"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if detect_language(target) is not None:
        return "code"
    return "file"


def _value_digest(content: Any, *, kind: str) -> str:
    if kind == "table" and isinstance(content, List) and content and isinstance(content[0], dict):
        columns = [str(key) for key in content[0]][:5]
        top = ", ".join(
            f'"{_clip(_title_value(item), 40)}"' for item in content[:2]
        )
        digest = f"{len(content)} items ({', '.join(columns)})"
        return f"{digest} — top: {top}" if top else digest
    if isinstance(content, dict):
        keys = [str(key) for key in content][:6]
        return f"keys: {', '.join(keys)}" if keys else "empty object"
    if isinstance(content, List):
        return f"{len(content)} items"
    text = content if isinstance(content, str) else str(content)
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    return f"{_clip(first_line, _DIGEST_VALUE_MAX_CHARS)} ({_human_size(len(text.encode('utf-8')))})"


def _title_value(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return str(item)
    for key in ("title", "name", "id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    for value in item.values():
        if isinstance(value, str) and value:
            return value
    return ""


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _language_suffix(target: Path) -> str:
    language = detect_language(target)
    return f", {language}" if language else ""


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
