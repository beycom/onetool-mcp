"""Read operation for the ctx pack."""
from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .config import Config, _get_config
from .store import HandleStore, _get_store, _resolve_handle, load_live_meta
from .toc import ctx_toc

log = LogSpan


def _truncate_line(line: str, max_chars: int) -> str:
    """Truncate a line to max_chars with a [+N chars] suffix if needed."""
    if len(line) <= max_chars:
        return line
    omitted = len(line) - max_chars
    return line[:max_chars] + f"  [+{omitted} chars]"


def ctx_read(
    handle: str,
    *,
    offset: int = 1,
    limit: int = 100,
    tail: int = 0,
    mode: str = "",
    store: HandleStore | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Return paginated raw content from a stored handle.

    Args:
        handle: Context store handle
        offset: 1-indexed starting line (default 1)
        limit: Max lines to return (default 100)
        tail: Return last N lines, overrides offset/limit
        mode: "toc" → return table of contents; "meta" → return metadata
        store: HandleStore instance (uses session default if not provided)
        config: Pack config (uses module default if not provided)
    """
    with log(span="ctx.read", handle=handle, mode=mode or None) as s:
        if config is None:
            config = _get_config()
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        # Validate args
        if offset < 1:
            return {"error": f"offset must be >= 1 (1-indexed), got {offset}"}
        if limit < 1:
            return {"error": f"limit must be >= 1, got {limit}"}

        meta, err = load_live_meta(store, handle)
        if meta is None:
            return {"error": err}

        # Unknown mode
        if mode and mode not in ("toc", "meta"):
            return {"error": f"Invalid mode {mode!r}. Valid modes: 'toc', 'meta'"}

        # mode=meta — return metadata fields without reading content
        if mode == "meta":
            # Increment access_count
            meta["access_count"] = meta.get("access_count", 0) + 1
            store.update_meta(handle, meta)
            return {
                "handle": meta["handle"],
                "source": meta.get("source", ""),
                "format": meta.get("format", "text"),
                "size_bytes": meta.get("size_bytes", 0),
                "total_lines": meta.get("total_lines", 0),
                "status": meta.get("status", "ready"),
                "created_at": meta.get("created_at"),
                "access_count": meta["access_count"],
            }

        # mode=toc
        if mode == "toc":
            # Increment access_count
            meta["access_count"] = meta.get("access_count", 0) + 1
            store.update_meta(handle, meta)
            return ctx_toc(handle, store=store)

        # Raw content read
        try:
            content = store.read_content(handle)
        except OSError:
            return {"error": f"Content not found for handle: {handle}"}

        lines = content.splitlines()
        total_lines = len(lines)
        max_chars = config.max_line_chars

        if tail > 0:
            actual_limit = min(tail, total_lines)
            start_idx = max(0, total_lines - actual_limit)
            end_idx = total_lines
            offset = start_idx + 1
            limit = actual_limit
        else:
            start_idx = offset - 1
            end_idx = start_idx + limit

        result_lines = [_truncate_line(ln, max_chars) for ln in lines[start_idx:end_idx]]
        returned = len(result_lines)
        has_more = end_idx < total_lines
        end_line = offset + returned - 1

        if total_lines == 0:
            progress = "empty (0 lines)"
        else:
            pct = int((end_line / total_lines) * 100)
            progress = f"lines {offset}-{end_line} of {total_lines} ({pct}%)"

        # Increment access_count
        meta["access_count"] = meta.get("access_count", 0) + 1
        store.update_meta(handle, meta)

        result: dict[str, Any] = {
            "handle": handle,
            "content": "\n".join(result_lines),
            "total_lines": total_lines,
            "returned": returned,
            "offset": offset,
            "has_more": has_more,
            "progress": progress,
            "total_size_bytes": meta.get("size_bytes", 0),
        }
        if has_more:
            next_offset = offset + returned
            result["next_query"] = f"ctx.read('{handle}', offset={next_offset}, limit={limit})"

        s.add("returned", returned)
        s.add("total_lines", total_lines)
        return result


__all__ = ["ctx_read"]
