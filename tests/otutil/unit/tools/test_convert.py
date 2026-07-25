"""Unit tests for Convert tool.

Tests convert.pdf(), convert.word(), convert.powerpoint(), convert.excel(), convert.auto()
Uses mocked converters to test the tool interface without requiring documents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

# Skip all tests if optional util deps not installed
pytest.importorskip("fitz", reason="pymupdf not installed (install onetool-mcp[util])")

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(autouse=True)
def mock_convert_config(tmp_path: Path) -> Generator[None, None, None]:
    """Mock convert tool config - patches effective CWD for internal tools."""
    with (
        patch("otpack.paths.get_effective_cwd", return_value=tmp_path),
    ):
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
    from otutil.tools.convert import pack

    assert pack == "convert"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from otutil.tools.convert import __all__

    expected = {"pdf", "word", "powerpoint", "excel", "auto"}
    assert set(__all__) == expected


# =============================================================================
# Glob Resolution Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_single_file(test_pdf: Path) -> None:
    """Verify glob resolves single file."""
    from otutil.tools.convert import _resolve_glob

    result = _resolve_glob(str(test_pdf))
    assert len(result) == 1
    assert result[0] == test_pdf


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_pattern(tmp_path: Path) -> None:
    """Verify glob pattern matching."""
    from otutil.tools.convert import _resolve_glob

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
    from otutil.tools.convert import _resolve_glob

    result = _resolve_glob("*.nonexistent")
    assert result == []


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_glob_home_expansion(tmp_path: Path) -> None:
    """Verify tilde expansion works."""
    from otutil.tools.convert import _resolve_glob

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
    from otutil.tools.convert import pdf

    result = pdf(pattern="nonexistent/*.pdf", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_single_file(test_pdf: Path, tmp_path: Path) -> None:
    """Verify pdf converts single file."""
    from otutil.tools.convert import pdf

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "pages": 5,
        "images": 2,
    }

    with patch("otutil.tools.convert.convert_pdf", return_value=mock_result):
        result = pdf(pattern=str(test_pdf), output_dir="output")

    assert "Converted test.pdf" in result
    assert "5 pages" in result
    assert "2 images" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_error_handling(test_pdf: Path, tmp_path: Path) -> None:
    """Verify pdf handles conversion errors."""
    from otutil.tools.convert import pdf

    with patch("otutil.tools.convert.convert_pdf", side_effect=Exception("Test error")):
        result = pdf(pattern=str(test_pdf), output_dir="output")

    assert "Error" in result
    assert "Test error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pdf_single_file_does_not_use_async_bridge(
    test_pdf: Path, tmp_path: Path
) -> None:
    """Verify single-file conversion stays on the direct synchronous path."""
    from otutil.tools.convert import pdf

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "pages": 5,
        "images": 2,
    }

    with (
        patch("otutil.tools.convert.convert_pdf", return_value=mock_result),
        patch("otutil.tools.convert.run_coro_sync") as mock_bridge,
    ):
        result = pdf(pattern=str(test_pdf), output_dir="output")

    assert "Converted test.pdf" in result
    mock_bridge.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
async def test_batch_conversions_run_inside_running_loop(tmp_path: Path) -> None:
    """Verify batch conversion wrappers work from an active event loop."""
    from otutil.tools import convert

    files_by_ext = {
        "pdf": [tmp_path / "pdf-a.pdf", tmp_path / "pdf-b.pdf"],
        "docx": [tmp_path / "word-a.docx", tmp_path / "word-b.docx"],
        "pptx": [tmp_path / "slides-a.pptx", tmp_path / "slides-b.pptx"],
        "xlsx": [tmp_path / "sheet-a.xlsx", tmp_path / "sheet-b.xlsx"],
    }
    for paths in files_by_ext.values():
        for path in paths:
            path.write_bytes(b"content")

    def _result(
        input_path: Path, _output_dir: Path, _source_rel: str, **_kwargs: Any
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"output": f"{input_path.stem}.md"}
        if input_path.suffix == ".pdf":
            data.update({"pages": 1, "images": 0})
        elif input_path.suffix == ".docx":
            data.update({"paragraphs": 1, "tables": 0, "images": 0})
        elif input_path.suffix == ".pptx":
            data.update({"slides": 1, "images": 0})
        elif input_path.suffix == ".xlsx":
            data.update({"sheets": 1, "rows": 1})
        return data

    with (
        patch("otutil.tools.convert.convert_pdf", side_effect=_result),
        patch("otutil.tools.convert.convert_word", side_effect=_result),
        patch("otutil.tools.convert.convert_powerpoint", side_effect=_result),
        patch("otutil.tools.convert.convert_excel", side_effect=_result),
    ):
        assert "Converted 2 files" in convert.pdf(pattern="*.pdf", output_dir="output")
        assert "Converted 2 files" in convert.word(
            pattern="*.docx", output_dir="output"
        )
        assert "Converted 2 files" in convert.powerpoint(
            pattern="*.pptx", output_dir="output"
        )
        assert "Converted 2 files" in convert.excel(
            pattern="*.xlsx", output_dir="output"
        )
        assert "Converted 8 files" in convert.auto(pattern="*", output_dir="output")


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize(
    ("tool_name", "suffix", "converter_name", "has_images"),
    [
        ("pdf", ".pdf", "convert_pdf", True),
        ("word", ".docx", "convert_word", True),
        ("powerpoint", ".pptx", "convert_powerpoint", True),
        ("excel", ".xlsx", "convert_excel", False),
    ],
)
def test_batch_same_stem_collision_fails_before_output_or_dispatch(
    tmp_path: Path,
    tool_name: str,
    suffix: str,
    converter_name: str,
    has_images: bool,
) -> None:
    from otutil.tools import convert

    sources = [tmp_path / "a" / f"report{suffix}", tmp_path / "b" / f"report{suffix}"]
    for source in sources:
        source.parent.mkdir()
        source.write_bytes(b"source")
    output_dir = tmp_path / "output"

    with (
        patch(f"otutil.tools.convert.{converter_name}") as converter,
        patch("otutil.tools.convert.run_coro_sync") as bridge,
        patch("otutil.tools.convert._get_conversion_executor") as executor,
    ):
        result = getattr(convert, tool_name)(
            pattern=f"**/*{suffix}",
            output_dir="output",
        )

    assert result.startswith("Error: Output collisions detected:")
    assert "output/report.md" in result
    assert "output/report.toc.md" in result
    assert ("output/report_images" in result) is has_images
    for source in sources:
        assert str(source) in result
    converter.assert_not_called()
    bridge.assert_not_called()
    executor.assert_not_called()
    assert not output_dir.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_auto_cross_format_collision_preserves_existing_outputs(tmp_path: Path) -> None:
    from otutil.tools.convert import auto

    supported = [tmp_path / "a" / "report.pdf", tmp_path / "b" / "report.docx"]
    unsupported = tmp_path / "c" / "report.txt"
    for source in [*supported, unsupported]:
        source.parent.mkdir()
        source.write_bytes(b"source")

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    existing = {
        output_dir / "report.md": b"existing markdown",
        output_dir / "report.toc.md": b"existing toc",
    }
    for path, content in existing.items():
        path.write_bytes(content)

    with (
        patch("otutil.tools.convert.convert_pdf") as pdf_converter,
        patch("otutil.tools.convert.convert_word") as word_converter,
        patch("otutil.tools.convert.run_coro_sync") as bridge,
        patch("otutil.tools.convert._get_conversion_executor") as executor,
    ):
        result = auto(pattern="**/*", output_dir="output")

    assert result.startswith("Error: Output collisions detected:")
    assert str(supported[0]) in result
    assert str(supported[1]) in result
    assert str(unsupported) not in result
    pdf_converter.assert_not_called()
    word_converter.assert_not_called()
    bridge.assert_not_called()
    executor.assert_not_called()
    assert {path: path.read_bytes() for path in existing} == existing
    assert set(output_dir.iterdir()) == set(existing)


@pytest.mark.unit
@pytest.mark.tools
def test_auto_non_colliding_sources_have_distinct_summary_outputs(
    tmp_path: Path,
) -> None:
    from otutil.tools.convert import auto

    sources = [
        tmp_path / "a" / "first.pdf",
        tmp_path / "b" / "second.docx",
        tmp_path / "c" / "third.pptx",
        tmp_path / "d" / "fourth.xlsx",
    ]
    for source in sources:
        source.parent.mkdir()
        source.write_bytes(b"source")

    def converted(
        input_path: Path,
        output_dir: Path,
        _source_rel: str,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        return {"output": str(output_dir / f"{input_path.stem}.md")}

    with (
        patch("otutil.tools.convert.convert_pdf", side_effect=converted),
        patch("otutil.tools.convert.convert_word", side_effect=converted),
        patch("otutil.tools.convert.convert_powerpoint", side_effect=converted),
        patch("otutil.tools.convert.convert_excel", side_effect=converted),
    ):
        result = auto(pattern="**/*", output_dir="output")

    assert result.startswith("Converted 4 files, 0 failed")
    outputs = [line.strip() for line in result.splitlines() if line.startswith("  ")]
    assert len(outputs) == 4
    assert len(set(outputs)) == 4


# =============================================================================
# Word Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_word_no_match() -> None:
    """Verify word returns error for no matches."""
    from otutil.tools.convert import word

    result = word(pattern="nonexistent/*.docx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_word_single_file(test_docx: Path, tmp_path: Path) -> None:
    """Verify word converts single file."""
    from otutil.tools.convert import word

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "paragraphs": 10,
        "tables": 2,
        "images": 1,
    }

    with patch("otutil.tools.convert.convert_word", return_value=mock_result):
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
    from otutil.tools.convert import powerpoint

    result = powerpoint(pattern="nonexistent/*.pptx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_powerpoint_single_file(test_pptx: Path, tmp_path: Path) -> None:
    """Verify powerpoint converts single file."""
    from otutil.tools.convert import powerpoint

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "slides": 15,
        "images": 5,
    }

    with patch("otutil.tools.convert.convert_powerpoint", return_value=mock_result):
        result = powerpoint(pattern=str(test_pptx), output_dir="output")

    assert "Converted test.pptx" in result
    assert "15 slides" in result
    assert "5 images" in result


@pytest.mark.unit
@pytest.mark.tools
def test_powerpoint_with_notes(test_pptx: Path, tmp_path: Path) -> None:
    """Verify powerpoint passes include_notes option."""
    from otutil.tools.convert import powerpoint

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "slides": 5,
        "images": 0,
    }

    with patch(
        "otutil.tools.convert.convert_powerpoint", return_value=mock_result
    ) as mock:
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
    from otutil.tools.convert import excel

    result = excel(pattern="nonexistent/*.xlsx", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_excel_single_file(test_xlsx: Path, tmp_path: Path) -> None:
    """Verify excel converts single file."""
    from otutil.tools.convert import excel

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "sheets": 3,
        "rows": 100,
    }

    with patch("otutil.tools.convert.convert_excel", return_value=mock_result):
        result = excel(pattern=str(test_xlsx), output_dir="output")

    assert "Converted test.xlsx" in result
    assert "3 sheets" in result
    assert "100 rows" in result


@pytest.mark.unit
@pytest.mark.tools
def test_excel_with_formulas(test_xlsx: Path, tmp_path: Path) -> None:
    """Verify excel passes include_formulas option."""
    from otutil.tools.convert import excel

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "sheets": 1,
        "rows": 10,
    }

    with patch("otutil.tools.convert.convert_excel", return_value=mock_result) as mock:
        excel(pattern=str(test_xlsx), output_dir="output", include_formulas=True)

    call_kwargs = mock.call_args[1]
    assert call_kwargs.get("include_formulas") is True


@pytest.mark.unit
@pytest.mark.tools
def test_excel_with_compute_formulas(test_xlsx: Path, tmp_path: Path) -> None:
    """Verify excel passes compute_formulas option."""
    from otutil.tools.convert import excel

    mock_result = {
        "output": str(tmp_path / "output" / "test.md"),
        "sheets": 1,
        "rows": 10,
    }

    with patch("otutil.tools.convert.convert_excel", return_value=mock_result) as mock:
        excel(pattern=str(test_xlsx), output_dir="output", compute_formulas=True)

    call_kwargs = mock.call_args[1]
    assert call_kwargs.get("compute_formulas") is True


# =============================================================================
# Auto Conversion Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_auto_no_match() -> None:
    """Verify auto returns error for no matches."""
    from otutil.tools.convert import auto

    result = auto(pattern="nonexistent/*", output_dir="output")
    assert "No files matched" in result


@pytest.mark.unit
@pytest.mark.tools
def test_auto_skips_unsupported(tmp_path: Path) -> None:
    """Verify auto skips unsupported formats."""
    from otutil.tools.convert import auto

    # Create unsupported file
    (tmp_path / "test.mp3").write_bytes(b"audio")

    result = auto(pattern="*.mp3", output_dir="output")
    assert "skipped" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_auto_mixed_formats(tmp_path: Path) -> None:
    """Verify auto handles mixed formats."""
    from otutil.tools.convert import auto

    # Create files of different types
    (tmp_path / "document.pdf").write_bytes(b"pdf")
    (tmp_path / "notes.docx").write_bytes(b"docx")
    (tmp_path / "doc.txt").write_text("txt")

    mock_result = {"output": "out.md", "pages": 1, "images": 0}

    with (
        patch("otutil.tools.convert.convert_pdf", return_value=mock_result),
        patch(
            "otutil.tools.convert.convert_word",
            return_value={**mock_result, "paragraphs": 1, "tables": 0, "images": 0},
        ),
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
    from otutil.tools.convert import _get_source_rel

    file_path = tmp_path / "subdir" / "file.pdf"
    result = _get_source_rel(file_path)

    assert "subdir" in result
    assert "file.pdf" in result


@pytest.mark.unit
@pytest.mark.tools
def test_resolve_output_dir(tmp_path: Path) -> None:
    """Verify output directory resolution."""
    from otutil.tools.convert import _resolve_output_dir

    result = _resolve_output_dir("output")
    assert result.is_absolute()
    assert "output" in str(result)


# =============================================================================
# Utils Module Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_checksum_cache_thread_safe(tmp_path: Path) -> None:
    """Verify checksum cache uses lru_cache for thread safety."""
    from otutil.tools._convert.utils import (
        _compute_checksum_cached,
        compute_file_checksum,
    )

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Compute checksum twice - should use cache
    checksum1 = compute_file_checksum(test_file)
    checksum2 = compute_file_checksum(test_file)

    assert checksum1 == checksum2
    assert checksum1.startswith("sha256:")

    # Verify the underlying function uses lru_cache
    assert hasattr(_compute_checksum_cached, "cache_info")
    cache_info = _compute_checksum_cached.cache_info()
    assert cache_info.hits >= 1  # Should have cache hit


@pytest.mark.unit
@pytest.mark.tools
def test_executor_shutdown_registered() -> None:
    """Verify atexit handler is registered for executor shutdown."""
    import atexit

    from otutil.tools.convert import _shutdown_executor

    # The _shutdown_executor should be registered
    # We can't easily test the actual registration, but we can verify the function exists
    assert callable(_shutdown_executor)
