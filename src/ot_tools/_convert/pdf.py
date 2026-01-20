"""PDF to Markdown converter.

Converts PDF documents to Markdown with:
- Lazy page loading via PyMuPDF
- Outline-based heading extraction
- Hash-based image naming for diff stability
- YAML frontmatter and TOC generation
"""

from __future__ import annotations

import io
from pathlib import Path  # noqa: TC003 (used at runtime)
from typing import TYPE_CHECKING, Any

import fitz  # type: ignore[import-untyped]  # PyMuPDF
from PIL import Image

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

from ot_tools._convert.utils import (
    IncrementalWriter,
    compute_file_checksum,
    compute_image_hash,
    get_mtime_iso,
    normalise_whitespace,
    write_toc_file,
)


def _merge_smask(image_bytes: bytes, sm_bytes: bytes) -> bytes:
    """Merge soft-mask into image for transparency.

    Args:
        image_bytes: Base image bytes
        sm_bytes: Soft-mask bytes

    Returns:
        PNG bytes with transparency
    """
    with (
        Image.open(io.BytesIO(image_bytes)) as im_file,
        Image.open(io.BytesIO(sm_bytes)) as mask_file,
    ):
        mask: PILImage = mask_file.convert("L")
        im: PILImage = im_file.convert("RGBA")
        if mask.size != im.size:
            mask = mask.resize(im.size)
        im.putalpha(mask)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()


def _detect_image_format(image_bytes: bytes) -> str:
    """Detect image format from bytes.

    Args:
        image_bytes: Image data

    Returns:
        File extension (e.g., 'png', 'jpg')
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            format_map = {
                "JPEG": "jpg",
                "PNG": "png",
                "GIF": "gif",
                "BMP": "bmp",
                "TIFF": "tiff",
                "WEBP": "webp",
            }
            return format_map.get(im.format or "", "png")
    except Exception:
        return "png"


def _get_outline_headings(doc: fitz.Document) -> list[tuple[int, str, int]]:
    """Extract outline/bookmarks from PDF.

    Args:
        doc: PyMuPDF document

    Returns:
        List of (level, title, page_number) tuples
    """
    try:
        toc = doc.get_toc()
        return [(level, title, page) for level, title, page in toc]
    except Exception:
        return []


def _extract_and_save_image(
    doc: fitz.Document,
    xref: int,
    images_dir: Path,
    writer: IncrementalWriter,
) -> bool:
    """Extract a single image and save to disk.

    This function encapsulates image processing so that memory (image_bytes)
    is freed when the function returns, preventing accumulation.

    Args:
        doc: PyMuPDF document
        xref: Image xref in the document
        images_dir: Directory for saving images
        writer: Incremental writer for markdown output

    Returns:
        True if image was successfully extracted, False otherwise
    """
    base_image = doc.extract_image(xref)
    image_bytes = base_image.get("image")
    smask = base_image.get("smask")

    if not image_bytes:
        return False

    # Handle soft-mask (transparency)
    if smask:
        try:
            sm_base = doc.extract_image(smask)
            sm_bytes = sm_base.get("image")
            if sm_bytes:
                image_bytes = _merge_smask(image_bytes, sm_bytes)
                extension = "png"
            else:
                extension = _detect_image_format(image_bytes)
        except Exception:
            extension = _detect_image_format(image_bytes)
    else:
        extension = _detect_image_format(image_bytes)

    # Hash-based naming for diff stability
    img_hash = compute_image_hash(image_bytes)
    img_name = f"img_{img_hash}.{extension}"
    img_path = images_dir / img_name

    # Only write if not already extracted (dedup by hash)
    if not img_path.exists():
        images_dir.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(image_bytes)

    rel_path = f"{images_dir.name}/{img_name}"
    writer.write(f"![{img_name}]({rel_path})\n\n")

    return True


def convert_pdf(
    input_path: Path,
    output_dir: Path,
    source_rel: str,
) -> dict[str, Any]:
    """Convert PDF to Markdown.

    Args:
        input_path: Path to PDF file
        output_dir: Directory for output files
        source_rel: Relative path to source for frontmatter

    Returns:
        Dict with 'output', 'pages', 'images' keys
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(input_path)
    try:
        total_pages = len(doc)

        # Get metadata for frontmatter
        checksum = compute_file_checksum(input_path)
        mtime = get_mtime_iso(input_path)

        # Get outline for heading insertion
        outline = _get_outline_headings(doc)
        outline_by_page: dict[int, list[tuple[int, str]]] = {}
        for level, title, page in outline:
            if page not in outline_by_page:
                outline_by_page[page] = []
            outline_by_page[page].append((level, title))

        # Set up images directory
        images_dir = output_dir / f"{input_path.stem}_images"
        writer = IncrementalWriter()
        images_extracted = 0

        # Process pages with lazy loading
        for pageno in range(total_pages):
            page = doc[pageno]
            page_num = pageno + 1

            # Insert outline headings for this page
            if page_num in outline_by_page:
                for level, title in outline_by_page[page_num]:
                    writer.write_heading(min(level, 6), title)
            elif not outline:
                # No outline - use page numbers as structure
                writer.write_heading(1, f"Page {page_num}")

            # Extract text
            text = page.get_text("text")
            if text.strip():
                writer.write(text.rstrip() + "\n\n")

            # Extract images - process one at a time to minimize memory
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]
                try:
                    result = _extract_and_save_image(
                        doc, xref, images_dir, writer
                    )
                    if result:
                        images_extracted += 1
                except Exception:
                    # Skip failed image extraction
                    continue
    finally:
        doc.close()

    # Write main output (pure content, no frontmatter - line numbers start at 1)
    content = normalise_whitespace(writer.get_content())
    output_path = output_dir / f"{input_path.stem}.md"
    output_path.write_text(content, encoding="utf-8")

    # Write separate TOC file (includes frontmatter)
    headings = writer.get_headings()
    toc_path = write_toc_file(
        headings=headings,
        output_dir=output_dir,
        stem=input_path.stem,
        source=source_rel,
        converted=mtime,
        pages=total_pages,
        checksum=checksum,
    )

    return {
        "output": str(output_path),
        "toc": str(toc_path),
        "pages": total_pages,
        "images": images_extracted,
    }
