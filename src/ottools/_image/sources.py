"""Source resolution for the image pack.

Detects the input type (clipboard, handle reference, URL, glob, file path)
and loads raw image bytes from the appropriate source.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Supported format magic bytes for validation
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"RIFF", "WEBP"),  # verified below against bytes 8-12
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
]

# ISOBMFF ftyp brands for HEIC/HEIF
_HEIF_BRANDS: frozenset[bytes] = frozenset(
    {b"heic", b"heix", b"heif", b"heis", b"heim", b"hevm", b"hevs", b"mif1", b"msf1"}
)

# ISOBMFF ftyp brands for AVIF
_AVIF_BRANDS: frozenset[bytes] = frozenset({b"avif", b"avis"})


def validate_image_bytes(data: bytes, label: str = "") -> str:
    """Validate that bytes look like a supported image format.

    Args:
        data: Raw image bytes to check.
        label: Optional label for error messages (e.g. file path).

    Returns:
        Detected format string (e.g. "PNG", "JPEG", "HEIC", "AVIF").

    Raises:
        ValueError: If the format is not recognised.
    """
    # ISOBMFF container (HEIC/HEIF/AVIF): ftyp box starts at offset 4
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in _HEIF_BRANDS:
            return "HEIC"
        if brand in _AVIF_BRANDS:
            return "AVIF"

    for magic, fmt in _MAGIC:
        if data[: len(magic)] == magic:
            if fmt == "WEBP" and data[8:12] != b"WEBP":
                continue
            return fmt

    # SVG: text-based XML — strip UTF-8 BOM and whitespace before checking
    stripped = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped[:4].lower() == b"<svg" or stripped[:5] == b"<?xml":
        return "SVG"

    suffix = f" for {label}" if label else ""
    raise ValueError(
        f"Unsupported image format{suffix}. Supported: PNG, JPEG, GIF, WebP, TIFF, HEIC, AVIF, SVG"
    )


def _is_url(img: str) -> bool:
    return img.startswith("http://") or img.startswith("https://")


def _is_glob(img: str) -> bool:
    return any(c in img for c in ("*", "?", "["))


def resolve_source(img: str) -> tuple[str, bytes | str]:
    """Detect image source type and load raw bytes.

    Detection order: ``"clip"`` → ``"#handle"`` → URL → glob → file path.

    Args:
        img: Source specifier string.

    Returns:
        Tuple of ``(source_type, data)`` where:

        - ``source_type``: one of ``"clipboard"``, ``"handle"``, ``"url"``,
          ``"glob"``, ``"file"``
        - ``data``: raw bytes for clipboard/url/file; handle name str (without
          ``#``) for handle references; the original ``img`` string for glob
          (callers handle globs as an error in ``load()``).

    Raises:
        FileNotFoundError: If a file path does not exist.
        ValueError: If a URL does not return image bytes.
        NotImplementedError: If clipboard is requested on Linux.
        RuntimeError: For other unrecoverable load failures.
    """
    if img in ("clip", "clipboard"):
        return "clipboard", _grab_clipboard()

    if img.startswith("#"):
        return "handle", img[1:]

    if _is_url(img):
        return "url", _fetch_url(img)

    if _is_glob(img):
        return "glob", img

    return "file", _load_file(img)


def _load_file(path: str) -> bytes:
    """Read image bytes from a file path.

    Args:
        path: File path (may contain ``~``).

    Returns:
        Raw file bytes.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path is a directory.
        ValueError: If the file format is not supported.
    """
    from ot.paths import expand_path

    p = expand_path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not p.is_file():
        raise IsADirectoryError(f"Path is a directory: {path}")
    raw = p.read_bytes()
    validate_image_bytes(raw, path)
    return raw


def _fetch_url(url: str) -> bytes:
    """Download image bytes from a URL using the shared HTTP client.

    Args:
        url: Full HTTP/HTTPS URL to download.

    Returns:
        Raw response bytes.

    Raises:
        ValueError: If the response content-type is not ``image/*``.
        RuntimeError: On HTTP or network errors.
    """
    from ot.http_client import _get_shared_client
    from ot.logging import LogSpan

    with LogSpan(span="ot_image.fetch_url", url=url) as s:
        try:
            client = _get_shared_client()
            response = client.get(url, timeout=30.0)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            s.add(status=response.status_code, contentType=content_type)
            if not content_type.startswith("image/"):
                raise ValueError(
                    f"URL did not return an image (content-type: {content_type!r})"
                )
            return response.content
        except Exception as e:
            s.add(error=str(e))
            raise


def _grab_clipboard() -> bytes:
    """Capture the current clipboard image.

    Returns:
        PNG bytes of the clipboard image.

    Raises:
        NotImplementedError: On Linux (not yet supported).
        ValueError: If the clipboard contains no image.
        ImportError: If Pillow is not installed.
    """
    if sys.platform == "linux":
        raise NotImplementedError(
            "Clipboard capture is not supported on Linux. "
            "Use a file path or URL instead."
        )

    try:
        from PIL import Image, ImageGrab
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for clipboard capture. "
            "Install with: pip install Pillow"
        ) from exc

    import io

    img = ImageGrab.grabclipboard()
    if img is None:
        raise ValueError("No image found in clipboard")
    if isinstance(img, list):
        if not img:
            raise ValueError("No image found in clipboard")
        return _load_file(img[0])
    if not isinstance(img, Image.Image):
        raise ValueError(
            f"Clipboard does not contain an image (got {type(img).__name__})"
        )

    buf = io.BytesIO()
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    img.save(buf, format="PNG")
    return buf.getvalue()


def resolve_clipboard_file_path() -> Path:
    """Return the first existing file path from clipboard file-list or text."""
    if sys.platform == "linux":
        raise NotImplementedError(
            "Clipboard path capture is not supported on Linux. "
            "Use display.show(kind='file', path=...) instead."
        )

    clipboard = _grab_clipboard_object()
    if isinstance(clipboard, list):
        if not clipboard:
            raise ValueError("No file path found in clipboard")
        return _existing_file_path(str(clipboard[0]))

    text = _clipboard_text()
    if text:
        return _existing_file_path(text.strip())

    raise ValueError("Clipboard does not contain an image or existing file path")


def clipboard_contains_image_object() -> bool:
    """Return whether clipboard currently contains an in-memory image object."""
    if sys.platform == "linux":
        return False
    try:
        from PIL import Image
    except ImportError:
        return False
    return isinstance(_grab_clipboard_object(), Image.Image)


def _grab_clipboard_object() -> object:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for clipboard capture. "
            "Install with: pip install Pillow"
        ) from exc
    return ImageGrab.grabclipboard()


def _clipboard_text() -> str | None:
    if sys.platform == "darwin":
        import subprocess

        result = subprocess.run(
            ["pbpaste"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout if result.returncode == 0 else None
    try:
        import tkinter
    except ImportError:
        return None
    root = tkinter.Tk()
    root.withdraw()
    try:
        return str(root.clipboard_get())
    except tkinter.TclError:
        return None
    finally:
        root.destroy()


def _existing_file_path(path_text: str) -> Path:
    from ot.paths import expand_path

    path = expand_path(path_text)
    if not path.is_file():
        raise ValueError(f"Clipboard text is not an existing file path: {path_text}")
    return path
