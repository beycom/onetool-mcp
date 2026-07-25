"""Table-of-contents operation for the ctx pack."""

from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, load_live_meta

log = LogSpan


def ctx_toc(
    handle: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Return a format-aware table of contents for a handle.

    TOC data is read from the stored metadata — no content file parse needed.

    Format-specific output:
        markdown: numbered list with level indent and line number
        json/yaml: key list with type/size hints
        text: empty list with explanatory note
    """
    with log(span="ctx.toc", handle=handle) as s:
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        meta, err = load_live_meta(store, handle)
        if meta is None:
            return {"error": err}

        fmt = meta.get("format", "text")
        toc: list[dict[str, Any]] = meta.get("toc", [])

        s.add("format", fmt)
        s.add("entries", len(toc))

        if fmt == "markdown":
            entries: list[str] = []
            for i, entry in enumerate(toc, start=1):
                level = entry.get("level", 1)
                indent = "  " * (level - 1)
                entries.append(
                    f"{indent}{i}. {entry['title']} (H{level}, line {entry['line']})"
                )
            return {
                "handle": handle,
                "format": fmt,
                "toc": toc,
                "sections": len(toc),
                "display": "\n".join(entries) if entries else "(no headings)",
            }

        if fmt in ("json", "yaml"):
            entries_str: list[str] = []
            for entry in toc:
                key = entry.get("key", "")
                type_name = entry.get("type", "")
                size = entry.get("size")
                if key == "[array]":
                    entries_str.append(f"[array] (list, {size} items)")
                elif size is not None:
                    unit = "keys" if type_name == "dict" else "items"
                    entries_str.append(f"{key} ({type_name}, {size} {unit})")
                else:
                    entries_str.append(f"{key} ({type_name})")
            return {
                "handle": handle,
                "format": fmt,
                "toc": toc,
                "display": "\n".join(entries_str) if entries_str else "(empty)",
            }

        # text
        return {
            "handle": handle,
            "format": fmt,
            "toc": [],
            "note": "text format has no structure; use ctx.grep() for pattern matching",
        }


__all__ = ["ctx_toc"]
