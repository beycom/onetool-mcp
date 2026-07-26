"""Core tool implementations for the image pack.

Implements load(), load_batch(), ask(), and summary() with session dedup,
LRU cache, and LogSpan observability.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.logging import LogEntry
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
    load_meta,
    load_raw_bytes,
    save_image,
    save_summary,
)
from .vision import ask_questions, extract_summary

if TYPE_CHECKING:
    from ot.config.routing import ReasoningEffort


def _background_summarise(handle_name: str, model_bytes: bytes) -> None:
    """Run extract_summary() and persist the result — called in a daemon thread.

    Silently skips if the vision model is not configured or if the call fails.
    Does not modify load() return value.
    """
    try:
        config = get_image_config()
        result = extract_summary(model_bytes, config)
        if isinstance(result, dict):
            save_summary(handle_name, result)
        else:
            logger.debug(
                LogEntry(
                    event="ot_image.background_summary.unavailable",
                    handle=handle_name,
                )
            )
    except Exception as exc:
        logger.warning(
            LogEntry(
                event="ot_image.background_summary.failed",
                handle=handle_name,
                errorType=type(exc).__name__,
            )
        )


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


def _resolve_handle_name(img: str, max_edge: int) -> tuple[str, dict[str, Any] | None]:
    """Resolve an image reference to a handle name, auto-loading when needed.

    Clipboard sources are always re-read so the latest content is picked up;
    ``load()`` deduplicates unchanged bytes by hash. File/URL sources that are
    not already loaded are loaded fresh.

    Args:
        img: Handle (``"#name"`` or bare ``"name"``), file path, URL, or
            ``"clip"``/``"clipboard"``.
        max_edge: Maximum longest edge passed to ``load()`` for fresh loads.

    Returns:
        ``(handle_name, None)`` on success, or ``("", error_dict)`` on failure
        where ``error_dict`` is ready to return from the calling tool.
    """
    if img in ("clip", "clipboard"):
        result = load(img="clip", max_edge=max_edge)
        if "error" in result:
            return "", {"error": result["error"], "handle": "clip"}
        return result["handle"].lstrip("#"), None
    if img.startswith("#"):
        return img[1:], None
    if load_meta(img) is not None:
        # Bare handle name (without # prefix)
        return img, None
    # Auto-load from file/url
    result = load(img=img, max_edge=max_edge)
    if "error" in result:
        return "", {"error": result["error"], "handle": img}
    return result["handle"].lstrip("#"), None


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
        # Resolve source type and raw bytes
        try:
            source_type, data = resolve_source(img)
        except NotImplementedError as e:
            s.add(error="clipboard_unsupported")
            return {"error": str(e)}
        except ImportError as e:
            s.add(error=str(e))
            return {"error": f"missing optional dependency — {e}"}
        except (FileNotFoundError, IsADirectoryError, ValueError, RuntimeError) as e:
            s.add(error=str(e))
            return {"error": str(e)}

        if source_type == "glob":
            s.add(error="glob_in_load")
            return {
                "error": (
                    "glob patterns are not supported by load() — "
                    "use load_batch() instead"
                )
            }

        if source_type == "handle":
            handle_name = str(data)
            handle_meta = load_meta(handle_name)
            if handle_meta is None:
                s.add(error="handle_not_found")
                return {"error": f"handle #{handle_name} not found"}
            s.add(handle=handle_name, passthrough=True)
            return {
                "handle": f"#{handle_name}",
                "source": handle_meta.get("source", ""),
                "dims": handle_meta.get("original_dims"),
                "resized": handle_meta.get("resized", False),
                "dedup": True,
            }

        assert isinstance(data, bytes)
        raw_bytes = bytes(data)

        try:
            # Detected format drives the stored extension. Do NOT use
            # prep.original_format for this — SVG rasterises to PNG before
            # Pillow sees it.
            detected_format = validate_image_bytes(raw_bytes, img)
        except ValueError as e:
            s.add(error=str(e))
            return {"error": str(e)}

        sha256_hex = _sha256(raw_bytes)

        # Dedup by hash (auto-handles only — named handles may differ intentionally)
        if handle is None:
            existing = find_by_hash(sha256_hex)
            if existing:
                # Re-populate cache if evicted
                if cache_get(existing) is None:
                    disk = load_raw_bytes(existing)
                    if disk is not None:
                        try:
                            prep = prepare_for_model(disk, max_edge)
                        except ImportError as e:
                            s.add(error=str(e))
                            return {"error": f"missing optional dependency — {e}"}
                        cache_put(existing, prep.model_bytes)
                s.add(handle=existing, dedup=True)
                existing_meta = load_meta(existing)
                return {
                    "handle": f"#{existing}",
                    "source": (existing_meta or {}).get("source", img),
                    "dims": (existing_meta or {}).get("original_dims"),
                    "resized": (existing_meta or {}).get("resized", False),
                    "dedup": True,
                }

        handle_name = handle if handle is not None else _auto_handle_name(sha256_hex)

        # Named handle collision check
        if handle is not None:
            existing_meta = load_meta(handle_name)
            if existing_meta is not None:
                if existing_meta.get("hash") != sha256_hex:
                    s.add(error="handle_collision")
                    return {
                        "error": (
                            f"handle #{handle_name} already exists with different "
                            "content. Use a different handle name or delete it first."
                        )
                    }
                # Same content, same named handle — dedup
                s.add(handle=handle_name, dedup=True)
                return {
                    "handle": f"#{handle_name}",
                    "source": existing_meta.get("source", img),
                    "dims": existing_meta.get("original_dims"),
                    "resized": existing_meta.get("resized", False),
                    "dedup": True,
                }

        try:
            prep = prepare_for_model(raw_bytes, max_edge)
        except ImportError as e:
            s.add(error=str(e))
            return {"error": f"missing optional dependency — {e}"}

        source_label = img if source_type in ("url", "file") else source_type
        image_meta: dict[str, Any] = {
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
        save_image(raw_bytes, handle_name, image_meta, fmt=detected_format)
        cache_put(handle_name, prep.model_bytes)

        # Spawn background summary — silently skipped if model not set
        thread = threading.Thread(
            target=_background_summarise,
            args=(handle_name, prep.model_bytes),
            daemon=True,
        )
        thread.start()

        s.add(
            handle=handle_name,
            sourceType=source_type,
            resized=prep.resized,
            originalDims=list(prep.original_dims),
        )
        return {
            "handle": f"#{handle_name}",
            "source": source_label,
            "dims": list(prep.original_dims),
            "resized": prep.resized,
            "dedup": False,
        }


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


# Providers commonly cap images per request; 8 keeps payloads sane at
# max_edge 1568.
_MAX_ASK_IMAGES = 8


def ask(
    *,
    img: str | list[str],
    q: str | list[str],
    max_edge: int = 1568,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> dict[str, Any]:
    """Send one or more questions about one or more images to the vision model.

    Accepts handle references (``"#name"``), file paths, URLs, or ``"clip"``.
    A list of image references (max 8) sends all images in a single model
    call — questions can reference "image 1" / "image 2" for comparisons.
    Multiple questions are batched into a single model call.

    Args:
        img: Image reference or list of references — each entry may be a
            handle (``"#name"`` or bare ``"name"``), file path, URL, or
            ``"clip"``. Sources not already in session are auto-loaded.
        q: Question string or list of question strings.
        max_edge: Maximum longest edge for resize if an image is loaded fresh.
        model: Model shortcut, concrete ID, or proxy alias override.
        effort: Reasoning effort override: ``low``, ``medium``, or ``high``.

    Returns:
        For string ``img``: ``{"result": pairs, "handle": "#name"}``.
        For list ``img`` (including single-element lists):
        ``{"result": pairs, "handles": ["#a", "#b", ...]}``.
        ``pairs`` is ``list[{"question": str, "answer": str}]``. Returns
        ``{"error": str, "handle": str}`` on failure (empty list, more than
        8 images, handle not found, file missing, load error) — resolution
        failures identify the failing reference and skip the model call.

    Example:
        image.ask(img="#img_a3f7b2c4", q="What framework is shown?")
        image.ask(img="clip", q=["Extract text", "Is this dark mode?"])
        image.ask(img=["#before", "#after"], q="What differs between image 1 and image 2?")
    """
    questions = [q] if isinstance(q, str) else list(q)
    is_multi = isinstance(img, list)
    img_refs = list(img) if isinstance(img, list) else [img]

    with LogSpan(
        span="ot_image.ask", questionCount=len(questions), imageCount=len(img_refs)
    ) as s:
        if not img_refs:
            s.add(error="empty_img_list")
            return {"error": "img list is empty"}
        if len(img_refs) > _MAX_ASK_IMAGES:
            s.add(error="too_many_images")
            return {
                "error": (
                    f"too many images ({len(img_refs)}) — "
                    f"ask() accepts at most {_MAX_ASK_IMAGES} images per call"
                )
            }

        config = get_image_config()

        # Resolve every reference before any model call (fail fast)
        handle_names: list[str] = []
        for ref in img_refs:
            handle_name, err = _resolve_handle_name(ref, max_edge)
            if err is not None:
                s.add(error=err["error"])
                return err
            handle_names.append(handle_name)

        s.add(handles=handle_names)

        images: list[bytes] = []
        for handle_name in handle_names:
            if load_meta(handle_name) is None:
                err_msg = f"Error: handle #{handle_name} not found"
                s.add(error=err_msg)
                return {"error": err_msg, "handle": f"#{handle_name}"}
            model_bytes = _get_model_bytes(handle_name, max_edge)
            if model_bytes is None:
                err_msg = f"Error: image file not found for handle #{handle_name}"
                s.add(error=err_msg)
                return {"error": err_msg, "handle": f"#{handle_name}"}
            images.append(model_bytes)

        answers = ask_questions(
            images,
            questions,
            config,
            model=model,
            effort=effort,
        )

        if len(answers) == 1 and answers[0].startswith("Error:"):
            s.add(error=answers[0])
            return {"error": answers[0], "handle": f"#{handle_names[0]}"}

        pairs = [{"question": q, "answer": a} for q, a in zip(questions, answers, strict=False)]
        if is_multi:
            return {"result": pairs, "handles": [f"#{h}" for h in handle_names]}
        return {"result": pairs, "handle": f"#{handle_names[0]}"}


def summary(
    *,
    img: str,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> dict[str, Any]:
    """Extract and cache a structured summary of an image.

    Runs a generic extraction prompt (text, mode, type, colours, shapes,
    description) and caches the result in ``meta.json``. Subsequent calls
    for the same handle return the cached result without a model call.

    Args:
        img: Handle reference (``"#name"``), file path, URL, or ``"clip"``.
        model: Model shortcut, concrete ID, or proxy alias override.
        effort: Reasoning effort override: ``low``, ``medium``, or ``high``.

    Returns:
        ``{"summary": dict, "handle": str, "cached": bool}`` on success, or
        ``{"error": str, "handle": str}`` on failure.

    Example:
        image.summary(img="#img_a3f7b2c4")
    """
    with LogSpan(span="ot_image.summary") as s:
        config = get_image_config()

        # Resolve handle name
        handle_name, err = _resolve_handle_name(img, config.max_edge)
        if err is not None:
            s.add(error=err["error"])
            return err

        s.add(handle=handle_name)

        meta = load_meta(handle_name)
        if meta is None:
            err_msg = f"Error: handle #{handle_name} not found"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": f"#{handle_name}"}

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
            err_msg = f"Error: image file not found for handle #{handle_name}"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": f"#{handle_name}"}

        result_data = extract_summary(
            model_bytes,
            config,
            model=model,
            effort=effort,
        )
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


def clip_ask(
    *,
    q: str | list[str],
    max_edge: int = 1568,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> dict[str, Any]:
    """Ask a question about the current clipboard image.

    Shorthand for ``ask(img="clip", q=q, max_edge=max_edge)``.

    Args:
        q: Question string or list of question strings.
        max_edge: Maximum longest edge for resize.
        model: Model shortcut, concrete ID, or proxy alias override.
        effort: Reasoning effort override: ``low``, ``medium``, or ``high``.

    Returns:
        Same as ``ask()``.

    Example:
        image.clip_ask(q="Extract the visible error message.")
    """
    return ask(
        img="clip",
        q=q,
        max_edge=max_edge,
        model=model,
        effort=effort,
    )


def clip_view(
    *,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> dict[str, Any]:
    """Extract a structured summary of the current clipboard image.

    Shorthand for ``summary(img="clip")``.

    Args:
        model: Model shortcut, concrete ID, or proxy alias override.
        effort: Reasoning effort override: ``low``, ``medium``, or ``high``.

    Returns:
        Same as ``summary()``.

    Example:
        image.clip_view(model="terra", effort="medium")
    """
    return summary(img="clip", model=model, effort=effort)
