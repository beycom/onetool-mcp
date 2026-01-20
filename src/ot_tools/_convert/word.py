"""Word document to Markdown converter.

Converts DOCX documents to Markdown with:
- Heading style detection (Heading 1-6)
- Table conversion
- Hash-based image naming for diff stability
- YAML frontmatter and TOC generation
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 (used at runtime)
from typing import TYPE_CHECKING, Any

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from ot_tools._convert.utils import (
    IncrementalWriter,
    compute_file_checksum,
    get_mtime_iso,
    normalise_whitespace,
    save_image,
    write_toc_file,
)

if TYPE_CHECKING:
    from docx.document import Document as DocumentType


def convert_word(
    input_path: Path,
    output_dir: Path,
    source_rel: str,
) -> dict[str, Any]:
    """Convert Word document to Markdown.

    Args:
        input_path: Path to DOCX file
        output_dir: Directory for output files
        source_rel: Relative path to source for frontmatter

    Returns:
        Dict with 'output', 'paragraphs', 'tables', 'images' keys
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    doc: DocumentType = Document(str(input_path))
    try:
        # Get metadata for frontmatter
        checksum = compute_file_checksum(input_path)
        mtime = get_mtime_iso(input_path)

        # Count pages (approximate - Word doesn't store exact page count)
        # Use paragraph count / 40 as rough estimate
        page_count = max(1, len(doc.paragraphs) // 40)

        # Set up images directory
        images_dir = output_dir / f"{input_path.stem}_images"
        writer = IncrementalWriter()
        images_extracted = 0
        paragraphs_processed = 0
        tables_processed = 0
        processed_image_rels: set[str] = set()

        # Process document elements in order
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)
                _process_paragraph(
                    paragraph, writer, doc, images_dir, processed_image_rels
                )
                if paragraph.text.strip():
                    paragraphs_processed += 1
                    # Count images extracted during paragraph processing
                    images_extracted = len(processed_image_rels)

            elif isinstance(element, CT_Tbl):
                table = Table(element, doc)
                _process_table(table, writer)
                tables_processed += 1

        # Extract remaining images not caught inline
        for rel_id, rel in doc.part.rels.items():
            if "image" in rel.target_ref and rel_id not in processed_image_rels:
                try:
                    image_data = rel.target_part.blob
                    save_image(image_data, images_dir, rel.target_part.content_type)
                    images_extracted += 1
                    processed_image_rels.add(rel_id)
                except Exception:
                    continue
    finally:
        # Ensure document resources are released
        # python-docx Document doesn't have explicit close, but we can
        # help garbage collection by clearing references
        del doc

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
        pages=page_count,
        checksum=checksum,
    )

    return {
        "output": str(output_path),
        "toc": str(toc_path),
        "paragraphs": paragraphs_processed,
        "tables": tables_processed,
        "images": images_extracted,
    }


def _process_paragraph(
    paragraph: Paragraph,
    writer: IncrementalWriter,
    doc: Any,
    images_dir: Path,
    processed_rels: set[str],
) -> None:
    """Process a paragraph, handling headings, text, and images."""
    text = paragraph.text.strip()
    if not text:
        return

    # Get style
    style_name = (
        paragraph.style.name.lower() if paragraph.style and paragraph.style.name else ""
    )

    # Handle headings via style
    if "heading" in style_name:
        try:
            level = int(style_name.split()[-1])
            level = min(level, 6)
            writer.write_heading(level, text)
            return
        except (ValueError, IndexError):
            pass

    # Handle special styles
    if "title" in style_name:
        writer.write_heading(1, text)
        return
    elif "subtitle" in style_name:
        writer.write_heading(2, text)
        return

    # Process formatted text
    formatted = _format_paragraph_runs(paragraph, doc, images_dir, processed_rels)

    # Handle quote/block styles
    if "quote" in style_name or "block" in style_name:
        lines = formatted.split("\n")
        formatted = "\n".join(f"> {line}" for line in lines)
        writer.write(formatted + "\n\n")
        return

    # Handle list styles
    if "list" in style_name:
        writer.write(f"- {formatted}\n")
        return

    # Regular paragraph
    writer.write(formatted + "\n\n")


def _format_paragraph_runs(
    paragraph: Paragraph,
    doc: Any,
    images_dir: Path,
    processed_rels: set[str],
) -> str:
    """Process runs within a paragraph for formatting and images."""
    parts: list[str] = []

    # Process inline images
    try:
        drawings = paragraph._element.xpath(".//w:drawing")
        for drawing in drawings:
            img_ref = _process_drawing(drawing, doc, images_dir, processed_rels)
            if img_ref:
                parts.append(img_ref)
    except Exception:
        pass

    # Process text runs
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue

        # Apply formatting
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"

        if run.underline:
            text = f"<u>{text}</u>"

        parts.append(text)

    return "".join(parts)


def _process_drawing(
    drawing_elem: Any,
    doc: Any,
    images_dir: Path,
    processed_rels: set[str],
) -> str:
    """Extract image from drawing element."""
    try:
        blips = drawing_elem.xpath(".//a:blip")
        for blip in blips:
            r_embed = blip.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )

            if r_embed and r_embed not in processed_rels:
                # Direct dictionary lookup instead of iteration - O(1) vs O(n)
                rel = doc.part.rels.get(r_embed)
                if rel is not None and "image" in rel.target_ref:
                    try:
                        image_data = rel.target_part.blob
                        processed_rels.add(r_embed)

                        img_path = save_image(
                            image_data, images_dir, rel.target_part.content_type
                        )
                        rel_path = f"{images_dir.name}/{img_path.name}"
                        return f"![{img_path.name}]({rel_path})"
                    except Exception:
                        return ""
    except Exception:
        pass
    return ""


def _process_table(table: Table, writer: IncrementalWriter) -> None:
    """Convert table to Markdown format."""
    if not table.rows:
        return

    # Process header row
    header_cells = [cell.text.strip() for cell in table.rows[0].cells]
    if not header_cells:
        return

    writer.write("| " + " | ".join(header_cells) + " |\n")
    writer.write("| " + " | ".join("---" for _ in header_cells) + " |\n")

    # Process data rows
    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        while len(cells) < len(header_cells):
            cells.append("")
        writer.write("| " + " | ".join(cells[: len(header_cells)]) + " |\n")

    writer.write("\n")
