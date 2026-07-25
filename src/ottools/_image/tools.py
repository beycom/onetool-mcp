"""Core tool implementations for the image pack.

Implements load(), load_batch(), ask(), and summary() with session dedup,
LRU cache, and LogSpan observability.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from otpack import LogSpan

from .config import get_image_config
from .resize import prepare_for_model
from .sources import ImageSourceError, resolve_source, validate_image_bytes
from .store import (
    cache_evict as _cache_evict,  # noqa: F401 — exported via __init__
)
from .store import (
    cache_get,
    cache_put,
    handle_name_for_hash,
    load_meta,
    load_raw_bytes,
    parse_public_handle,
    public_handle,
    save_image,
    save_summary,
)
from .vision import ask_questions, extract_summary


def _background_summarise(handle_name: str, model_bytes: bytes) -> None:
    """Run extract_summary() and persist the result — called in a daemon thread.

    Logs failures because daemon-thread exceptions cannot propagate to load().
    """
    try:
        config = get_image_config()
        result = extract_summary(model_bytes, config)
        if isinstance(result, dict):
            save_summary(handle_name, result)
    except Exception:
        logger.exception("background image summary failed for {}", handle_name)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _auto_handle_name(sha256_hex: str) -> str:
    return handle_name_for_hash(sha256_hex)


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
        img: Canonical handle (``"#img_<64hex>"``), file path, URL, or
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
        return parse_public_handle(str(result["handle"])), None
    if img.startswith("#"):
        try:
            return parse_public_handle(img), None
        except ValueError as exc:
            return "", {"error": str(exc), "handle": img}
    if img.startswith("img_"):
        return "", {
            "error": "invalid image reference; canonical handles require a # prefix",
            "handle": img,
        }
    # Auto-load from file/url
    result = load(img=img, max_edge=max_edge)
    if "error" in result:
        return "", {"error": result["error"], "handle": img}
    return parse_public_handle(str(result["handle"])), None


def load(*, img: str, max_edge: int = 1568) -> dict[str, Any]:
    """Load a single image into session storage and return a stable handle.

    Accepts file paths (including ``~``), HTTP/HTTPS URLs, and ``"clip"`` for
    the system clipboard. Deduplicates by content hash — loading the same image
    twice returns the existing handle without writing new files.

    Args:
        img: Source specifier. One of:
            - File path (absolute or relative, may contain ``~``)
            - ``"https://..."`` URL
            - ``"clip"`` for clipboard
        max_edge: Maximum longest edge (pixels) for in-memory model resize.

    Returns:
        ``{"handle": "#img_<64hex>", ...}`` on success, or
        ``{"error": str}`` on failure.

    Example:
        image.load(img="~/screenshots/ui.png")
        image.load(img="https://example.org/diagram.png")
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
        except (
            FileNotFoundError,
            ImageSourceError,
            IsADirectoryError,
            ValueError,
        ) as e:
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
        handle_name = _auto_handle_name(sha256_hex)
        try:
            existing_meta = load_meta(handle_name)
            if existing_meta is not None:
                if cache_get(handle_name) is None:
                    disk = load_raw_bytes(handle_name)
                    if disk is None:
                        raise ValueError(
                            f"image file not found for {public_handle(handle_name)}"
                        )
                    prep = prepare_for_model(disk, max_edge)
                    cache_put(handle_name, prep.model_bytes)
                s.add(handle=handle_name, dedup=True)
                return {
                    "handle": public_handle(handle_name),
                    "source": existing_meta.get("source", img),
                    "dims": existing_meta.get("original_dims"),
                    "resized": existing_meta.get("resized", False),
                    "dedup": True,
                }
        except ImportError as e:
            s.add(error=str(e))
            return {"error": f"missing optional dependency — {e}"}
        except (OSError, ValueError) as e:
            s.add(error=str(e))
            return {"error": str(e)}

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
            "original_format": detected_format,
            "created_at": datetime.now(UTC).isoformat(),
            "summary": None,
        }
        try:
            save_image(raw_bytes, handle_name, image_meta, fmt=detected_format)
            cache_put(handle_name, prep.model_bytes)
        except (OSError, ValueError) as e:
            s.add(error=str(e))
            return {"error": str(e)}

        if get_image_config().model:
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
            "handle": public_handle(handle_name),
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
        List of result dicts. Each item contains a canonical ``handle`` on
        success or ``{"error": str}`` on failure. An empty list is returned
        for a glob that matches no files.

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
) -> dict[str, Any]:
    """Send one or more questions about one or more images to the vision model.

    Accepts canonical handle references, file paths, URLs, or ``"clip"``.
    A list of image references (max 8) sends all images in a single model
    call — questions can reference "image 1" / "image 2" for comparisons.
    Multiple questions are batched into a single model call.

    Args:
        img: Image reference or list of references — each entry may be a
            canonical handle (``"#img_<64hex>"``), file path, URL, or
            ``"clip"``. Sources not already in session are auto-loaded.
        q: Question string or list of question strings.
        max_edge: Maximum longest edge for resize if an image is loaded fresh.

    Returns:
        For string ``img``: ``{"result": pairs, "handle": "#name"}``.
        For list ``img`` (including single-element lists):
        ``{"result": pairs, "handles": ["#a", "#b", ...]}``.
        ``pairs`` is ``list[{"question": str, "answer": str}]``. Returns
        ``{"error": str, "handle": str}`` on failure (empty list, more than
        8 images, handle not found, file missing, load error) — resolution
        failures identify the failing reference and skip the model call.

    Example:
        image.ask(
            img="#img_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            q="What framework is shown?",
        )
        image.ask(img="clip", q=["Extract text", "Is this dark mode?"])
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
            handle_ref = public_handle(handle_name)
            try:
                meta = load_meta(handle_name)
                model_bytes = (
                    _get_model_bytes(handle_name, max_edge)
                    if meta is not None
                    else None
                )
            except (OSError, ValueError) as exc:
                err_msg = f"Error: {exc}"
                s.add(error=err_msg)
                return {"error": err_msg, "handle": handle_ref}
            if meta is None:
                err_msg = f"Error: handle {handle_ref} not found"
                s.add(error=err_msg)
                return {"error": err_msg, "handle": handle_ref}
            if model_bytes is None:
                err_msg = f"Error: image file not found for handle {handle_ref}"
                s.add(error=err_msg)
                return {"error": err_msg, "handle": handle_ref}
            images.append(model_bytes)

        answers = ask_questions(images, questions, config)

        if len(answers) == 1 and answers[0].startswith("Error:"):
            s.add(error=answers[0])
            return {"error": answers[0], "handle": public_handle(handle_names[0])}

        pairs = [
            {"question": q, "answer": a}
            for q, a in zip(questions, answers, strict=False)
        ]
        if is_multi:
            return {
                "result": pairs,
                "handles": [public_handle(h) for h in handle_names],
            }
        return {"result": pairs, "handle": public_handle(handle_names[0])}


def summary(*, img: str) -> dict[str, Any]:
    """Extract and cache a structured summary of an image.

    Runs a generic extraction prompt (text, mode, type, colours, shapes,
    description) and caches the result in ``meta.json``. Subsequent calls
    for the same handle return the cached result without a model call.

    Args:
        img: Canonical handle reference, file path, URL, or ``"clip"``.

    Returns:
        ``{"summary": dict, "handle": str, "cached": bool}`` on success, or
        ``{"error": str, "handle": str}`` on failure.

    Example:
        image.summary(
            img="#img_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )
    """
    with LogSpan(span="ot_image.summary") as s:
        config = get_image_config()

        # Resolve handle name
        handle_name, err = _resolve_handle_name(img, config.max_edge)
        if err is not None:
            s.add(error=err["error"])
            return err

        s.add(handle=handle_name)

        handle_ref = public_handle(handle_name)
        try:
            meta = load_meta(handle_name)
        except (OSError, ValueError) as exc:
            err_msg = f"Error: {exc}"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": handle_ref}
        if meta is None:
            err_msg = f"Error: handle {handle_ref} not found"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": handle_ref}

        # Return cached summary if present
        if meta.get("summary") is not None:
            s.add(cached=True)
            return {
                "summary": meta["summary"],
                "handle": handle_ref,
                "cached": True,
            }

        # Call vision model
        try:
            model_bytes = _get_model_bytes(handle_name, config.max_edge)
        except (OSError, ValueError) as exc:
            err_msg = f"Error: {exc}"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": handle_ref}
        if model_bytes is None:
            err_msg = f"Error: image file not found for handle {handle_ref}"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": handle_ref}

        result_data = extract_summary(model_bytes, config)
        if isinstance(result_data, str):
            # Error string
            s.add(error=result_data)
            return {"error": result_data, "handle": handle_ref}

        try:
            save_summary(handle_name, result_data)
        except (OSError, ValueError) as exc:
            err_msg = f"Error: {exc}"
            s.add(error=err_msg)
            return {"error": err_msg, "handle": handle_ref}
        s.add(cached=False)

        return {
            "summary": result_data,
            "handle": handle_ref,
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
