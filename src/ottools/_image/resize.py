"""In-memory image resize for model upload.

The original image bytes are never modified. Resize happens entirely in memory
and the resized bytes are used only for vision model uploads.
"""

from __future__ import annotations

import io
from typing import NamedTuple


class PreparedImage(NamedTuple):
    """Result of prepare_for_model."""

    model_bytes: bytes
    """PNG bytes ready for model upload (resized if necessary)."""

    original_dims: tuple[int, int]
    """Original (width, height) in pixels."""

    model_dims: tuple[int, int]
    """Model-upload (width, height) in pixels."""

    resized: bool
    """True if the image was resized to fit max_edge."""

    original_format: str
    """Detected source format (e.g. 'PNG', 'JPEG')."""


def prepare_for_model(raw_bytes: bytes, max_edge: int) -> PreparedImage:
    """Resize image in-memory (if needed) and encode to PNG for model upload.

    Preserves aspect ratio. The original ``raw_bytes`` are not modified.

    Args:
        raw_bytes: Original image bytes (any Pillow-supported format).
        max_edge: Maximum allowed longest edge in pixels. Images within this
            limit are encoded to PNG unchanged.

    Returns:
        PreparedImage with ``model_bytes`` (PNG), dimension info, and resize flag.
    """
    from PIL import Image

    # SVG: rasterize to PNG using resvg-py before Pillow
    stripped = raw_bytes.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped[:4].lower() == b"<svg" or stripped[:5] == b"<?xml":
        try:
            import resvg_py
        except ImportError as exc:
            raise ImportError(
                "resvg-py is required for SVG support. "
                "Install with: pip install resvg-py"
            ) from exc
        raw_bytes = resvg_py.svg_to_bytes(svg_string=raw_bytes.decode("utf-8", errors="replace"))

    # Register pillow-heif opener lazily for HEIC/HEIF/AVIF (ISOBMFF containers)
    if len(raw_bytes) >= 12 and raw_bytes[4:8] == b"ftyp":
        try:
            import pillow_heif  # type: ignore[import-untyped]

            pillow_heif.register_heif_opener()
        except ImportError as exc:
            raise ImportError(
                "pillow-heif is required for HEIC/HEIF/AVIF support. "
                "Install with: pip install pillow-heif"
            ) from exc

    img: Image.Image = Image.open(io.BytesIO(raw_bytes))
    original_format = img.format or "PNG"
    original_dims = (img.width, img.height)

    long_edge = max(img.width, img.height)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        model_dims: tuple[int, int] = (new_w, new_h)
        resized = True
    else:
        model_dims = original_dims
        resized = False

    # Normalise mode for clean PNG encoding
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    return PreparedImage(
        model_bytes=buf.getvalue(),
        original_dims=original_dims,
        model_dims=model_dims,
        resized=resized,
        original_format=original_format,
    )
