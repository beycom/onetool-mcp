"""Append operation for the ctx pack."""
from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .format import build_toc, detect_format, normalize_content
from .store import HandleStore, _get_store, _resolve_handle, load_live_meta

log = LogSpan


def ctx_append(
    handle: str,
    content: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Append content to an existing handle.

    Re-detects format on the combined content, regenerates the TOC,
    and rewrites the metadata. Fully synchronous — no background threads.

    Args:
        handle: Context store handle to append to.
        content: Text content to append. Concatenated to existing content.
        store: HandleStore instance (uses session default if not provided).
    """
    with log(span="ctx.append", handle=handle) as s:
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        meta, err = load_live_meta(store, handle)
        if meta is None:
            return {"error": err}

        try:
            existing = store.read_content(handle)
        except OSError:
            return {"error": f"Content not found for handle: {handle}"}

        combined = existing + "\n" + content

        # Re-detect format on combined content, normalise, regenerate TOC
        fmt = detect_format(combined)
        normalised = normalize_content(combined, fmt)
        toc = build_toc(normalised, fmt)

        new_size = len(normalised.encode("utf-8"))
        new_lines = len(normalised.splitlines())

        # Update metadata
        meta["format"] = fmt
        meta["size_bytes"] = new_size
        meta["total_lines"] = new_lines
        meta["status"] = "ready"
        meta["toc"] = toc

        store.write(handle, normalised, meta)

        s.add("size_bytes", new_size)
        s.add("total_lines", new_lines)
        return {
            "handle": handle,
            "status": "ready",
            "format": fmt,
            "size_bytes": new_size,
            "total_lines": new_lines,
        }


__all__ = ["ctx_append"]
