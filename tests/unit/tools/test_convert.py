"""Unit tests for Convert tool.

Tests convert.pdf(), convert.word(), convert.powerpoint(), convert.excel(), convert.auto()
Uses mocked converters to test the tool interface without requiring documents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(autouse=True)
def mock_convert_config(tmp_path: Path) -> Generator[None, None, None]:
    """Mock convert tool config - patches effective CWD for internal tools."""
    with patch("ot.paths.get_effective_cwd", return_value=tmp_path):
        yield


@pytest.fixture
def test_pdf(tmp_path: Path) -> Path:
    """Create a mock PDF file."""
    f = tmp_path / "test.pdf"
    f.write_bytes(b"%PDF-1.4 mock pdf content")
    return f


@pytest.fixture
def test_docx(tmp_path: Path) -> Path:
    """Create a mock DOCX file."""
    f = tmp_path / "test.docx"
    f.write_bytes(b"PK mock docx content")
    return f


@pytest.fixture
def test_pptx(tmp_path: Path) -> Path:
    """Create a mock PPTX file."""
    f = tmp_path / "test.pptx"
    f.write_bytes(b"PK mock pptx content")
    return f


@pytest.fixture
def test_xlsx(tmp_path: Path) -> Path:
    """Create a mock XLSX file."""
    f = tmp_path / "test.xlsx"
    f.write_bytes(b"PK mock xlsx content")
    return f


@pytest.mark.unit
@pytest.mark.tools
def test_pack_is_convert() -> None:
    """Verify pack is correctly set."""
    from ot_tools.convert import pack

    assert pack == "convert"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from ot_tools.convert import __all__

    expected = {"pdf", "word", "powerpoint", "excel", "auto"}
    assert set(__all__) == expected


# =============================================================================
# Glob Resolution Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_single_file(test_pdf: Path) -> None:
    """Verify glob resolves single file."""
    from ot_tools.convert import _resolve_glob

    result = _resolve_glob(str(test_pdf))
    assert len(result) == 1
    assert result[0] == test_pdf


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_pattern(tmp_path: Path) -> None:
    """Verify glob pattern matching."""
    from ot_tools.convert import _resolve_glob

    # Create multiple PDFs
    (tmp_path / "a.pdf").write_bytes(b"pdf")
    (tmp_path / "b.pdf").write_bytes(b"pdf")
    (tmp_path / "c.txt").write_text("txt")

    result = _resolve_glob("*.pdf")
    assert len(result) == 2
    names = {p.name for p in result}
    assert names == {"a.pdf", "b.pdf"}


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_no_match(tmp_path: Path) -> None:
    """Verify glob returns empty for no matches."""
    from ot_tools.convert import _resolve_glob

    result = _resolve_glob("*.nonexistent")
    assert result == []


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_home_expansion(tmp_path: Path) -> None:
    """Verify tilde expansion works."""
    from ot_tools.convert import _resolve_glob

    # This tests the path expansion, not actual home directory access
    result = _resolve_glob(str(tmp_path / "test.pdf"))
    # Should return empty since file doesn't exist
    assert result == []


# =============================================================================
# PDF Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_no_match() -> None:
    """Verify pdf returns error for no matches."""
    from ot_tools.convert import pdf

    result = pdf(pattern="nonexistent/*.pdf", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_single_file(test_pdf: Path, tmp_path: Path) -> None:
    """Verify pdf converts single file."""
    from ot_tools.convert import pdf

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "pages": 5,
        "images": 2,
    }

    with patch("ot_tools.convert.convert_pdf", return_value=mock_result):
        result = pdf(pattern=str(test_pdf), output_dir="output")

    assert "Converted test.pdf" in result
    assert "5 pages" in result
    assert "2 images" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_error_handling(test_pdf: Path, tmp_path: Path) -> None:
    """Verify pdf handles conversion errors."""
    from ot_tools.convert import pdf

    with patch("ot_tools.convert.convert_pdf", side_effect=Exception("Test error")):
        result = pdf(pattern=str(test_pdf), output_dir="output")

    assert "Error" in result
    assert "Test error" in result


# =============================================================================
# Word Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_word_no_match() -> None:
    """Verify word returns error for no matches."""
    from ot_tools.convert import word

    result = word(pattern="nonexistent/*.docx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_word_single_file(test_docx: Path, tmp_path: Path) -> None:
    """Verify word converts single file."""
    from ot_tools.convert import word

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "paragraphs": 10,
        "tables": 2,
        "images": 1,
    }

    with patch("ot_tools.convert.convert_word", return_value=mock_result):
        result = word(pattern=str(test_docx), output_dir="output")

    assert "Converted test.docx" in result
    assert "10 paragraphs" in result
    assert "2 tables" in result


# =============================================================================
# PowerPoint Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_powerpoint_no_match() -> None:
    """Verify powerpoint returns error for no matches."""
    from ot_tools.convert import powerpoint

    result = powerpoint(pattern="nonexistent/*.pptx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_powerpoint_single_file(test_pptx: Path, tmp_path: Path) -> None:
    """Verify powerpoint converts single file."""
    from ot_tools.convert import powerpoint

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "slides": 15,
        "images": 5,
    }

    with patch("ot_tools.convert.convert_powerpoint", return_value=mock_result):
        result = powerpoint(pattern=str(test_pptx), output_dir="output")

    assert "Converted test.pptx" in result
    assert "15 slides" in result
    assert "5 images" in result


@pytest.mark.unit
@pytest.mark.tools
def test_powerpoint_with_notes(test_pptx: Path, tmp_path: Path) -> None:
    """Verify powerpoint passes include_notes option."""
    from ot_tools.convert import powerpoint

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "slides": 5,
        "images": 0,
    }

    with patch("ot_tools.convert.convert_powerpoint", return_value=mock_result) as mock:
        powerpoint(pattern=str(test_pptx), output_dir="output", include_notes=True)

    # Verify include_notes was passed
    call_kwargs = mock.call_args[1]
    assert call_kwargs.get("include_notes") is True


# =============================================================================
# Excel Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_excel_no_match() -> None:
    """Verify excel returns error for no matches."""
    from ot_tools.convert import excel

    result = excel(pattern="nonexistent/*.xlsx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_excel_single_file(test_xlsx: Path, tmp_path: Path) -> None:
    """Verify excel converts single file."""
    from ot_tools.convert import excel

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "sheets": 3,
        "rows": 100,
    }

    with patch("ot_tools.convert.convert_excel", return_value=mock_result):
        result = excel(pattern=str(test_xlsx), output_dir="output")

    assert "Converted test.xlsx" in result
    assert "3 sheets" in result
    assert "100 rows" in result


@pytest.mark.unit
@pytest.mark.tools
def test_excel_with_formulas(test_xlsx: Path, tmp_path: Path) -> None:
    """Verify excel passes include_formulas option."""
    from ot_tools.convert import excel

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "sheets": 1,
        "rows": 10,
    }

    with patch("ot_tools.convert.convert_excel", return_value=mock_result) as mock:
        excel(pattern=str(test_xlsx), output_dir="output", include_formulas=True)

    call_kwargs = mock.call_args[1]
    assert call_kwargs.get("include_formulas") is True


# =============================================================================
# Auto Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_auto_no_match() -> None:
    """Verify auto returns error for no matches."""
    from ot_tools.convert import auto

    result = auto(pattern="nonexistent/*", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_auto_skips_unsupported(tmp_path: Path) -> None:
    """Verify auto skips unsupported formats."""
    from ot_tools.convert import auto

    # Create unsupported file
    (tmp_path / "test.mp3").write_bytes(b"audio")

    result = auto(pattern="*.mp3", output_dir="output")
    assert "skipped" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_auto_mixed_formats(tmp_path: Path) -> None:
    """Verify auto handles mixed formats."""
    from ot_tools.convert import auto

    # Create files of different types
    (tmp_path / "doc.pdf").write_bytes(b"pdf")
    (tmp_path / "doc.docx").write_bytes(b"docx")
    (tmp_path / "doc.txt").write_text("txt")

    mock_result = {"output": "out.md", "pages": 1, "images": 0}

    with (
        patch("ot_tools.convert.convert_pdf", return_value=mock_result),
        patch("ot_tools.convert.convert_word", return_value={**mock_result, "paragraphs": 1, "tables": 0, "images": 0}),
    ):
        result = auto(pattern="*", output_dir="output")

    assert "Converted 2 files" in result
    assert "1 skipped" in result


# =============================================================================
# Utility Function Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_get_source_rel(tmp_path: Path) -> None:
    """Verify source path is made relative."""
    from ot_tools.convert import _get_source_rel

    file_path = tmp_path / "subdir" / "file.pdf"
    result = _get_source_rel(file_path)

    assert "subdir" in result
    assert "file.pdf" in result


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_output_dir(tmp_path: Path) -> None:
    """Verify output directory resolution."""
    from ot_tools.convert import _resolve_output_dir

    result = _resolve_output_dir("output")
    assert result.is_absolute()
    assert "output" in str(result)
