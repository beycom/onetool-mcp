"""Integration tests for Convert tool.

Tests actual document conversion using sample files.
Requires PyMuPDF, python-docx, python-pptx, and openpyxl.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# Sample files directory
SAMPLE_DIR = Path(__file__).parent.parent.parent.parent / "scratch" / "tools" / "convert" / "input"


@pytest.fixture(autouse=True)
def mock_convert_config(tmp_path: Path) -> Generator[None, None, None]:
    """Mock convert tool config - patches effective cwd."""
    with patch("ot_tools.convert.get_effective_cwd", return_value=SAMPLE_DIR):
        yield


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create output directory."""
    out = tmp_path / "converted"
    out.mkdir()
    return out


def _has_sample(name: str) -> bool:
    """Check if sample file exists."""
    return (SAMPLE_DIR / name).exists()


# =============================================================================
# PDF Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.skipif(
    not _has_sample("file_example_PDF_1MB.pdf"),
    reason="Sample PDF not available"
)
def test_pdf_real_conversion(output_dir: Path) -> None:
    """Test actual PDF conversion."""
    from ot_tools._convert.pdf import convert_pdf

    pdf_path = SAMPLE_DIR / "file_example_PDF_1MB.pdf"
    result = convert_pdf(pdf_path, output_dir, "file_example_PDF_1MB.pdf")

    # Verify output
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()

    # Verify content structure
    content = output_path.read_text()
    assert "---" in content  # Frontmatter
    assert "source:" in content
    assert "checksum:" in content
    assert "pages" in result
    assert result["pages"] > 0


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.skipif(
    not _has_sample("file_example_PDF_1MB.pdf"),
    reason="Sample PDF not available"
)
def test_pdf_frontmatter(output_dir: Path) -> None:
    """Test PDF frontmatter generation."""
    from ot_tools._convert.pdf import convert_pdf

    pdf_path = SAMPLE_DIR / "file_example_PDF_1MB.pdf"
    result = convert_pdf(pdf_path, output_dir, "test.pdf")

    output_path = Path(result["output"])
    content = output_path.read_text()

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
@pytest.mark.skipif(
    not _has_sample("file_example_1MB.docx"),
    reason="Sample DOCX not available"
)
def test_word_real_conversion(output_dir: Path) -> None:
    """Test actual Word document conversion."""
    from ot_tools._convert.word import convert_word

    docx_path = SAMPLE_DIR / "file_example_1MB.docx"
    result = convert_word(docx_path, output_dir, "file_example_1MB.docx")

    # Verify output
    assert "output" in result
    output_path = Path(result["output"])
    assert output_path.exists()

    # Verify content
    content = output_path.read_text()
    assert "---" in content  # Frontmatter
    assert "paragraphs" in result


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.skipif(
    not _has_sample("file_example_1MB.docx"),
    reason="Sample DOCX not available"
)
def test_word_heading_detection(output_dir: Path) -> None:
    """Test Word heading style detection."""
    from ot_tools._convert.word import convert_word

    docx_path = SAMPLE_DIR / "file_example_1MB.docx"
    result = convert_word(docx_path, output_dir, "test.docx")

    output_path = Path(result["output"])
    content = output_path.read_text()

    # Should have markdown headings
    assert "#" in content


# =============================================================================
# PowerPoint Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.skipif(
    not _has_sample("file_example_PPT_1MB.pptx"),
    reason="Sample PPTX not available"
)
def test_powerpoint_real_conversion(output_dir: Path) -> None:
    """Test actual PowerPoint conversion."""
    from ot_tools._convert.powerpoint import convert_powerpoint

    pptx_path = SAMPLE_DIR / "file_example_PPT_1MB.pptx"
    result = convert_powerpoint(pptx_path, output_dir, "file_example_PPT_1MB.pptx")

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
@pytest.mark.skipif(
    not _has_sample("file_example_PPT_1MB.pptx"),
    reason="Sample PPTX not available"
)
def test_powerpoint_slide_structure(output_dir: Path) -> None:
    """Test PowerPoint slide structure."""
    from ot_tools._convert.powerpoint import convert_powerpoint

    pptx_path = SAMPLE_DIR / "file_example_PPT_1MB.pptx"
    result = convert_powerpoint(pptx_path, output_dir, "test.pptx")

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
@pytest.mark.skipif(
    not _has_sample("file_example_XLS_1000.xlsx"),
    reason="Sample XLSX not available"
)
def test_excel_real_conversion(output_dir: Path) -> None:
    """Test actual Excel conversion."""
    from ot_tools._convert.excel import convert_excel

    xlsx_path = SAMPLE_DIR / "file_example_XLS_1000.xlsx"
    result = convert_excel(xlsx_path, output_dir, "file_example_XLS_1000.xlsx")

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
@pytest.mark.skipif(
    not _has_sample("file_example_XLS_1000.xlsx"),
    reason="Sample XLSX not available"
)
def test_excel_table_format(output_dir: Path) -> None:
    """Test Excel table markdown format."""
    from ot_tools._convert.excel import convert_excel

    xlsx_path = SAMPLE_DIR / "file_example_XLS_1000.xlsx"
    result = convert_excel(xlsx_path, output_dir, "test.xlsx")

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
    """Test TOC generation."""
    from ot_tools._convert.utils import generate_toc

    headings = [
        (1, "Introduction", 10, 50),
        (2, "Background", 15, 30),
        (2, "Methods", 31, 50),
        (1, "Results", 51, 100),
    ]

    toc = generate_toc(headings)

    assert "## Table of Contents" in toc
    assert "[Introduction]" in toc
    assert "L10-L50" in toc
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
