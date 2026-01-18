"""Secure file operations for OneTool.

Provides file reading, writing, editing, and management with configurable
security boundaries. All paths are validated against allowed directories.

Configuration via ot-serve.yaml:
    tools:
      file:
        allowed_dirs: ["."]          # Allowed directories (empty = cwd only)
        exclude_patterns: [".git"]   # Patterns to exclude
        max_file_size: 10000000      # Max file size (10MB)
        backup_on_write: true        # Create .bak before writes

Attribution: Inspired by fast-filesystem-mcp (Apache 2.0)
https://github.com/efforthye/fast-filesystem-mcp
"""

from __future__ import annotations

# Note: This module defines a function named `list` which shadows the builtin.
# Use typing.List for type annotations to avoid mypy confusion.
from typing import List  # noqa: UP035

namespace = "file"

__all__ = [
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
]

import fnmatch
import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ot.config import get_config
from ot.logging import LogSpan
from ot.paths import get_effective_cwd

# Optional send2trash for safe deletion
try:
    import send2trash

    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

# Pre-computed set of text characters for binary detection (P2 fix)
# Includes common control chars (bell, backspace, tab, newline, formfeed, carriage return, escape)
# plus all printable ASCII and extended ASCII
_TEXT_CHARS = frozenset({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))


# ============================================================================
# Path Validation
# ============================================================================


def _get_file_config() -> Any:
    """Get file tool configuration."""
    return get_config().tools.file


def _expand_path(path: str) -> Path:
    """Resolve a file path relative to project directory.

    Path resolution follows project conventions:
        - Relative paths: resolved relative to project directory (OT_CWD)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory

    Note: ${VAR} patterns are NOT expanded. Use ~/path instead of ${HOME}/path.

    Args:
        path: Path string (can contain ~)

    Returns:
        Resolved absolute Path (not yet validated for existence)
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return (get_effective_cwd() / p).resolve()


def _is_excluded(path: Path, exclude_patterns: List[str]) -> bool:  # noqa: UP006
    """Check if path matches any exclude pattern.

    Args:
        path: Resolved path to check
        exclude_patterns: List of fnmatch patterns

    Returns:
        True if path matches any exclude pattern
    """
    path_str = str(path)
    path_parts = path.parts

    for pattern in exclude_patterns:
        # Check full path
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True
        # Check each part of the path
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True

    return False


def _validate_path(
    path: str, *, must_exist: bool = True
) -> tuple[Path | None, str | None]:
    """Validate and resolve a path against security constraints.

    Args:
        path: User-provided path string
        must_exist: If True, path must exist

    Returns:
        Tuple of (resolved_path, error_message)
        If error, resolved_path is None
    """
    cfg = _get_file_config()

    # Expand and resolve
    try:
        resolved = _expand_path(path)
        # Always resolve to normalize ".." and follow symlinks for security
        # resolve() works on non-existent paths too (normalizes parent components)
        real_path = resolved.resolve()
    except (OSError, ValueError) as e:
        return None, f"Invalid path: {e}"

    # Check if path exists when required
    if must_exist and not resolved.exists():
        return None, f"Path not found: {path}"

    # Check against allowed directories
    cwd = get_effective_cwd()
    allowed_dirs: List[Path] = []  # noqa: UP006

    if cfg.allowed_dirs:
        for allowed in cfg.allowed_dirs:
            expanded = Path(allowed).expanduser()
            if expanded.is_absolute():
                allowed_dirs.append(expanded.resolve())
            else:
                allowed_dirs.append((cwd / expanded).resolve())
    else:
        # Default: only cwd and subdirectories
        allowed_dirs = [cwd]

    # Verify path is under an allowed directory
    is_allowed = False
    for allowed in allowed_dirs:
        try:
            real_path.relative_to(allowed)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        return None, "Access denied: path outside allowed directories"

    # Check exclude patterns
    if _is_excluded(real_path, cfg.exclude_patterns):
        return None, "Access denied: path matches exclude pattern"

    return resolved, None


def _check_file_size(path: Path) -> str | None:
    """Check if file exceeds max size limit.

    Args:
        path: Path to check

    Returns:
        Error message if too large, None if OK
    """
    cfg = _get_file_config()
    try:
        size = path.stat().st_size
        if size > cfg.max_file_size:
            max_mb = cfg.max_file_size / 1_000_000
            size_mb = size / 1_000_000
            return f"File too large: {size_mb:.1f}MB (max: {max_mb:.1f}MB)"
    except OSError as e:
        return f"Cannot check file size: {e}"
    return None


def _is_binary(data: bytes, sample_size: int = 8192) -> bool:
    """Detect if data appears to be binary.

    Args:
        data: Bytes to check
        sample_size: Number of bytes to sample

    Returns:
        True if data appears binary
    """
    sample = data[:sample_size]
    # Check for null bytes (common in binary files)
    if b"\x00" in sample:
        return True
    # Check ratio of non-printable characters using pre-computed set
    non_text = sum(1 for byte in sample if byte not in _TEXT_CHARS)
    return non_text / len(sample) > 0.3 if sample else False


def _format_yaml(data: Any) -> str:
    """Format data as YAML."""
    return yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    ).rstrip()


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable string like "1.23 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _create_backup(path: Path) -> str | None:
    """Create a backup of a file.

    Args:
        path: File to backup

    Returns:
        Error message if backup failed, None if OK
    """
    if not path.exists():
        return None

    cfg = _get_file_config()
    if not cfg.backup_on_write:
        return None

    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        shutil.copy2(path, backup_path)
    except OSError as e:
        return f"Backup failed: {e}"

    return None


# ============================================================================
# Read Operations
# ============================================================================


def read(
    *,
    path: str,
    offset: int = 0,
    limit: int | None = None,
    encoding: str = "utf-8",
) -> str:
    """Read file content with optional offset and limit.

    Reads text files line by line. For large files, use offset/limit
    for pagination. Binary files return a warning message.

    Args:
        path: Path to file (relative to cwd or absolute)
        offset: Line number to start from (0-indexed, default: 0)
        limit: Maximum lines to return (default: all remaining)
        encoding: Text encoding (default: utf-8)

    Returns:
        File content with line numbers, or error message

    Example:
        file.read(path="src/main.py")
        file.read(path="src/main.py", offset=100, limit=50)
        file.read(path="config.json", encoding="utf-8")
    """
    with LogSpan(span="file.read", path=path, offset=offset, limit=limit) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        if not resolved.is_file():
            s.add(error="not_a_file")
            return f"Error: Not a file: {path}"

        # Check file size
        size_error = _check_file_size(resolved)
        if size_error:
            s.add(error="file_too_large")
            return f"Error: {size_error}"

        try:
            # Read first chunk to check for binary content
            with resolved.open("rb") as f:
                sample = f.read(8192)
                if _is_binary(sample):
                    # Get full size for error message
                    f.seek(0, 2)  # Seek to end
                    size = f.tell()
                    s.add(error="binary_file")
                    return f"Error: Binary file detected ({size} bytes). Use appropriate tools for binary files."

            # Stream file line by line for efficient paginated reads (P1 fix)
            output_lines = []
            total_lines = 0
            lines_collected = 0
            end_line = offset + limit if limit else None

            try:
                with resolved.open("r", encoding=encoding) as f:
                    for line_num, line in enumerate(f):
                        total_lines = line_num + 1

                        # Skip lines before offset
                        if line_num < offset:
                            continue

                        # Stop if we've collected enough lines
                        if end_line and line_num >= end_line:
                            # Continue counting total lines
                            continue

                        # Collect this line
                        line_text = line.rstrip("\n\r")
                        output_lines.append(f"{line_num + 1:6d}\t{line_text}")
                        lines_collected += 1

            except UnicodeDecodeError:
                # Fallback: try charset detection
                try:
                    import charset_normalizer

                    raw_data = resolved.read_bytes()
                    detected = charset_normalizer.from_bytes(raw_data).best()
                    if detected:
                        content = str(detected)
                        lines = content.splitlines()
                        total_lines = len(lines)
                        end = offset + limit if limit else total_lines
                        for i, line in enumerate(lines[offset:end], start=offset + 1):
                            output_lines.append(f"{i:6d}\t{line}")
                            lines_collected += 1
                    else:
                        s.add(error="encoding_error")
                        return f"Error: Could not decode file with {encoding} or auto-detected encoding"
                except ImportError:
                    s.add(error="encoding_error")
                    return f"Error: Could not decode file as {encoding}. Try specifying correct encoding."

            if offset >= total_lines:
                s.add(resultLen=0, totalLines=total_lines)
                return f"(empty - offset {offset} >= total lines {total_lines})"

            result = "\n".join(output_lines)

            # Add pagination info if truncated
            remaining = total_lines - (offset + lines_collected)
            if remaining > 0:
                result += f"\n\n... ({remaining} more lines, use offset={offset + lines_collected} to continue)"

            s.add(
                resultLen=len(result),
                totalLines=total_lines,
                linesReturned=lines_collected,
            )
            return result

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def info(*, path: str) -> str:
    """Get file or directory metadata.

    Returns size, timestamps, permissions, and type information.

    Args:
        path: Path to file or directory

    Returns:
        YAML formatted metadata

    Example:
        file.info(path="src/main.py")
        file.info(path="./docs")
    """
    with LogSpan(span="file.info", path=path) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        try:
            st = resolved.stat()

            # Determine type (check symlink first - is_file/is_dir follow symlinks)
            if resolved.is_symlink():
                file_type = "symlink"
            elif resolved.is_file():
                file_type = "file"
            elif resolved.is_dir():
                file_type = "directory"
            else:
                file_type = "other"

            # Format timestamps
            created = datetime.fromtimestamp(st.st_ctime, tz=UTC).isoformat()
            modified = datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat()
            accessed = datetime.fromtimestamp(st.st_atime, tz=UTC).isoformat()

            # Format permissions
            mode = stat.filemode(st.st_mode)

            info_data: dict[str, Any] = {
                "path": str(resolved),
                "type": file_type,
                "size": st.st_size,
                "size_readable": _format_size(st.st_size),
                "permissions": mode,
                "created": created,
                "modified": modified,
                "accessed": accessed,
            }

            # Add symlink target if applicable
            if resolved.is_symlink():
                info_data["target"] = str(resolved.readlink())

            s.add(found=True, type=file_type)
            return _format_yaml(info_data)

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def list(
    *,
    path: str = ".",
    pattern: str | None = None,
    recursive: bool = False,
    include_hidden: bool = False,
    sort_by: str = "name",
    reverse: bool = False,
) -> str:
    """List directory contents.

    Lists files and directories with optional filtering and sorting.

    Args:
        path: Directory path (default: current directory)
        pattern: Glob pattern to filter (e.g., "*.py", "**/*.md")
        recursive: If True, list recursively (default: False)
        include_hidden: If True, include hidden files (default: False)
        sort_by: Sort field - "name", "type", "size", "modified" (default: "name")
        reverse: If True, reverse sort order (default: False)

    Returns:
        List of entries with type indicator and size

    Example:
        file.list()
        file.list(path="src", pattern="*.py")
        file.list(path=".", recursive=True, pattern="*.md")
        file.list(path=".", sort_by="size", reverse=True)
    """
    with LogSpan(
        span="file.list", path=path, pattern=pattern, recursive=recursive
    ) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        if not resolved.is_dir():
            s.add(error="not_a_directory")
            return f"Error: Not a directory: {path}"

        cfg = _get_file_config()

        try:
            # Collect entries with metadata: (type, rel_path, size, mtime, entry)
            entries: List[tuple[str, str, int, float]] = []  # noqa: UP006

            if pattern:
                matches = (
                    resolved.rglob(pattern) if recursive else resolved.glob(pattern)
                )
            else:
                matches = resolved.rglob("*") if recursive else resolved.iterdir()

            for entry in matches:
                # Skip hidden files unless requested
                if not include_hidden and entry.name.startswith("."):
                    continue

                # Check against exclude patterns
                if _is_excluded(entry, cfg.exclude_patterns):
                    continue

                # Get relative path from listing root
                try:
                    rel_path = entry.relative_to(resolved)
                except ValueError:
                    rel_path = entry

                # Type indicator and metadata
                try:
                    st = entry.stat()
                    size = st.st_size
                    mtime = st.st_mtime
                except OSError:
                    size = 0
                    mtime = 0

                if entry.is_dir():
                    type_ind = "d"
                elif entry.is_symlink():
                    type_ind = "l"
                else:
                    type_ind = "f"

                entries.append((type_ind, str(rel_path), size, mtime))

                # Enforce limit before sorting (will re-limit after sort)
                if len(entries) >= cfg.max_list_entries * 2:
                    break

            # Sort based on sort_by parameter
            if sort_by == "type":
                entries.sort(key=lambda x: (x[0], x[1].lower()), reverse=reverse)
            elif sort_by == "size":
                entries.sort(key=lambda x: (x[2], x[1].lower()), reverse=reverse)
            elif sort_by == "modified":
                entries.sort(key=lambda x: (x[3], x[1].lower()), reverse=reverse)
            else:  # name (default) - dirs first, then alphabetically
                entries.sort(
                    key=lambda x: (0 if x[0] == "d" else 1, x[1].lower()),
                    reverse=reverse,
                )

            # Limit after sorting
            truncated = len(entries) > cfg.max_list_entries
            entries = entries[: cfg.max_list_entries]

            # Format output with size for files
            lines = []
            for type_ind, rel, size, _ in entries:
                if type_ind == "f":
                    size_str = _format_size(size)
                    lines.append(f"{type_ind} {rel} ({size_str})")
                else:
                    lines.append(f"{type_ind} {rel}")

            if truncated:
                lines.append(f"\n... (truncated at {cfg.max_list_entries} entries)")

            s.add(fileCount=len(entries))
            return "\n".join(lines) if lines else "(empty directory)"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def tree(
    *,
    path: str = ".",
    max_depth: int = 3,
    include_hidden: bool = False,
) -> str:
    """Display directory tree structure.

    Shows an ASCII tree visualization of the directory structure.

    Args:
        path: Root directory (default: current directory)
        max_depth: Maximum depth to display (default: 3)
        include_hidden: Include hidden files (default: False)

    Returns:
        ASCII tree visualization

    Example:
        file.tree()
        file.tree(path="src", max_depth=2)
        file.tree(path=".", include_hidden=True)
    """
    with LogSpan(span="file.tree", path=path, maxDepth=max_depth) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        if not resolved.is_dir():
            s.add(error="not_a_directory")
            return f"Error: Not a directory: {path}"

        cfg = _get_file_config()
        node_count = 0
        max_nodes = cfg.max_list_entries

        def build_tree(dir_path: Path, prefix: str, depth: int) -> List[str]:  # noqa: UP006
            nonlocal node_count

            if depth > max_depth or node_count >= max_nodes:
                return []

            lines = []
            try:
                # Filter first, then sort (P4 fix - more efficient)
                filtered = [
                    entry
                    for entry in dir_path.iterdir()
                    if (include_hidden or not entry.name.startswith("."))
                    and not _is_excluded(entry, cfg.exclude_patterns)
                ]
                filtered.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return [f"{prefix}[permission denied]"]

            for i, entry in enumerate(filtered):
                if node_count >= max_nodes:
                    lines.append(f"{prefix}... (truncated)")
                    break

                node_count += 1
                is_last = i == len(filtered) - 1
                connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
                name = entry.name + ("/" if entry.is_dir() else "")

                lines.append(f"{prefix}{connector}{name}")

                if entry.is_dir() and depth < max_depth:
                    extension = "    " if is_last else "\u2502   "
                    lines.extend(build_tree(entry, prefix + extension, depth + 1))

            return lines

        result_lines = [str(resolved.name) + "/"]
        result_lines.extend(build_tree(resolved, "", 1))

        s.add(nodeCount=node_count)
        return "\n".join(result_lines)


def search(
    *,
    path: str = ".",
    pattern: str,
    file_pattern: str | None = None,
    case_sensitive: bool = False,
    max_results: int = 100,
) -> str:
    """Search for files by name pattern.

    Recursively searches for files matching the given pattern.
    Supports glob patterns and optional file type filtering.

    Args:
        path: Root directory to search (default: current directory)
        pattern: Search pattern (glob-style, e.g., "*.py", "*test*")
        file_pattern: Filter by file extension (e.g., "*.py", "*.md")
        case_sensitive: If True, pattern matching is case-sensitive (default: False)
        max_results: Maximum number of results to return (default: 100)

    Returns:
        List of matching files with path and size

    Example:
        file.search(pattern="*test*")
        file.search(pattern="config", file_pattern="*.yaml")
        file.search(path="src", pattern="*handler*", file_pattern="*.py")
    """
    with LogSpan(
        span="file.search", path=path, pattern=pattern, filePattern=file_pattern
    ) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        if not resolved.is_dir():
            s.add(error="not_a_directory")
            return f"Error: Not a directory: {path}"

        cfg = _get_file_config()
        results: List[tuple[str, int]] = []  # noqa: UP006

        # Normalize pattern for case-insensitive matching
        search_pattern = pattern if case_sensitive else pattern.lower()

        try:
            for entry in resolved.rglob("*"):
                if len(results) >= max_results:
                    break

                # Skip directories
                if entry.is_dir():
                    continue

                # Skip hidden files
                if entry.name.startswith("."):
                    continue

                # Skip excluded patterns
                if _is_excluded(entry, cfg.exclude_patterns):
                    continue

                # Apply file pattern filter if specified
                if file_pattern and not fnmatch.fnmatch(entry.name, file_pattern):
                    continue

                # Match against search pattern (glob or substring)
                name_to_match = entry.name if case_sensitive else entry.name.lower()
                pattern_core = search_pattern.replace("*", "")
                if (
                    not fnmatch.fnmatch(name_to_match, search_pattern)
                    and pattern_core not in name_to_match
                ):
                    continue

                # Get relative path and size
                try:
                    entry_rel = entry.relative_to(resolved)
                    entry_size = entry.stat().st_size
                except (ValueError, OSError):
                    continue

                results.append((str(entry_rel), entry_size))

            # Sort by path
            results.sort(key=lambda x: x[0].lower())

            # Format output
            if not results:
                s.add(resultCount=0)
                return f"No files matching '{pattern}' found in {path}"

            lines = []
            for rel_path, size in results:
                size_str = _format_size(size)
                lines.append(f"{rel_path} ({size_str})")

            if len(results) >= max_results:
                lines.append(f"\n... (limited to {max_results} results)")

            s.add(resultCount=len(results))
            return "\n".join(lines)

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


# ============================================================================
# Write Operations
# ============================================================================


def write(
    *,
    path: str,
    content: str,
    append: bool = False,
    create_dirs: bool = False,
) -> str:
    """Write content to a file.

    Creates the file if it doesn't exist. Optionally creates parent
    directories and can append to existing files.

    Args:
        path: Path to file
        content: Content to write
        append: If True, append to file (default: overwrite)
        create_dirs: If True, create parent directories (default: False)

    Returns:
        Success message with bytes written, or error message

    Example:
        file.write(path="output.txt", content="Hello, World!")
        file.write(path="log.txt", content="New entry\\n", append=True)
        file.write(path="new/dir/file.txt", content="data", create_dirs=True)
    """
    with LogSpan(
        span="file.write", path=path, append=append, contentLen=len(content)
    ) as s:
        # For new files, validate parent directory
        resolved, error = _validate_path(path, must_exist=False)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        # Check parent directory
        parent = resolved.parent
        if not parent.exists():
            if create_dirs:
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    s.add(error=f"mkdir_failed: {e}")
                    return f"Error: Could not create directory: {e}"
            else:
                s.add(error="parent_not_found")
                return f"Error: Parent directory does not exist: {parent}. Use create_dirs=True to create it."

        # Create backup if file exists
        if resolved.exists():
            backup_error = _create_backup(resolved)
            if backup_error:
                s.add(error=f"backup_failed: {backup_error}")
                return f"Error: {backup_error}"

        try:
            # Encode once for byte count (P5 fix - avoid double encoding)
            content_bytes = content.encode("utf-8")
            bytes_written = len(content_bytes)

            # Use atomic write for non-append operations
            if append:
                with resolved.open("ab") as f:
                    f.write(content_bytes)
            else:
                # Write to temp file then rename (atomic)
                fd, temp_path = tempfile.mkstemp(
                    dir=str(parent),
                    prefix=".tmp_",
                    suffix=resolved.suffix,
                )
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(content_bytes)
                    # Preserve permissions if file exists
                    if resolved.exists():
                        shutil.copymode(str(resolved), temp_path)
                    Path(temp_path).replace(resolved)
                except Exception:
                    # Clean up temp file on error
                    temp = Path(temp_path)
                    if temp.exists():
                        temp.unlink()
                    raise

            action = "appended" if append else "wrote"
            s.add(written=True, bytesWritten=bytes_written)
            return f"OK: {action} {bytes_written} bytes to {path}"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def edit(
    *,
    path: str,
    old_text: str,
    new_text: str,
    occurrence: int = 1,
) -> str:
    """Edit a file by replacing text.

    Performs exact string replacement. By default replaces the first
    occurrence. Errors if old_text appears multiple times and occurrence
    is not specified.

    Args:
        path: Path to file
        old_text: Exact text to find and replace
        new_text: Text to replace with
        occurrence: Which occurrence to replace (1=first, 0=all, default: 1)

    Returns:
        Success message showing replacement count, or error message

    Example:
        file.edit(path="config.py", old_text="DEBUG = False", new_text="DEBUG = True")
        file.edit(path="main.py", old_text="TODO", new_text="DONE", occurrence=0)
    """
    with LogSpan(
        span="file.edit", path=path, oldLen=len(old_text), newLen=len(new_text)
    ) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        if not resolved.is_file():
            s.add(error="not_a_file")
            return f"Error: Not a file: {path}"

        if not old_text:
            s.add(error="empty_old_text")
            return "Error: old_text cannot be empty"

        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            s.add(error="encoding_error")
            return f"Error: Could not read file as UTF-8: {e}"
        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"

        # Count occurrences
        count = content.count(old_text)

        if count == 0:
            s.add(error="not_found")
            return "Error: Text not found in file"

        if count > 1 and occurrence == 1:
            s.add(error="ambiguous")
            return f"Error: Found {count} occurrences. Use occurrence=0 to replace all, or specify which (1-{count})."

        if occurrence > count:
            s.add(error="occurrence_out_of_range")
            return f"Error: Requested occurrence {occurrence} but only found {count}"

        # Create backup
        backup_error = _create_backup(resolved)
        if backup_error:
            s.add(error=f"backup_failed: {backup_error}")
            return f"Error: {backup_error}"

        # Perform replacement
        if occurrence == 0:
            # Replace all
            new_content = content.replace(old_text, new_text)
            replaced_count = count
        else:
            # Replace specific occurrence
            parts = content.split(old_text)
            if occurrence <= len(parts) - 1:
                # Join with old_text except at the target position
                new_parts = []
                for i, part in enumerate(parts):
                    new_parts.append(part)
                    if i < len(parts) - 1:
                        if i == occurrence - 1:
                            new_parts.append(new_text)
                        else:
                            new_parts.append(old_text)
                new_content = "".join(new_parts)
                replaced_count = 1
            else:
                s.add(error="occurrence_out_of_range")
                return f"Error: Could not find occurrence {occurrence}"

        try:
            # Write using atomic operation
            fd, temp_path = tempfile.mkstemp(
                dir=str(resolved.parent),
                prefix=".tmp_",
                suffix=resolved.suffix,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(new_content)
                shutil.copymode(str(resolved), temp_path)
                Path(temp_path).replace(resolved)
            except Exception:
                temp = Path(temp_path)
                if temp.exists():
                    temp.unlink()
                raise

            s.add(edited=True, replacements=replaced_count)
            return f"OK: Replaced {replaced_count} occurrence(s) in {path}"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


# ============================================================================
# File Management
# ============================================================================


def delete(*, path: str, backup: bool = True) -> str:
    """Delete a file or empty directory.

    By default creates a backup before deletion. If send2trash is
    available and use_trash is enabled, moves to trash instead.

    Args:
        path: Path to file or directory
        backup: If True, create backup before delete (default: True)

    Returns:
        Success message or error message

    Example:
        file.delete(path="temp.txt")
        file.delete(path="old_file.py", backup=False)
    """
    with LogSpan(span="file.delete", path=path) as s:
        resolved, error = _validate_path(path, must_exist=True)
        if error:
            s.add(error=error)
            return f"Error: {error}"
        assert resolved is not None  # mypy: error check above ensures this

        cfg = _get_file_config()

        try:
            # Create backup if requested and it's a file
            if backup and resolved.is_file():
                backup_error = _create_backup(resolved)
                if backup_error:
                    s.add(error=f"backup_failed: {backup_error}")
                    return f"Error: {backup_error}"

            # Use send2trash if available and configured
            if cfg.use_trash and HAS_SEND2TRASH:
                send2trash.send2trash(str(resolved))
                s.add(deleted=True, method="trash")
                return f"OK: Moved to trash: {path}"

            # Standard deletion
            if resolved.is_file() or resolved.is_symlink():
                resolved.unlink()
            elif resolved.is_dir():
                # Only delete empty directories
                if any(resolved.iterdir()):
                    s.add(error="directory_not_empty")
                    return f"Error: Directory not empty: {path}"
                resolved.rmdir()
            else:
                s.add(error="unknown_type")
                return f"Error: Cannot delete: {path}"

            s.add(deleted=True, method="unlink")
            return f"OK: Deleted: {path}"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def copy(*, source: str, dest: str) -> str:
    """Copy a file or directory.

    For files, copies content and metadata. For directories, copies
    the entire tree recursively.

    Args:
        source: Source path
        dest: Destination path

    Returns:
        Success message or error message

    Example:
        file.copy(source="config.yaml", dest="config.backup.yaml")
        file.copy(source="src/", dest="src_backup/")
    """
    with LogSpan(span="file.copy", source=source, dest=dest) as s:
        src_resolved, error = _validate_path(source, must_exist=True)
        if error:
            s.add(error=f"source: {error}")
            return f"Error: {error}"
        assert src_resolved is not None  # mypy: error check above ensures this

        dest_resolved, error = _validate_path(dest, must_exist=False)
        if error:
            s.add(error=f"dest: {error}")
            return f"Error: {error}"
        assert dest_resolved is not None  # mypy: error check above ensures this

        try:
            if src_resolved.is_file():
                # Copy file with metadata
                shutil.copy2(src_resolved, dest_resolved)
                s.add(copied=True, type="file")
                return f"OK: Copied file: {source} -> {dest}"
            elif src_resolved.is_dir():
                # Copy directory tree
                if dest_resolved.exists():
                    s.add(error="dest_exists")
                    return f"Error: Destination already exists: {dest}"
                # S3 fix: Copy symlink targets (not symlinks) to prevent
                # copying links that point outside allowed directories
                shutil.copytree(src_resolved, dest_resolved, symlinks=False)
                s.add(copied=True, type="directory")
                return f"OK: Copied directory: {source} -> {dest}"
            else:
                s.add(error="unknown_type")
                return f"Error: Cannot copy: {source}"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"


def move(*, source: str, dest: str) -> str:
    """Move or rename a file or directory.

    Moves source to destination. Can be used for renaming files
    within the same directory.

    Args:
        source: Source path
        dest: Destination path

    Returns:
        Success message or error message

    Example:
        file.move(source="old_name.py", dest="new_name.py")
        file.move(source="file.txt", dest="archive/file.txt")
    """
    with LogSpan(span="file.move", source=source, dest=dest) as s:
        src_resolved, error = _validate_path(source, must_exist=True)
        if error:
            s.add(error=f"source: {error}")
            return f"Error: {error}"
        assert src_resolved is not None  # mypy: error check above ensures this

        dest_resolved, error = _validate_path(dest, must_exist=False)
        if error:
            s.add(error=f"dest: {error}")
            return f"Error: {error}"
        assert dest_resolved is not None  # mypy: error check above ensures this

        # Check destination parent exists
        if not dest_resolved.parent.exists():
            s.add(error="dest_parent_not_found")
            return (
                f"Error: Destination directory does not exist: {dest_resolved.parent}"
            )

        # Determine type before move (source won't exist after)
        src_type = "file" if src_resolved.is_file() else "directory"

        try:
            shutil.move(str(src_resolved), str(dest_resolved))
            s.add(moved=True, type=src_type)
            return f"OK: Moved: {source} -> {dest}"

        except OSError as e:
            s.add(error=str(e))
            return f"Error: {e}"
