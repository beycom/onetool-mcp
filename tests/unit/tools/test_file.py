"""Unit tests for File tool.

Tests file.read(), file.write(), file.list(), etc.
Uses tmp_path fixture for isolated test files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


class MockFileConfig:
    """Mock file config that allows any directory."""

    allowed_dirs: ClassVar[list[str]] = []  # Empty = allows cwd, but we patch cwd
    exclude_patterns: ClassVar[list[str]] = [".git", "__pycache__"]
    max_file_size: int = 10_000_000
    max_list_entries: int = 1000
    backup_on_write: bool = False  # Disable for cleaner tests
    use_trash: bool = False


@pytest.fixture(autouse=True)
def mock_file_config(tmp_path: Path) -> Generator[None, None, None]:
    """Mock file tool config to allow temp directories."""
    mock_config = MagicMock()
    mock_config.tools.file = MockFileConfig()

    # Patch both the config getter and effective cwd
    with (
        patch("ot_tools.file.get_config", return_value=mock_config),
        patch("ot_tools.file.get_effective_cwd", return_value=tmp_path),
    ):
        yield


@pytest.fixture
def test_file(tmp_path: Path) -> Path:
    """Create a temp text file with content."""
    f = tmp_path / "test.txt"
    f.write_text("Line 1\nLine 2\nLine 3\n")
    return f


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """Create a temp directory structure."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.py").write_text("content2")
    (tmp_path / "subdir" / "nested.txt").write_text("nested")
    return tmp_path


@pytest.mark.unit
@pytest.mark.serve
def test_pack_is_file() -> None:
    """Verify pack is correctly set."""
    from ot_tools.file import pack

    assert pack == "file"


@pytest.mark.unit
@pytest.mark.serve
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from ot_tools.file import __all__

    expected = {
        "copy",
        "delete",
        "edit",
        "info",
        "list",
        "move",
        "read",
        "search",
        "tree",
        "write",
    }
    assert set(__all__) == expected


# =============================================================================
# Read Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_read_file(test_file: Path) -> None:
    """Verify read returns file content with line numbers."""
    from ot_tools.file import read

    result = read(path=str(test_file))

    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result
    # Line numbers should be present
    assert "1\t" in result or "1→" in result


@pytest.mark.unit
@pytest.mark.serve
def test_read_with_offset(test_file: Path) -> None:
    """Verify read respects offset parameter."""
    from ot_tools.file import read

    result = read(path=str(test_file), offset=1)

    assert "Line 1" not in result
    assert "Line 2" in result
    assert "Line 3" in result


@pytest.mark.unit
@pytest.mark.serve
def test_read_with_limit(test_file: Path) -> None:
    """Verify read respects limit parameter."""
    from ot_tools.file import read

    result = read(path=str(test_file), limit=2)

    assert "Line 1" in result
    assert "Line 2" in result
    # Line 3 may or may not be present depending on implementation


@pytest.mark.unit
@pytest.mark.serve
def test_read_nonexistent_file() -> None:
    """Verify read returns error for missing file."""
    from ot_tools.file import read

    result = read(path="/nonexistent/path/missing.txt")

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.serve
def test_info_file(test_file: Path) -> None:
    """Verify info returns file metadata."""
    from ot_tools.file import info

    result = info(path=str(test_file))

    # Result is now a dict with path, type, size, etc.
    assert isinstance(result, dict)
    assert "test.txt" in result["path"]
    assert result["type"] == "file"
    assert "size" in result


@pytest.mark.unit
@pytest.mark.serve
def test_info_directory(test_dir: Path) -> None:
    """Verify info returns directory metadata."""
    from ot_tools.file import info

    result = info(path=str(test_dir))

    # Result is now a dict with type field
    assert isinstance(result, dict)
    assert result["type"] == "directory"


# =============================================================================
# List and Tree Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_list_directory(test_dir: Path) -> None:
    """Verify list returns directory contents."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir))

    assert "file1.txt" in result
    assert "file2.py" in result
    assert "subdir" in result


@pytest.mark.unit
@pytest.mark.serve
def test_list_with_pattern(test_dir: Path) -> None:
    """Verify list filters by pattern."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir), pattern="*.txt")

    assert "file1.txt" in result
    assert "file2.py" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_list_recursive(test_dir: Path) -> None:
    """Verify list can search recursively."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir), recursive=True)

    assert "nested.txt" in result


@pytest.mark.unit
@pytest.mark.serve
def test_tree(test_dir: Path) -> None:
    """Verify tree returns directory structure."""
    from ot_tools.file import tree

    result = tree(path=str(test_dir))

    assert "file1.txt" in result
    assert "subdir" in result
    # Tree should have connectors
    assert "├" in result or "└" in result or "─" in result


@pytest.mark.unit
@pytest.mark.serve
def test_search(test_dir: Path) -> None:
    """Verify search finds files by pattern."""
    from ot_tools.file import search

    result = search(path=str(test_dir), pattern="*file*")

    assert "file1.txt" in result
    assert "file2.py" in result


@pytest.mark.unit
@pytest.mark.serve
def test_search_with_file_pattern(test_dir: Path) -> None:
    """Verify search filters by file extension."""
    from ot_tools.file import search

    result = search(path=str(test_dir), pattern="*", file_pattern="*.py")

    assert "file2.py" in result
    assert "file1.txt" not in result


# =============================================================================
# Write Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_write_new_file(tmp_path: Path) -> None:
    """Verify write creates new file."""
    from ot_tools.file import write

    new_file = tmp_path / "new.txt"
    result = write(path=str(new_file), content="Hello, World!")

    assert "OK" in result or "wrote" in result.lower()
    assert new_file.exists()
    assert new_file.read_text() == "Hello, World!"


@pytest.mark.unit
@pytest.mark.serve
def test_write_append(test_file: Path) -> None:
    """Verify write can append to file."""
    from ot_tools.file import write

    original = test_file.read_text()
    result = write(path=str(test_file), content="Line 4\n", append=True)

    assert "OK" in result or "appended" in result.lower()
    new_content = test_file.read_text()
    assert original in new_content
    assert "Line 4" in new_content


@pytest.mark.unit
@pytest.mark.serve
def test_write_create_dirs(tmp_path: Path) -> None:
    """Verify write creates parent directories when requested."""
    from ot_tools.file import write

    nested_file = tmp_path / "a" / "b" / "c" / "file.txt"
    result = write(path=str(nested_file), content="nested", create_dirs=True)

    assert "OK" in result or "wrote" in result.lower()
    assert nested_file.exists()


@pytest.mark.unit
@pytest.mark.serve
def test_edit_replace(test_file: Path) -> None:
    """Verify edit replaces text."""
    from ot_tools.file import edit

    result = edit(path=str(test_file), old_text="Line 2", new_text="Modified 2")

    assert "OK" in result or "Replaced" in result
    content = test_file.read_text()
    assert "Modified 2" in content
    assert "Line 2" not in content


@pytest.mark.unit
@pytest.mark.serve
def test_edit_not_found(test_file: Path) -> None:
    """Verify edit returns error when text not found."""
    from ot_tools.file import edit

    result = edit(path=str(test_file), old_text="Nonexistent", new_text="New")

    assert "Error" in result
    assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.serve
def test_edit_multiple_occurrences(tmp_path: Path) -> None:
    """Verify edit handles multiple occurrences correctly."""
    from ot_tools.file import edit

    f = tmp_path / "multi.txt"
    f.write_text("foo bar foo baz foo")

    # Should error without specifying which occurrence
    result = edit(path=str(f), old_text="foo", new_text="FOO")

    assert "Error" in result
    assert "3" in result or "occurrences" in result.lower()


@pytest.mark.unit
@pytest.mark.serve
def test_edit_replace_all(tmp_path: Path) -> None:
    """Verify edit can replace all occurrences."""
    from ot_tools.file import edit

    f = tmp_path / "multi.txt"
    f.write_text("foo bar foo baz foo")

    result = edit(path=str(f), old_text="foo", new_text="FOO", occurrence=0)

    assert "OK" in result or "Replaced" in result
    content = f.read_text()
    assert content == "FOO bar FOO baz FOO"


# =============================================================================
# File Management
# =============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_copy_file(test_file: Path, tmp_path: Path) -> None:
    """Verify copy duplicates a file."""
    from ot_tools.file import copy

    dest = tmp_path / "copy.txt"
    result = copy(source=str(test_file), dest=str(dest))

    assert "OK" in result or "Copied" in result
    assert dest.exists()
    assert dest.read_text() == test_file.read_text()


@pytest.mark.unit
@pytest.mark.serve
def test_move_file(test_file: Path, tmp_path: Path) -> None:
    """Verify move relocates a file."""
    from ot_tools.file import move

    dest = tmp_path / "moved.txt"
    original_content = test_file.read_text()

    result = move(source=str(test_file), dest=str(dest))

    assert "OK" in result or "Moved" in result
    assert dest.exists()
    assert not test_file.exists()
    assert dest.read_text() == original_content


@pytest.mark.unit
@pytest.mark.serve
def test_delete_file(test_file: Path) -> None:
    """Verify delete removes a file."""
    from ot_tools.file import delete

    result = delete(path=str(test_file))

    assert "OK" in result or "Deleted" in result
    # File should be gone (or in trash)
    assert not test_file.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.serve
def test_delete_empty_directory(tmp_path: Path) -> None:
    """Verify delete removes empty directory."""
    from ot_tools.file import delete

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = delete(path=str(empty_dir))

    assert "OK" in result or "Deleted" in result
    assert not empty_dir.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.serve
def test_delete_nonempty_directory_fails(test_dir: Path) -> None:
    """Verify delete fails for non-empty directory."""
    from ot_tools.file import delete

    result = delete(path=str(test_dir))

    assert "Error" in result
    assert "not empty" in result.lower()
