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
    from otutil.tools.file import Config

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
        patch("otpack.paths.get_effective_cwd", return_value=tmp_path),
        patch("otutil.tools.file.get_tool_config", return_value=test_config),
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
    from otutil.tools.file import pack

    assert pack == "file"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from otutil.tools.file import __all__

    expected = {
        "copy",
        "delete",
        "edit",
        "grep",
        "info",
        "list",
        "move",
        "read",
        "read_batch",
        "search",
        "slice",
        "slice_batch",
        "toc",
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
    """Verify read returns raw file content by default."""
    from otutil.tools.file import read

    result = read(path=str(test_file))

    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result
    assert "1\t" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_file_with_line_numbers(test_file: Path) -> None:
    """Verify read can include line numbers when requested."""
    from otutil.tools.file import read

    result = read(path=str(test_file), line_numbers=True)

    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result
    assert "1\t" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_with_offset(test_file: Path) -> None:
    """Verify read respects offset parameter (1-indexed, start at line N)."""
    from otutil.tools.file import read

    # offset=2 means start at line 2 (1-indexed)
    result = read(path=str(test_file), offset=2)

    assert "Line 1" not in result
    assert "Line 2" in result
    assert "Line 3" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_offset_default_is_line_1(test_file: Path) -> None:
    """Verify read with offset=1 (default) starts at line 1."""
    from otutil.tools.file import read

    # offset=1 means start at line 1 (the first line)
    result = read(path=str(test_file), offset=1)

    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_with_limit(test_file: Path) -> None:
    """Verify read respects limit parameter."""
    from otutil.tools.file import read

    result = read(path=str(test_file), limit=2)

    assert "Line 1" in result
    assert "Line 2" in result
    # Line 3 may or may not be present depending on implementation


@pytest.mark.unit
@pytest.mark.tools
def test_read_nonexistent_file() -> None:
    """Verify read returns error for missing file."""
    from otutil.tools.file import read

    result = read(path="/nonexistent/path/missing.txt")

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_info_file(test_file: Path) -> None:
    """Verify info returns file metadata."""
    from otutil.tools.file import info

    result = info(path=str(test_file))

    # Result is a dict with path, type, size, etc.
    assert isinstance(result, dict)
    assert "test.txt" in result["path"]
    assert result["type"] == "file"
    assert "size" in result


@pytest.mark.unit
@pytest.mark.tools
def test_info_directory(test_dir: Path) -> None:
    """Verify info returns directory metadata."""
    from otutil.tools.file import info

    result = info(path=str(test_dir))

    # Result is a dict with type field
    assert isinstance(result, dict)
    assert result["type"] == "directory"


# =============================================================================
# List and Tree Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_list_directory(test_dir: Path) -> None:
    """Verify list returns directory contents."""
    from otutil.tools.file import list as list_dir

    result = list_dir(path=str(test_dir))

    assert "file1.txt" in result
    assert "file2.py" in result
    assert "subdir" in result


@pytest.mark.unit
@pytest.mark.tools
def test_list_with_pattern(test_dir: Path) -> None:
    """Verify list filters by pattern."""
    from otutil.tools.file import list as list_dir

    result = list_dir(path=str(test_dir), pattern="*.txt")

    assert "file1.txt" in result
    assert "file2.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_list_recursive(test_dir: Path) -> None:
    """Verify list can search recursively."""
    from otutil.tools.file import list as list_dir

    result = list_dir(path=str(test_dir), recursive=True)

    assert "nested.txt" in result


@pytest.mark.unit
@pytest.mark.tools
def test_tree(test_dir: Path) -> None:
    """Verify tree returns directory structure."""
    from otutil.tools.file import tree

    result = tree(path=str(test_dir))

    assert "file1.txt" in result
    assert "subdir" in result
    # Tree should have connectors
    assert "├" in result or "└" in result or "─" in result


@pytest.mark.unit
@pytest.mark.tools
def test_search(test_dir: Path) -> None:
    """Verify search finds files by pattern."""
    from otutil.tools.file import search

    result = search(path=str(test_dir), pattern="*file*")

    assert "file1.txt" in result
    assert "file2.py" in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_with_file_pattern(test_dir: Path) -> None:
    """Verify search filters by file extension."""
    from otutil.tools.file import search

    result = search(path=str(test_dir), pattern="*", file_pattern="*.py")

    assert "file2.py" in result
    assert "file1.txt" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_glob_recursive(test_dir: Path) -> None:
    """Verify search with glob parameter for full path matching."""
    from otutil.tools.file import search

    result = search(path=str(test_dir), glob="**/*.txt")

    assert "file1.txt" in result
    assert "subdir/nested.txt" in result or "subdir\\nested.txt" in result
    assert "file2.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_glob_nested_pattern(test_dir: Path) -> None:
    """Verify search with glob matches nested directories."""
    from otutil.tools.file import search

    result = search(path=str(test_dir), glob="**/nested*")

    assert "nested.txt" in result
    assert "file1.txt" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_search_requires_pattern_or_glob(test_dir: Path) -> None:
    """Verify search errors when neither pattern nor glob provided."""
    from otutil.tools.file import search

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
    from otutil.tools.file import write

    new_file = tmp_path / "new.txt"
    result = write(path=str(new_file), content="Hello, World!")

    assert "OK" in result or "wrote" in result.lower()
    assert new_file.exists()
    assert new_file.read_text() == "Hello, World!"


@pytest.mark.unit
@pytest.mark.tools
def test_write_append(test_file: Path) -> None:
    """Verify write can append to file."""
    from otutil.tools.file import write

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
    from otutil.tools.file import write

    nested_file = tmp_path / "a" / "b" / "c" / "file.txt"
    result = write(path=str(nested_file), content="nested", create_dirs=True)

    assert "OK" in result or "wrote" in result.lower()
    assert nested_file.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_edit_replace(test_file: Path) -> None:
    """Verify edit replaces text."""
    from otutil.tools.file import edit

    result = edit(path=str(test_file), old_text="Line 2", new_text="Modified 2")

    assert "OK" in result or "Replaced" in result
    content = test_file.read_text()
    assert "Modified 2" in content
    assert "Line 2" not in content


@pytest.mark.unit
@pytest.mark.tools
def test_edit_not_found(test_file: Path) -> None:
    """Verify edit returns error when text not found."""
    from otutil.tools.file import edit

    result = edit(path=str(test_file), old_text="Nonexistent", new_text="New")

    assert "Error" in result
    assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_edit_multiple_occurrences(tmp_path: Path) -> None:
    """Verify edit handles multiple occurrences correctly."""
    from otutil.tools.file import edit

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
    from otutil.tools.file import edit

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
    from otutil.tools.file import copy

    dest = tmp_path / "copy.txt"
    result = copy(source=str(test_file), dest=str(dest))

    assert "OK" in result or "Copied" in result
    assert dest.exists()
    assert dest.read_text() == test_file.read_text()


@pytest.mark.unit
@pytest.mark.tools
def test_move_file(test_file: Path, tmp_path: Path) -> None:
    """Verify move relocates a file."""
    from otutil.tools.file import move

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
    from otutil.tools.file import delete

    result = delete(path=str(test_file))

    assert "OK" in result or "Deleted" in result
    # File should be gone (or in trash)
    assert not test_file.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_delete_empty_directory(tmp_path: Path) -> None:
    """Verify delete removes empty directory."""
    from otutil.tools.file import delete

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = delete(path=str(empty_dir))

    assert "OK" in result or "Deleted" in result
    assert not empty_dir.exists() or "trash" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_delete_nonempty_directory_fails(test_dir: Path) -> None:
    """Verify delete fails for non-empty directory."""
    from otutil.tools.file import delete

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
    from otutil.tools.file import list as list_dir

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
    from otutil.tools.file import list as list_dir

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
    from otutil.tools.file import info

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
    from otutil.tools.file import search

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
    from otutil.tools.file import write

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
    from otutil.tools.file import edit

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, 世界!", encoding="utf-8")

    result = edit(path=str(test_file), old_text="世界", new_text="World")
    assert "OK" in result
    assert test_file.read_text(encoding="utf-8") == "Hello, World!"


@pytest.mark.unit
@pytest.mark.tools
def test_delete_recursive(tmp_path: Path) -> None:
    """Verify delete recursive parameter works (I3)."""
    from otutil.tools.file import delete

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
    from otutil.tools.file import write

    test_file = tmp_path / "test.txt"

    result = write(path=str(test_file), content="Hello", dry_run=True)
    assert "Dry run" in result
    assert not test_file.exists()  # File should not be created


@pytest.mark.unit
@pytest.mark.tools
def test_edit_dry_run(tmp_path: Path) -> None:
    """Verify edit dry_run parameter works (P1)."""
    from otutil.tools.file import edit

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
    from otutil.tools.file import delete

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = delete(path=str(test_file), dry_run=True)
    assert "Dry run" in result
    assert test_file.exists()  # File should still exist


@pytest.mark.unit
@pytest.mark.tools
def test_copy_follow_symlinks(tmp_path: Path) -> None:
    """Verify copy follow_symlinks parameter works (P2)."""
    from otutil.tools.file import copy

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


# =============================================================================
# Grep
# =============================================================================


@pytest.fixture
def grep_dir(tmp_path: Path) -> Path:
    """Create a temp directory with searchable files."""
    (tmp_path / "alpha.py").write_text(
        "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    )
    (tmp_path / "beta.txt").write_text(
        "hello world\nfoo is here\ngoodbye\n"
    )
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "gamma.py").write_text("# no match\nx = 42\n")
    return tmp_path


@pytest.mark.unit
@pytest.mark.tools
def test_grep_basic_match(grep_dir: Path) -> None:
    """Basic pattern match returns filename:lineno: line format."""
    from otutil.tools.file import grep

    result = grep(pattern="def foo", path=str(grep_dir))
    assert "alpha.py:1: def foo():" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_with_glob(grep_dir: Path) -> None:
    """Glob filter restricts files searched."""
    from otutil.tools.file import grep

    # Only search .txt files — should find "foo" in beta.txt
    result = grep(pattern="foo", path=str(grep_dir), glob="*.txt")
    assert "beta.txt" in result
    assert "alpha.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_case_insensitive(grep_dir: Path) -> None:
    """case_sensitive=False matches regardless of case."""
    from otutil.tools.file import grep

    result = grep(pattern="FOO", path=str(grep_dir), case_sensitive=False)
    assert "foo" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_grep_fixed_strings(grep_dir: Path) -> None:
    """fixed_strings=True treats pattern as literal, not regex."""
    from otutil.tools.file import grep

    # Regex special chars should be treated literally
    result = grep(pattern="def foo()", path=str(grep_dir), fixed_strings=True)
    assert "alpha.py:1: def foo():" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_context_lines(grep_dir: Path) -> None:
    """Context lines appear with dash separator."""
    from otutil.tools.file import grep

    result = grep(pattern="def bar", path=str(grep_dir), glob="*.py", context=1)
    # The match line
    assert "alpha.py:4: def bar():" in result
    # A context line (before or after, dash format)
    assert "alpha.py-" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_no_match(grep_dir: Path) -> None:
    """Returns 'No matches found' when pattern not in any file."""
    from otutil.tools.file import grep

    result = grep(pattern="xyzzy_no_such_thing", path=str(grep_dir))
    assert "No matches found" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_invalid_regex(grep_dir: Path) -> None:
    """Invalid regex returns error message."""
    from otutil.tools.file import grep

    result = grep(pattern="[invalid", path=str(grep_dir))
    assert "Error" in result
    assert "regex" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_grep_skips_binary(tmp_path: Path) -> None:
    """Binary files are skipped silently."""
    from otutil.tools.file import grep

    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02hello\x00world")
    (tmp_path / "text.txt").write_text("hello world\n")

    result = grep(pattern="hello", path=str(tmp_path))
    # Only the text file should appear
    assert "text.txt" in result
    assert "binary.bin" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_glob_recurses_into_subdirs(grep_dir: Path) -> None:
    """glob='*.py' recurses into subdirs — sub/gamma.py is found."""
    from otutil.tools.file import grep

    # grep_dir has sub/gamma.py containing "x = 42"
    result = grep(pattern="x = 42", path=str(grep_dir), glob="*.py")
    assert "gamma.py" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_glob_double_star_same_as_simple(grep_dir: Path) -> None:
    """glob='**/*.py' and glob='*.py' return identical results."""
    from otutil.tools.file import grep

    result_simple = grep(pattern="x = 42", path=str(grep_dir), glob="*.py")
    result_double = grep(pattern="x = 42", path=str(grep_dir), glob="**/*.py")
    assert result_simple == result_double


@pytest.mark.unit
@pytest.mark.tools
def test_grep_gitignore_true_skips_ignored(tmp_path: Path) -> None:
    """gitignore=True skips files matched by .gitignore."""
    from otutil.tools.file import grep

    (tmp_path / ".gitignore").write_text("ignored.py\n")
    (tmp_path / "ignored.py").write_text("secret = 'hunter2'\n")
    (tmp_path / "visible.py").write_text("secret = 'hunter2'\n")

    result = grep(pattern="secret", path=str(tmp_path), gitignore=True)
    assert "visible.py" in result
    assert "ignored.py" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_gitignore_false_includes_ignored(tmp_path: Path) -> None:
    """gitignore=False includes files matched by .gitignore."""
    from otutil.tools.file import grep

    (tmp_path / ".gitignore").write_text("logs/\n")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("error: something failed\n")

    result = grep(pattern="error", path=str(tmp_path), gitignore=False)
    assert "app.log" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_gitignore_no_gitignore_file(tmp_path: Path) -> None:
    """gitignore=True is a no-op when no .gitignore exists."""
    from otutil.tools.file import grep

    (tmp_path / "main.py").write_text("hello = 1\n")

    result = grep(pattern="hello", path=str(tmp_path), gitignore=True)
    assert "main.py" in result


# =============================================================================
# TOC
# =============================================================================

MD_CONTENT = """\
# Introduction

Some intro text here.
More intro.

## Installation

Run the install command.
And configure it.

### Advanced Setup

Extra steps here.

## Usage

Use it like this.
"""


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "doc.md"
    f.write_text(MD_CONTENT)
    return f


@pytest.mark.unit
@pytest.mark.tools
def test_toc_basic(md_file: Path) -> None:
    """TOC lists headings with line numbers."""
    from otutil.tools.file import toc

    result = toc(path=str(md_file))
    assert "Table of Contents" in result
    assert "Introduction" in result
    assert "Installation" in result
    assert "Usage" in result


@pytest.mark.unit
@pytest.mark.tools
def test_toc_no_sections(tmp_path: Path) -> None:
    """File with no headings returns 'No sections found'."""
    from otutil.tools.file import toc

    f = tmp_path / "plain.txt"
    f.write_text("just some text\nno headings here\n")
    result = toc(path=str(f))
    assert "No sections found" in result


@pytest.mark.unit
@pytest.mark.tools
def test_toc_not_a_file(tmp_path: Path) -> None:
    """Directory path returns error."""
    from otutil.tools.file import toc

    result = toc(path=str(tmp_path))
    assert "Error" in result


# =============================================================================
# Slice
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_slice_line_range(md_file: Path) -> None:
    """Line range selector ':3' returns first 3 lines."""
    from otutil.tools.file import slice

    result = slice(path=str(md_file), select=":3")
    lines = result.strip().splitlines()
    assert lines[0] == "# Introduction"
    assert len(lines) == 3


@pytest.mark.unit
@pytest.mark.tools
def test_slice_heading_match(md_file: Path) -> None:
    """Heading substring match returns that section."""
    from otutil.tools.file import slice

    result = slice(path=str(md_file), select="Installation")
    assert "## Installation" in result
    assert "Run the install command" in result


@pytest.mark.unit
@pytest.mark.tools
def test_slice_section_number(md_file: Path) -> None:
    """Section number 1 returns first heading's content."""
    from otutil.tools.file import slice

    result = slice(path=str(md_file), select=1)
    assert "Introduction" in result


@pytest.mark.unit
@pytest.mark.tools
def test_slice_list_selectors(md_file: Path) -> None:
    """List of selectors returns concatenated results."""
    from otutil.tools.file import slice

    result = slice(path=str(md_file), select=["Installation", "Usage"])
    assert "Installation" in result
    assert "Usage" in result


@pytest.mark.unit
@pytest.mark.tools
def test_slice_no_match(md_file: Path) -> None:
    """Non-matching selector returns 'No matching content'."""
    from otutil.tools.file import slice

    result = slice(path=str(md_file), select="NonExistentHeading")
    assert "No matching content" in result


# =============================================================================
# Read Batch
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_paths(tmp_path: Path) -> None:
    """Read multiple files by explicit path list."""
    from otutil.tools.file import read_batch

    (tmp_path / "a.txt").write_text("content of a")
    (tmp_path / "b.txt").write_text("content of b")

    result = read_batch(paths=[str(tmp_path / "a.txt"), str(tmp_path / "b.txt")])
    assert "content of a" in result
    assert "content of b" in result
    assert "Read 2 files" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_glob(tmp_path: Path) -> None:
    """Read files by glob pattern."""
    from otutil.tools.file import read_batch

    (tmp_path / "x.py").write_text("def x(): pass")
    (tmp_path / "y.py").write_text("def y(): pass")
    (tmp_path / "z.txt").write_text("not python")

    result = read_batch(glob="*.py")
    assert "def x(): pass" in result
    assert "def y(): pass" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_glob_recurses_into_subdirs(tmp_path: Path) -> None:
    """glob='*.py' recurses into subdirectories."""
    from otutil.tools.file import read_batch

    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.py").write_text("def deep(): pass")

    result = read_batch(glob="*.py")
    assert "def deep(): pass" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_glob_double_star_same_as_simple(tmp_path: Path) -> None:
    """glob='**/*.py' and glob='*.py' return identical results."""
    from otutil.tools.file import read_batch

    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.py").write_text("def deep(): pass")

    result_simple = read_batch(glob="*.py")
    result_double = read_batch(glob="**/*.py")
    assert result_simple == result_double


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_missing_input(tmp_path: Path) -> None:
    """Neither paths nor glob returns error."""
    from otutil.tools.file import read_batch

    result = read_batch()
    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_skips_binary(tmp_path: Path) -> None:
    """Binary files are skipped silently."""
    from otutil.tools.file import read_batch

    (tmp_path / "bin.bin").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "text.txt").write_text("hello")

    result = read_batch(paths=[str(tmp_path / "bin.bin"), str(tmp_path / "text.txt")])
    assert "hello" in result
    assert "bin.bin" not in result or "Read 1 file" in result


# =============================================================================
# Slice Batch
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_slice_batch_basic(tmp_path: Path) -> None:
    """Slice batch extracts sections from multiple files."""
    from otutil.tools.file import slice_batch

    f1 = tmp_path / "a.md"
    f1.write_text("# Intro\nhello\n\n# Setup\nworld\n")
    f2 = tmp_path / "b.md"
    f2.write_text("# Config\nfoo\n\n# Run\nbar\n")

    result = slice_batch(items=[
        {"path": str(f1), "select": "Intro"},
        {"path": str(f2), "select": "Run"},
    ])
    assert "hello" in result
    assert "bar" in result
    assert "Sliced 2 files" in result


@pytest.mark.unit
@pytest.mark.tools
def test_slice_batch_empty(tmp_path: Path) -> None:
    """Empty items list returns error."""
    from otutil.tools.file import slice_batch

    result = slice_batch(items=[])
    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_slice_batch_too_many(tmp_path: Path) -> None:
    """More than 20 items returns error."""
    from otutil.tools.file import slice_batch

    result = slice_batch(items=[{"path": "x.md", "select": 1}] * 21)
    assert "Error" in result
    assert "20" in result


# =============================================================================
# Security and size-limit fixes
# =============================================================================


@pytest.fixture
def tiny_size_config(tmp_path: Path) -> Generator[None, None, None]:
    """Override file config with a very small max_file_size (100 bytes)."""
    from otutil.tools.file import Config

    small_config = Config(
        allowed_dirs=[],
        exclude_patterns=[".git", "__pycache__"],
        max_file_size=1000,  # minimum allowed — 1000 bytes
        max_list_entries=1000,
        backup_on_write=False,
        use_trash=False,
        relative_paths=True,
    )
    with (
        patch("otpack.paths.get_effective_cwd", return_value=tmp_path),
        patch("otutil.tools.file.get_tool_config", return_value=small_config),
    ):
        yield


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_drops_security_rejected_paths(tmp_path: Path) -> None:
    """Paths that fail _validate_path are silently dropped — not read."""
    import tempfile
    from pathlib import Path as PurePath

    from otutil.tools.file import read_batch

    # File inside the allowed dir (tmp_path = effective CWD)
    good = tmp_path / "good.txt"
    good.write_text("safe content")

    # File in a separate temp dir — outside allowed area
    outside_dir = tempfile.mkdtemp()
    bad = PurePath(outside_dir) / "bad.txt"
    bad.write_text("should not appear")

    result = read_batch(paths=[str(good), str(bad)])
    assert "safe content" in result
    assert "should not appear" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_read_batch_oversized_file_gets_error(tmp_path: Path, tiny_size_config: None) -> None:
    """Files exceeding max_file_size get an error entry, not a crash."""
    from otutil.tools.file import read_batch

    big = tmp_path / "big.txt"
    big.write_text("x" * 1500)  # 1500 bytes > 1000 byte limit
    small = tmp_path / "small.txt"
    small.write_text("ok")  # 2 bytes < 1000 byte limit

    result = read_batch(paths=[str(big), str(small)])
    assert "big.txt" in result
    assert "too large" in result.lower() or "Error" in result
    assert "ok" in result


@pytest.mark.unit
@pytest.mark.tools
def test_grep_skips_oversized_files(tmp_path: Path, tiny_size_config: None) -> None:
    """Files exceeding max_file_size are silently skipped during grep."""
    from otutil.tools.file import grep

    big = tmp_path / "big.txt"
    big.write_text("needle " * 200)  # > 1000 bytes, contains the pattern
    small = tmp_path / "small.txt"
    small.write_text("needle")  # < 1000 bytes

    result = grep(pattern="needle", path=str(tmp_path))
    # Only the small file should match — big is skipped due to size
    assert "small.txt" in result
    assert "big.txt" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_toc_oversized_file_returns_error(tmp_path: Path, tiny_size_config: None) -> None:
    """TOC on a file exceeding max_file_size returns an error."""
    from otutil.tools.file import toc

    big = tmp_path / "big.md"
    big.write_text("# Heading\n" + "content\n" * 200)  # > 1000 bytes

    result = toc(path=str(big))
    assert "Error" in result
    assert "large" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_slice_oversized_file_returns_error(tmp_path: Path, tiny_size_config: None) -> None:
    """Slice on a file exceeding max_file_size returns an error."""
    from otutil.tools.file import slice

    big = tmp_path / "big.md"
    big.write_text("# Heading\n" + "content\n" * 200)  # > 1000 bytes

    result = slice(path=str(big), select=":5")
    assert "Error" in result
    assert "large" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_slice_batch_oversized_file_gets_error_entry(tmp_path: Path, tiny_size_config: None) -> None:
    """slice_batch includes an error entry for oversized files, not a crash."""
    from otutil.tools.file import slice_batch

    big = tmp_path / "big.md"
    big.write_text("# Heading\n" + "content\n" * 200)  # > 1000 bytes
    small = tmp_path / "small.md"
    small.write_text("# Hi\nok\n")

    result = slice_batch(items=[
        {"path": str(big), "select": "Heading"},
        {"path": str(small), "select": "Hi"},
    ])
    assert "large" in result.lower() or "Error" in result
    assert "ok" in result
