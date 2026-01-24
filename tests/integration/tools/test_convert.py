"""Integration tests for Convert tool.

Tests actual document conversion using programmatically generated sample files.
Requires PyMuPDF, python-docx, python-pptx, and openpyxl.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create output directory."""
    out = tmp_path / "converted"
    out.mkdir()
    return out


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a minimal PDF file for testing."""
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()

    # Create 3 pages with content
    for i in range(3):
        page = doc.new_page()
        text = f"Page {i + 1}\n\nThis is test content for page {i + 1}.\n\nHeading {i + 1}"
        page.insert_text((72, 72), text, fontsize=12)

    doc.save(pdf_path)
    doc.close()
    yield pdf_path


@pytest.fixture
def sample_docx(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a minimal Word document for testing."""
    Document = pytest.importorskip("docx").Document

    docx_path = tmp_path / "test.docx"
    doc = Document()

    doc.add_heading("Test Document", 0)
    doc.add_heading("Introduction", level=1)
    doc.add_paragraph("This is a test paragraph with some content.")
    doc.add_heading("Details", level=2)
    doc.add_paragraph("More detailed content here.")

    doc.save(docx_path)
    yield docx_path


@pytest.fixture
def sample_pptx(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a minimal PowerPoint presentation for testing."""
    pptx = pytest.importorskip("pptx")
    Presentation = pptx.Presentation

    pptx_path = tmp_path / "test.pptx"
    prs = Presentation()

    # Add title slide
    title_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_layout)
    slide.shapes.title.text = "Test Presentation"
    slide.placeholders[1].text = "Subtitle text"

    # Add content slide
    content_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(content_layout)
    slide.shapes.title.text = "Slide 2"
    slide.placeholders[1].text = "Content for slide 2"

    prs.save(pptx_path)
    yield pptx_path


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a minimal Excel workbook for testing."""
    Workbook = pytest.importorskip("openpyxl").Workbook

    xlsx_path = tmp_path / "test.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"

    # Add header row
    ws.append(["Name", "Value", "Category"])
    # Add data rows
    ws.append(["Item A", 100, "Type 1"])
    ws.append(["Item B", 200, "Type 2"])
    ws.append(["Item C", 150, "Type 1"])

    wb.save(xlsx_path)
    yield xlsx_path


# =============================================================================
# PDF Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
def test_pdf_real_conversion(sample_pdf: Path, output_dir: Path) -> None:
    """Test actual PDF conversion."""
    from ot_tools._convert.pdf import convert_pdf

    result = convert_pdf(sample_pdf, output_dir, "test.pdf")

    # Verify main output (pure content, no frontmatter)
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()
    content = output_path.read_text()
    assert len(content) > 0  # Has content

    # Verify TOC file has frontmatter
    assert "toc" in result
    toc_path = Path(result["toc"])
    assert toc_path.exists()
    toc_content = toc_path.read_text()
    assert "---" in toc_content  # Frontmatter
    assert "source:" in toc_content
    assert "checksum:" in toc_content

    assert "pages" in result
    assert result["pages"] > 0


@pytest.mark.integration
@pytest.mark.tools
def test_pdf_frontmatter(sample_pdf: Path, output_dir: Path) -> None:
    """Test PDF frontmatter generation in TOC file."""
    from ot_tools._convert.pdf import convert_pdf

    result = convert_pdf(sample_pdf, output_dir, "test.pdf")

    # Frontmatter is now in the separate TOC file
    toc_path = Path(result["toc"])
    content = toc_path.read_text()

    # Check frontmatter
    assert content.startswith("---\n")
    assert "source: test.pdf" in content
    assert "converted:" in content
    assert "checksum: sha256:" in content


# =============================================================================
# Word Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
def test_word_real_conversion(sample_docx: Path, output_dir: Path) -> None:
    """Test actual Word document conversion."""
    from ot_tools._convert.word import convert_word

    result = convert_word(sample_docx, output_dir, "test.docx")

    # Verify main output (pure content, no frontmatter)
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()
    content = output_path.read_text()
    assert len(content) > 0  # Has content

    # Verify TOC file has frontmatter
    assert "toc" in result
    toc_path = Path(result["toc"])
    assert toc_path.exists()
    toc_content = toc_path.read_text()
    assert "---" in toc_content  # Frontmatter

    assert "paragraphs" in result


@pytest.mark.integration
@pytest.mark.tools
def test_word_heading_detection(sample_docx: Path, output_dir: Path) -> None:
    """Test Word heading style detection."""
    from ot_tools._convert.word import convert_word

    result = convert_word(sample_docx, output_dir, "test.docx")

    output_path = Path(result["output"])
    content = output_path.read_text()

    # Should have markdown headings
    assert "#" in content


# =============================================================================
# PowerPoint Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
def test_powerpoint_real_conversion(sample_pptx: Path, output_dir: Path) -> None:
    """Test actual PowerPoint conversion."""
    from ot_tools._convert.powerpoint import convert_powerpoint

    result = convert_powerpoint(sample_pptx, output_dir, "test.pptx")

    # Verify output
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()

    # Verify content
    content = output_path.read_text()
    assert "---" in content  # Frontmatter
    assert "slides" in result
    assert result["slides"] > 0


@pytest.mark.integration
@pytest.mark.tools
def test_powerpoint_slide_structure(sample_pptx: Path, output_dir: Path) -> None:
    """Test PowerPoint slide structure."""
    from ot_tools._convert.powerpoint import convert_powerpoint

    result = convert_powerpoint(sample_pptx, output_dir, "test.pptx")

    output_path = Path(result["output"])
    content = output_path.read_text()

    # Should have slide headers
    assert "##" in content  # Slide headers are H2
    assert "---" in content  # Slide separators


# =============================================================================
# Excel Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
def test_excel_real_conversion(sample_xlsx: Path, output_dir: Path) -> None:
    """Test actual Excel conversion."""
    from ot_tools._convert.excel import convert_excel

    result = convert_excel(sample_xlsx, output_dir, "test.xlsx")

    # Verify output
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()

    # Verify content
    content = output_path.read_text()
    assert "---" in content  # Frontmatter
    assert "sheets" in result
    assert "rows" in result


@pytest.mark.integration
@pytest.mark.tools
def test_excel_table_format(sample_xlsx: Path, output_dir: Path) -> None:
    """Test Excel table markdown format."""
    from ot_tools._convert.excel import convert_excel

    result = convert_excel(sample_xlsx, output_dir, "test.xlsx")

    output_path = Path(result["output"])
    content = output_path.read_text()

    # Should have markdown table format
    assert "|" in content
    assert "---" in content


# =============================================================================
# Utility Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
def test_compute_file_checksum(tmp_path: Path) -> None:
    """Test file checksum computation."""
    from ot_tools._convert.utils import compute_file_checksum

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    checksum = compute_file_checksum(test_file)

    assert checksum.startswith("sha256:")
    assert len(checksum) > 10


@pytest.mark.integration
@pytest.mark.tools
def test_compute_image_hash() -> None:
    """Test image hash computation."""
    from ot_tools._convert.utils import compute_image_hash

    data = b"test image data"
    hash1 = compute_image_hash(data)
    hash2 = compute_image_hash(data)

    # Same data should give same hash
    assert hash1 == hash2
    assert len(hash1) == 8


@pytest.mark.integration
@pytest.mark.tools
def test_normalise_whitespace() -> None:
    """Test whitespace normalisation."""
    from ot_tools._convert.utils import normalise_whitespace

    # Test CRLF conversion
    input_text = "line1\r\nline2\rline3"
    result = normalise_whitespace(input_text)
    assert "\r" not in result
    assert result.endswith("\n")

    # Test trailing whitespace removal
    input_text = "line1   \nline2  "
    result = normalise_whitespace(input_text)
    assert "   \n" not in result

    # Test blank line collapsing
    input_text = "line1\n\n\n\n\nline2"
    result = normalise_whitespace(input_text)
    assert "\n\n\n\n" not in result


@pytest.mark.integration
@pytest.mark.tools
def test_generate_frontmatter() -> None:
    """Test frontmatter generation."""
    from ot_tools._convert.utils import generate_frontmatter

    fm = generate_frontmatter(
        source="test.pdf",
        converted="2026-01-20T10:00:00Z",
        pages=5,
        checksum="sha256:abc123",
    )

    assert fm.startswith("---\n")
    assert fm.endswith("---\n")
    assert "source: test.pdf" in fm
    assert "pages: 5" in fm


@pytest.mark.integration
@pytest.mark.tools
def test_generate_toc() -> None:
    """Test TOC generation with frontmatter."""
    from ot_tools._convert.utils import generate_toc

    headings = [
        (1, "Introduction", 10, 50),
        (2, "Background", 15, 30),
        (2, "Methods", 31, 50),
        (1, "Results", 51, 100),
    ]

    toc = generate_toc(
        headings=headings,
        main_file="test.md",
        source="test.pdf",
        converted="2026-01-20T10:00:00Z",
        pages=5,
        checksum="sha256:abc123",
    )

    # TOC now includes frontmatter
    assert toc.startswith("---\n")
    assert "source: test.pdf" in toc
    assert "# Table of Contents" in toc
    assert "[Introduction]" in toc
    assert "(lines 10-50)" in toc
    assert "  -" in toc  # Nested items should be indented


@pytest.mark.integration
@pytest.mark.tools
def test_incremental_writer() -> None:
    """Test incremental writer with headings."""
    from ot_tools._convert.utils import IncrementalWriter

    writer = IncrementalWriter()
    writer.write("Some preamble\n\n")
    writer.write_heading(1, "First Section")
    writer.write("Content of first section\n")
    writer.write_heading(2, "Subsection")
    writer.write("More content\n")

    content = writer.get_content()
    headings = writer.get_headings()

    assert "# First Section" in content
    assert "## Subsection" in content
    assert len(headings) == 2
    assert headings[0][1] == "First Section"
    assert headings[1][1] == "Subsection"
