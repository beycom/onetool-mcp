"""Source resolution for the image pack.

Detects the input type (clipboard, URL, glob, or file path) and loads raw image
bytes from the appropriate source.
"""

from __future__ import annotations

import sys

import httpx

MAX_ORIGINAL_RESPONSE_BYTES = 20 * 1024 * 1024


class ImageSourceError(RuntimeError):
    """Expected source failure that public image tools return as an error."""


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

    Detection order: ``"clip"`` → URL → glob → file path.

    Args:
        img: Source specifier string.

    Returns:
        Tuple of ``(source_type, data)`` where:

        - ``source_type``: one of ``"clipboard"``, ``"url"``, ``"glob"``,
          ``"file"``
        - ``data``: raw bytes for clipboard/url/file or the original ``img``
          string for glob (callers handle globs as an error in ``load()``).

    Raises:
        FileNotFoundError: If a file path does not exist.
        ValueError: If a URL does not return image bytes.
        NotImplementedError: If clipboard is requested on Linux.
        RuntimeError: For other unrecoverable load failures.
    """
    if img in ("clip", "clipboard"):
        return "clipboard", _grab_clipboard()

    if img.startswith("#"):
        raise ImageSourceError(
            "image.load() accepts sources, not image handle references"
        )

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


def _content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value)
    except ValueError as exc:
        raise ImageSourceError(
            f"URL returned an invalid content-length: {value!r}"
        ) from exc
    if length < 0:
        raise ImageSourceError(f"URL returned an invalid content-length: {value!r}")
    return length


def _fetch_url(url: str) -> bytes:
    """Stream bounded image bytes from a URL using the shared HTTP client.

    Args:
        url: Full HTTP/HTTPS URL to download.

    Returns:
        Raw response bytes.

    Raises:
        ImageSourceError: For expected status, network, content, or size errors.
    """
    from ot.http_client import _get_shared_client
    from ot.logging import LogSpan

    with LogSpan(span="ot_image.fetch_url", url=url) as s:
        try:
            client = _get_shared_client()
            with client.stream("GET", url, timeout=30.0) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                s.add(status=response.status_code, contentType=content_type)
                if not content_type.lower().startswith("image/"):
                    raise ImageSourceError(
                        f"URL did not return an image (content-type: {content_type!r})"
                    )

                declared_length = _content_length(response.headers)
                if (
                    declared_length is not None
                    and declared_length > MAX_ORIGINAL_RESPONSE_BYTES
                ):
                    raise ImageSourceError(
                        "remote image exceeds the 20 MiB original-response limit"
                    )

                data = bytearray()
                for chunk in response.iter_bytes():
                    if len(data) + len(chunk) > MAX_ORIGINAL_RESPONSE_BYTES:
                        raise ImageSourceError(
                            "remote image exceeds the 20 MiB original-response limit"
                        )
                    data.extend(chunk)
                return bytes(data)
        except httpx.HTTPError as exc:
            s.add(error=str(exc))
            raise ImageSourceError(f"failed to download image: {exc}") from exc


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
            "Pillow is required for clipboard capture. Install with: pip install Pillow"
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
