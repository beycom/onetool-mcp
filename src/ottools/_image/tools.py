"""Core tool implementations for the image pack.

Implements load(), load_batch(), ask(), and summary() with session dedup,
LRU cache, and LogSpan observability.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from otpack import LogSpan

from .config import get_image_config
from .resize import prepare_for_model
from .sources import resolve_source, validate_image_bytes
from .store import (
    cache_evict as _cache_evict,  # noqa: F401 — exported via __init__
)
from .store import (
    cache_get,
    cache_put,
    find_by_hash,
    image_path,
    load_meta,
    load_raw_bytes,
    save_image,
    save_summary,
)
from .vision import ask_questions, extract_summary

# Track last clipboard handle for metadata/observability only.
# Clipboard reads for ask/summary always refresh via load(img="clip"),
# which deduplicates unchanged content by hash.
_clip_handle: str | None = None


@dataclass(frozen=True)
class LoadedImage:
    """Internal loaded image result shared by public image/display tools."""

    handle: str
    path: str
    source: str
    dims: list[int] | None
    resized: bool
    dedup: bool
    sha256: str | None


def _background_summarise(handle_name: str, model_bytes: bytes) -> None:
    """Run extract_summary() and persist the result — called in a daemon thread.

    Silently skips if the vision model is not configured or if the call fails.
    Does not modify load() return value.
    """
    try:
        config = get_image_config()
        if not config.model:
            return
        result = extract_summary(model_bytes, config)
        if isinstance(result, dict):
            save_summary(handle_name, result)
    except Exception:
        pass  # background thread — never propagate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _auto_handle_name(sha256_hex: str) -> str:
    return f"img_{sha256_hex[:8]}"


def _get_model_bytes(handle_name: str, max_edge: int) -> bytes | None:
    """Return model bytes for a handle — from cache or re-loaded from disk."""
    b64 = cache_get(handle_name)
    if b64 is not None:
        import base64

        return base64.b64decode(b64)

    raw = load_raw_bytes(handle_name)
    if raw is None:
        return None

    prep = prepare_for_model(raw, max_edge)
    cache_put(handle_name, prep.model_bytes)
    return prep.model_bytes


def load(*, img: str, handle: str | None = None, max_edge: int = 1568) -> dict[str, Any]:
    """Load a single image into session storage and return a stable handle.

    Accepts file paths (including ``~``), HTTP/HTTPS URLs, and ``"clip"`` for
    the system clipboard. Deduplicates by content hash — loading the same image
    twice returns the existing handle without writing new files.

    Args:
        img: Source specifier. One of:
            - File path (absolute or relative, may contain ``~``)
            - ``"https://..."`` URL
            - ``"clip"`` for clipboard
            - ``"#handle"`` to verify an existing handle
        handle: Optional custom handle name (e.g. ``"vscode"``). When omitted,
            an auto-generated hash-based name is used (``"img_<8hexchars>"``).
        max_edge: Maximum longest edge (pixels) for in-memory model resize.

    Returns:
        ``{"handle": "#name"}`` on success, or ``{"error": str}`` on failure.

    Note:
        Deduplication by content hash only applies to auto-named handles
        (when ``handle`` is omitted). Loading the same image with a custom
        ``handle`` always creates a new entry, even if the content is identical
        to an existing auto-named handle.

    Example:
        image.load(img="~/screenshots/ui.png")
        image.load(img="https://example.org/diagram.png", handle="ref")
    """
    with LogSpan(span="ot_image.load", source=img) as s:
        try:
            loaded = load_image_source(img=img, handle=handle, max_edge=max_edge)
        except NotImplementedError as e:
            s.add(error="clipboard_unsupported")
            return {"error": str(e)}
        except (FileNotFoundError, IsADirectoryError, ValueError, RuntimeError, ImportError) as e:
            s.add(error=str(e))
            return {"error": str(e)}
        s.add(
            handle=loaded.handle,
            resized=loaded.resized,
            originalDims=loaded.dims,
            dedup=loaded.dedup,
        )
        return {
            "handle": f"#{loaded.handle}",
            "source": loaded.source,
            "dims": loaded.dims,
            "resized": loaded.resized,
            "dedup": loaded.dedup,
        }


def load_image_source(*, img: str, handle: str | None = None, max_edge: int = 1568) -> LoadedImage:
    """Load image bytes into session storage and return internal path metadata."""
    global _clip_handle

    source_type, data = resolve_source(img)
    if source_type == "glob":
        raise ValueError("glob patterns are not supported by load() — use load_batch() instead")
    if source_type == "handle":
        handle_name = str(data)
        meta = load_meta(handle_name)
        if meta is None:
            raise ValueError(f"handle #{handle_name} not found")
        return LoadedImage(
            handle=handle_name,
            path=str(image_path(handle_name)),
            source=str(meta.get("source", "")),
            dims=meta.get("original_dims"),
            resized=bool(meta.get("resized", False)),
            dedup=True,
            sha256=meta.get("hash"),
        )

    raw_bytes = bytes(data)
    validate_image_bytes(raw_bytes, img)
    sha256_hex = _sha256(raw_bytes)

    if handle is None:
        existing = find_by_hash(sha256_hex)
        if existing:
            if cache_get(existing) is None:
                disk = load_raw_bytes(existing)
                if disk is not None:
                    prep = prepare_for_model(disk, max_edge)
                    cache_put(existing, prep.model_bytes)
            if source_type == "clipboard":
                _clip_handle = existing
            existing_meta = load_meta(existing) or {}
            return LoadedImage(
                handle=existing,
                path=str(image_path(existing)),
                source=str(existing_meta.get("source", img)),
                dims=existing_meta.get("original_dims"),
                resized=bool(existing_meta.get("resized", False)),
                dedup=True,
                sha256=sha256_hex,
            )

    handle_name = handle if handle is not None else _auto_handle_name(sha256_hex)
    if handle is not None:
        existing_meta = load_meta(handle_name)
        if existing_meta is not None:
            if existing_meta.get("hash") != sha256_hex:
                raise ValueError(
                    f"handle #{handle_name} already exists with different content. "
                    "Use a different handle name or delete it first."
                )
            if source_type == "clipboard":
                _clip_handle = handle_name
            return LoadedImage(
                handle=handle_name,
                path=str(image_path(handle_name)),
                source=str(existing_meta.get("source", img)),
                dims=existing_meta.get("original_dims"),
                resized=bool(existing_meta.get("resized", False)),
                dedup=True,
                sha256=sha256_hex,
            )

    prep = prepare_for_model(raw_bytes, max_edge)
    source_label = img if source_type in ("url", "file") else source_type
    meta: dict[str, Any] = {
        "handle": handle_name,
        "source": source_label,
        "hash": sha256_hex,
        "original_dims": list(prep.original_dims),
        "model_dims": list(prep.model_dims),
        "resized": prep.resized,
        "max_edge": max_edge,
        "original_format": prep.original_format,
        "created_at": datetime.now(UTC).isoformat(),
        "summary": None,
    }
    save_image(raw_bytes, handle_name, meta)
    cache_put(handle_name, prep.model_bytes)

    if get_image_config().model:
        thread = threading.Thread(
            target=_background_summarise,
            args=(handle_name, prep.model_bytes),
            daemon=True,
        )
        thread.start()

    if source_type == "clipboard":
        _clip_handle = handle_name

    return LoadedImage(
        handle=handle_name,
        path=str(image_path(handle_name)),
        source=source_label,
        dims=list(prep.original_dims),
        resized=prep.resized,
        dedup=False,
        sha256=sha256_hex,
    )


def load_batch(*, img: str | list[str], max_edge: int = 1568) -> list[dict[str, Any]]:
    """Load multiple images and return a list of result dicts.

    Accepts a glob pattern string or a list of source strings (file paths,
    URLs, ``"clip"``). Each source is loaded as if ``load()`` were called
    individually.

    Args:
        img: Glob pattern string (e.g. ``"~/screenshots/*.png"``) or list of
            source strings.
        max_edge: Maximum longest edge (pixels) for model resize.

    Returns:
        List of result dicts. Each item is ``{"handle": "#name"}`` on success
        or ``{"error": str}`` on failure. An empty list is returned for a
        glob that matches no files.

    Example:
        image.load_batch(img="~/screenshots/*.png")
        image.load_batch(img=["~/a.png", "~/b.png"])
    """
    with LogSpan(span="ot_image.load_batch") as s:
        sources: list[str]
        if isinstance(img, list):
            sources = img
        else:
            # Expand glob using Path.glob
            from ot.paths import expand_path

            p = expand_path(img)
            sources = sorted(str(f) for f in p.parent.glob(p.name))

        results: list[dict[str, Any]] = []
        for src in sources:
            results.append(load(img=src, max_edge=max_edge))

        s.add(count=len(sources), loaded=len([r for r in results if "error" not in r]))
        return results


def ask(
    *,
    img: str,
    q: str | list[str],
    max_edge: int = 1568,
) -> dict[str, Any]:
    """Send one or more questions about an image to the vision model.

    Accepts a handle reference (``"#name"``), a file path, URL, or ``"clip"``.
    Multiple questions are batched into a single model call.

    Args:
        img: Image reference — handle (``"#name"`` or bare ``"name"``), file
            path, URL, or ``"clip"``. Clipboard sources are auto-loaded if not
            already in session.
        q: Question string or list of question strings.
        max_edge: Maximum longest edge for resize if the image is loaded fresh.

    Returns:
        ``{"result": list[{"question": str, "answer": str}], "handle": str}`` —
        each entry pairs the original question with its answer. Returns
        ``{"error": str, "handle": str}`` on failure (handle not found, file
        missing, load error).

    Example:
        image.ask(img="#img_a3f7b2c4", q="What framework is shown?")
        image.ask(img="clip", q=["Extract text", "Is this dark mode?"])
    """
    questions = [q] if isinstance(q, str) else list(q)

    with LogSpan(span="ot_image.ask", questionCount=len(questions)) as s:
        config = get_image_config()

        # Resolve handle name
        handle_name: str
        if img in ("clip", "clipboard"):
            # Always re-read clipboard to pick up latest content.
            # load() deduplicates unchanged bytes and updates _clip_handle.
            result = load(img="clip", max_edge=max_edge)
            if "error" in result:
                s.add(error=result["error"])
                return {"error": result["error"], "handle": "clip"}
            handle_name = result["handle"].lstrip("#")
        elif img.startswith("#"):
            handle_name = img[1:]
        elif load_meta(img) is not None:
            # Bare handle name (without # prefix)
            handle_name = img
        else:
            # Auto-load from file/url
            result = load(img=img, max_edge=max_edge)
            if "error" in result:
                s.add(error=result["error"])
                return {"error": result["error"], "handle": img}
            handle_name = result["handle"].lstrip("#")

        s.add(handle=handle_name)

        # Verify handle exists
        if load_meta(handle_name) is None:
            err = f"Error: handle #{handle_name} not found"
            s.add(error=err)
            return {"error": err, "handle": f"#{handle_name}"}

        # Get model bytes (from cache or disk)
        model_bytes = _get_model_bytes(handle_name, max_edge)
        if model_bytes is None:
            err = f"Error: image file not found for handle #{handle_name}"
            s.add(error=err)
            return {"error": err, "handle": f"#{handle_name}"}

        answers = ask_questions(model_bytes, questions, config)

        if len(answers) == 1 and answers[0].startswith("Error:"):
            s.add(error=answers[0])
            return {"error": answers[0], "handle": f"#{handle_name}"}

        pairs = [{"question": q, "answer": a} for q, a in zip(questions, answers, strict=False)]
        return {"result": pairs, "handle": f"#{handle_name}"}


def summary(*, img: str) -> dict[str, Any]:
    """Extract and cache a structured summary of an image.

    Runs a generic extraction prompt (text, mode, type, colours, shapes,
    description) and caches the result in ``meta.json``. Subsequent calls
    for the same handle return the cached result without a model call.

    Args:
        img: Handle reference (``"#name"``), file path, URL, or ``"clip"``.

    Returns:
        ``{"summary": dict, "handle": str, "cached": bool}`` on success, or
        ``{"error": str, "handle": str}`` on failure.

    Example:
        image.summary(img="#img_a3f7b2c4")
    """
    with LogSpan(span="ot_image.summary") as s:
        config = get_image_config()

        # Resolve handle name
        handle_name: str
        if img in ("clip", "clipboard"):
            # Always re-read clipboard to pick up latest content.
            # load() deduplicates unchanged bytes and updates _clip_handle.
            result = load(img="clip", max_edge=config.max_edge)
            if "error" in result:
                s.add(error=result["error"])
                return {"error": result["error"], "handle": "clip"}
            handle_name = result["handle"].lstrip("#")
        elif img.startswith("#"):
            handle_name = img[1:]
        elif load_meta(img) is not None:
            # Bare handle name (without # prefix)
            handle_name = img
        else:
            result = load(img=img)
            if "error" in result:
                s.add(error=result["error"])
                return {"error": result["error"], "handle": img}
            handle_name = result["handle"].lstrip("#")

        s.add(handle=handle_name)

        meta = load_meta(handle_name)
        if meta is None:
            err = f"Error: handle #{handle_name} not found"
            s.add(error=err)
            return {"error": err, "handle": f"#{handle_name}"}

        # Return cached summary if present
        if meta.get("summary") is not None:
            s.add(cached=True)
            return {
                "summary": meta["summary"],
                "handle": f"#{handle_name}",
                "cached": True,
            }

        # Call vision model
        model_bytes = _get_model_bytes(handle_name, config.max_edge)
        if model_bytes is None:
            err = f"Error: image file not found for handle #{handle_name}"
            s.add(error=err)
            return {"error": err, "handle": f"#{handle_name}"}

        result_data = extract_summary(model_bytes, config)
        if isinstance(result_data, str):
            # Error string
            s.add(error=result_data)
            return {"error": result_data, "handle": f"#{handle_name}"}

        save_summary(handle_name, result_data)
        s.add(cached=False)

        return {
            "summary": result_data,
            "handle": f"#{handle_name}",
            "cached": False,
        }


def clip_ask(*, q: str | list[str], max_edge: int = 1568) -> dict[str, Any]:
    """Ask a question about the current clipboard image.

    Shorthand for ``ask(img="clip", q=q, max_edge=max_edge)``.

    Args:
        q: Question string or list of question strings.
        max_edge: Maximum longest edge for resize.

    Returns:
        Same as ``ask()``.
    """
    return ask(img="clip", q=q, max_edge=max_edge)


def clip_view() -> dict[str, Any]:
    """Extract a structured summary of the current clipboard image.

    Shorthand for ``summary(img="clip")``.

    Returns:
        Same as ``summary()``.
    """
    return summary(img="clip")
