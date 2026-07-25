"""Write operation for the ctx pack."""
from __future__ import annotations

import secrets
from typing import Any

from ot.logging import LogSpan

from .config import Config, _get_config
from .format import build_toc, detect_format, normalize_content
from .store import HandleStore, _get_store, expires_at_ts, now_ts

log = LogSpan


def ctx_write(
    content: str | dict[str, Any],
    *,
    source: str = "",
    verbose: bool = False,
    store: HandleStore | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Store content synchronously and return a handle dict immediately.

    Format is detected at write time. JSON content is pretty-printed.
    The handle is ready immediately — no background indexing.

    Args:
        content: Text content to store, or a runner auto-offload handle dict
            (``{"handle": "...", ...}``) — transparently dereferenced.
        source: Optional label for the content origin (e.g. tool name or URL).
        verbose: When ``True``, include ``preview`` in the response.
        store: HandleStore instance (uses session default if not provided).
        config: Pack config (uses module default if not provided).
    """
    with log(span="ctx.write", source=source or None) as s:
        if config is None:
            config = _get_config()
        if store is None:
            store = _get_store()

        # Dereference runner auto-offload handle dict transparently
        if isinstance(content, dict) and "handle" in content:
            ref_handle = content["handle"]
            if not store.exists(ref_handle):
                return {"error": f"Failed to dereference handle {ref_handle!r}: handle not found"}
            try:
                content = store.read_content(ref_handle)
            except OSError:
                return {"error": f"Failed to dereference handle {ref_handle!r}: handle not found"}

        assert isinstance(content, str)

        # Detect format, normalise, build TOC
        fmt = detect_format(content)
        normalised = normalize_content(content, fmt)
        toc = build_toc(normalised, fmt)

        size_bytes = len(normalised.encode("utf-8"))
        total_lines = len(normalised.splitlines())
        while True:
            handle = secrets.token_hex(16)
            meta: dict[str, Any] = {
                "handle": handle,
                "source": source,
                "format": fmt,
                "size_bytes": size_bytes,
                "total_lines": total_lines,
                "status": "ready",
                "created_at": now_ts(),
                "expires_at": expires_at_ts(config.ttl),
                "toc": toc,
            }
            try:
                store.write(handle, normalised, meta)
            except FileExistsError:
                continue
            break

        result: dict[str, Any] = {
            "handle": handle,
            "source": source,
            "format": fmt,
            "size_bytes": size_bytes,
            "total_lines": total_lines,
            "status": "ready",
        }

        if verbose:
            lines = normalised.splitlines()
            preview_lines = [ln for ln in lines if ln.strip()][:5]
            result["preview"] = "\n".join(preview_lines)

        s.add("handle", handle)
        s.add("size_bytes", size_bytes)
        s.add("total_lines", total_lines)
        return result


__all__ = ["ctx_write"]
