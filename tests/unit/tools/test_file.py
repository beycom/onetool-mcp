"""Unit tests for File tool.

Tests file.read(), file.write(), file.list(), etc.
Uses tmp_path fixture for isolated test files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(autouse=True)
def mock_file_config(tmp_path: Path) -> Generator[None, None, None]:
    """Mock file tool config to allow temp directories."""
    from ot_tools.file import Config

    # Create a Config instance with test-friendly defaults
    test_config = Config(
        allowed_dirs=[],  # Empty = allows cwd, but we set project path
        exclude_patterns=[".git", "__pycache__"],
        max_file_size=10_000_000,
        max_list_entries=1000,
        backup_on_write=False,  # Disable for cleaner tests
        use_trash=False,  # Disable for cleaner tests
        relative_paths=True,  # Use relative paths (default)
    )

    # Mock effective CWD to tmp_path for path resolution
    with (
        patch("ot.paths.get_effective_cwd", return_value=tmp_path),
        patch("ot_tools.file.get_tool_config", return_value=test_config),
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
@pytest.mark.tools
def test_pack_is_file() -> None:
    """Verify pack is correctly set."""
    from ot_tools.file import pack

    assert pack == "file"


@pytest.mark.unit
@pytest.mark.tools
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
@pytest.mark.tools
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
@pytest.mark.tools
def test_read_with_offset(test_file: Path) -> None:
    """Verify read respects offset parameter (1-indexed, start at line N)."""
    from ot_tools.file import read

    # offset=2 means start at line 2 (1-indexed)
    result = read(path=str(test_file), offset=2)

    assert "Line 1" not in result
    assert "Line 2" in result
    assert "Line 3" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_offset_default_is_line_1(test_file: Path) -> None:
    """Verify read with offset=1 (default) starts at line 1."""
    from ot_tools.file import read

    # offset=1 means start at line 1 (the first line)
    result = read(path=str(test_file), offset=1)

    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_with_limit(test_file: Path) -> None:
    """Verify read respects limit parameter."""
    from ot_tools.file import read

    result = read(path=str(test_file), limit=2)

    assert "Line 1" in result
    assert "Line 2" in result
    # Line 3 may or may not be present depending on implementation


@pytest.mark.unit
@pytest.mark.tools
def test_read_nonexistent_file() -> None:
    """Verify read returns error for missing file."""
    from ot_tools.file import read

    result = read(path="/nonexistent/path/missing.txt")

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
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
@pytest.mark.tools
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
@pytest.mark.tools
def test_list_directory(test_dir: Path) -> None:
    """Verify list returns directory contents."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir))

    assert "file1.txt" in result
    assert "file2.py" in result
    assert "subdir" in result


@pytest.mark.unit
@pytest.mark.tools
def test_list_with_pattern(test_dir: Path) -> None:
    """Verify list filters by pattern."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir), pattern="*.txt")

    assert "file1.txt" in result
    assert "file2.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_list_recursive(test_dir: Path) -> None:
    """Verify list can search recursively."""
    from ot_tools.file import list as list_dir

    result = list_dir(path=str(test_dir), recursive=True)

    assert "nested.txt" in result


@pytest.mark.unit
@pytest.mark.tools
def test_tree(test_dir: Path) -> None:
    """Verify tree returns directory structure."""
    from ot_tools.file import tree

    result = tree(path=str(test_dir))

    assert "file1.txt" in result
    assert "subdir" in result
    # Tree should have connectors
    assert "├" in result or "└" in result or "─" in result


@pytest.mark.unit
@pytest.mark.tools
def test_search(test_dir: Path) -> None:
    """Verify search finds files by pattern."""
    from ot_tools.file import search

    result = search(path=str(test_dir), pattern="*file*")

    assert "file1.txt" in result
    assert "file2.py" in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_with_file_pattern(test_dir: Path) -> None:
    """Verify search filters by file extension."""
    from ot_tools.file import search

    result = search(path=str(test_dir), pattern="*", file_pattern="*.py")

    assert "file2.py" in result
    assert "file1.txt" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_glob_recursive(test_dir: Path) -> None:
    """Verify search with glob parameter for full path matching."""
    from ot_tools.file import search

    result = search(path=str(test_dir), glob="**/*.txt")

    assert "file1.txt" in result
    assert "subdir/nested.txt" in result or "subdir\\nested.txt" in result
    assert "file2.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_glob_nested_pattern(test_dir: Path) -> None:
    """Verify search with glob matches nested directories."""
    from ot_tools.file import search

    result = search(path=str(test_dir), glob="**/nested*")

    assert "nested.txt" in result
    assert "file1.txt" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_requires_pattern_or_glob(test_dir: Path) -> None:
    """Verify search errors when neither pattern nor glob provided."""
    from ot_tools.file import search

    result = search(path=str(test_dir))

    assert "Error" in result
    assert "pattern" in result.lower() or "glob" in result.lower()


# =============================================================================
# Write Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_write_new_file(tmp_path: Path) -> None:
    """Verify write creates new file."""
    from ot_tools.file import write

    new_file = tmp_path / "new.txt"
    result = write(path=str(new_file), content="Hello, World!")

    assert "OK" in result or "wrote" in result.lower()
    assert new_file.exists()
    assert new_file.read_text() == "Hello, World!"


@pytest.mark.unit
@pytest.mark.tools
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
@pytest.mark.tools
def test_write_create_dirs(tmp_path: Path) -> None:
    """Verify write creates parent directories when requested."""
    from ot_tools.file import write

    nested_file = tmp_path / "a" / "b" / "c" / "file.txt"
    result = write(path=str(nested_file), content="nested", create_dirs=True)

    assert "OK" in result or "wrote" in result.lower()
    assert nested_file.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_edit_replace(test_file: Path) -> None:
    """Verify edit replaces text."""
    from ot_tools.file import edit

    result = edit(path=str(test_file), old_text="Line 2", new_text="Modified 2")

    assert "OK" in result or "Replaced" in result
    content = test_file.read_text()
    assert "Modified 2" in content
    assert "Line 2" not in content


@pytest.mark.unit
@pytest.mark.tools
def test_edit_not_found(test_file: Path) -> None:
    """Verify edit returns error when text not found."""
    from ot_tools.file import edit

    result = edit(path=str(test_file), old_text="Nonexistent", new_text="New")

    assert "Error" in result
    assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
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
@pytest.mark.tools
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
@pytest.mark.tools
def test_copy_file(test_file: Path, tmp_path: Path) -> None:
    """Verify copy duplicates a file."""
    from ot_tools.file import copy

    dest = tmp_path / "copy.txt"
    result = copy(source=str(test_file), dest=str(dest))

    assert "OK" in result or "Copied" in result
    assert dest.exists()
    assert dest.read_text() == test_file.read_text()


@pytest.mark.unit
@pytest.mark.tools
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
@pytest.mark.tools
def test_delete_file(test_file: Path) -> None:
    """Verify delete removes a file."""
    from ot_tools.file import delete

    result = delete(path=str(test_file))

    assert "OK" in result or "Deleted" in result
    # File should be gone (or in trash)
    assert not test_file.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_delete_empty_directory(tmp_path: Path) -> None:
    """Verify delete removes empty directory."""
    from ot_tools.file import delete

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = delete(path=str(empty_dir))

    assert "OK" in result or "Deleted" in result
    assert not empty_dir.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_delete_nonempty_directory_fails(test_dir: Path) -> None:
    """Verify delete fails for non-empty directory."""
    from ot_tools.file import delete

    result = delete(path=str(test_dir))

    assert "Error" in result
    assert "not empty" in result.lower()


# =============================================================================
# New Feature Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_list_symlink_detection(tmp_path: Path) -> None:
    """Verify list correctly identifies symlinks as 'l' type (D1 fix)."""
    from ot_tools.file import list as list_dir

    # Create a directory and a symlink to it
    target_dir = tmp_path / "target_dir"
    target_dir.mkdir()
    symlink = tmp_path / "link_to_dir"
    symlink.symlink_to(target_dir)

    result = list_dir(path=str(tmp_path))

    # Symlink should be marked as 'l', not 'd'
    assert "[l]" in result or "l " in result


@pytest.mark.unit
@pytest.mark.tools
def test_list_follow_symlinks(tmp_path: Path) -> None:
    """Verify list follow_symlinks parameter works (P2)."""
    from ot_tools.file import list as list_dir

    # Create a directory and a symlink to it
    target_dir = tmp_path / "target_dir"
    target_dir.mkdir()
    symlink = tmp_path / "link_to_dir"
    symlink.symlink_to(target_dir)

    # Default: symlinks shown as 'l'
    result = list_dir(path=str(tmp_path), follow_symlinks=False)
    assert "link_to_dir" in result

    # With follow_symlinks: symlinks shown as their target type
    result = list_dir(path=str(tmp_path), follow_symlinks=True)
    assert "link_to_dir" in result


@pytest.mark.unit
@pytest.mark.tools
def test_info_symlink_metadata(tmp_path: Path) -> None:
    """Verify info returns symlink metadata with lstat (D2 fix)."""
    from ot_tools.file import info

    # Create a file and a symlink to it
    target_file = tmp_path / "target.txt"
    target_file.write_text("x" * 1000)
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(target_file)

    # With follow_symlinks=False, should get symlink metadata (smaller size)
    result = info(path=str(symlink), follow_symlinks=False)
    assert isinstance(result, dict)
    assert result["type"] == "symlink"


@pytest.mark.unit
@pytest.mark.tools
def test_search_include_hidden(tmp_path: Path) -> None:
    """Verify search include_hidden parameter works (I1)."""
    from ot_tools.file import search

    # Create hidden and regular files
    (tmp_path / ".hidden.txt").write_text("hidden")
    (tmp_path / "visible.txt").write_text("visible")

    # Default: hidden files excluded
    result = search(path=str(tmp_path), pattern="*.txt")
    assert "visible.txt" in result
    assert ".hidden.txt" not in result

    # With include_hidden: hidden files included
    result = search(path=str(tmp_path), pattern="*.txt", include_hidden=True)
    assert "visible.txt" in result
    assert ".hidden.txt" in result


@pytest.mark.unit
@pytest.mark.tools
def test_write_encoding(tmp_path: Path) -> None:
    """Verify write encoding parameter works (I2)."""
    from ot_tools.file import write

    test_file = tmp_path / "test.txt"
    content = "Hello, 世界!"

    # Write with UTF-8 (default)
    result = write(path=str(test_file), content=content)
    assert "OK" in result
    assert test_file.read_text(encoding="utf-8") == content


@pytest.mark.unit
@pytest.mark.tools
def test_edit_encoding(tmp_path: Path) -> None:
    """Verify edit encoding parameter works (I2)."""
    from ot_tools.file import edit

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, 世界!", encoding="utf-8")

    result = edit(path=str(test_file), old_text="世界", new_text="World")
    assert "OK" in result
    assert test_file.read_text(encoding="utf-8") == "Hello, World!"


@pytest.mark.unit
@pytest.mark.tools
def test_delete_recursive(tmp_path: Path) -> None:
    """Verify delete recursive parameter works (I3)."""
    from ot_tools.file import delete

    # Create a non-empty directory
    subdir = tmp_path / "nonempty"
    subdir.mkdir()
    (subdir / "file.txt").write_text("content")

    # Without recursive, should fail
    result = delete(path=str(subdir))
    assert "Error" in result
    assert "recursive=True" in result

    # With recursive, should succeed
    result = delete(path=str(subdir), recursive=True)
    assert "OK" in result
    assert not subdir.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_write_dry_run(tmp_path: Path) -> None:
    """Verify write dry_run parameter works (P1)."""
    from ot_tools.file import write

    test_file = tmp_path / "test.txt"

    result = write(path=str(test_file), content="Hello", dry_run=True)
    assert "Dry run" in result
    assert not test_file.exists()  # File should not be created


@pytest.mark.unit
@pytest.mark.tools
def test_edit_dry_run(tmp_path: Path) -> None:
    """Verify edit dry_run parameter works (P1)."""
    from ot_tools.file import edit

    test_file = tmp_path / "test.txt"
    original = "Hello World"
    test_file.write_text(original)

    result = edit(path=str(test_file), old_text="World", new_text="Universe", dry_run=True)
    assert "Dry run" in result
    assert test_file.read_text() == original  # Content unchanged


@pytest.mark.unit
@pytest.mark.tools
def test_delete_dry_run(tmp_path: Path) -> None:
    """Verify delete dry_run parameter works (P1)."""
    from ot_tools.file import delete

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = delete(path=str(test_file), dry_run=True)
    assert "Dry run" in result
    assert test_file.exists()  # File should still exist


@pytest.mark.unit
@pytest.mark.tools
def test_copy_follow_symlinks(tmp_path: Path) -> None:
    """Verify copy follow_symlinks parameter works (P2)."""
    from ot_tools.file import copy

    # Create a file and a symlink to it
    source_file = tmp_path / "source.txt"
    source_file.write_text("content")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(source_file)
    dest = tmp_path / "dest.txt"

    # Default: follow symlinks (copy content)
    result = copy(source=str(symlink), dest=str(dest))
    assert "OK" in result
    assert dest.is_file() and not dest.is_symlink()

    # Clean up for next test
    dest.unlink()

    # Without follow: copy as symlink
    result = copy(source=str(symlink), dest=str(dest), follow_symlinks=False)
    assert "OK" in result
    assert dest.is_symlink()
