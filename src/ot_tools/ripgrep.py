"""Ripgrep text search tools.

Provides fast text and regex search in files using ripgrep (rg).
Requires the `rg` binary in PATH (install with: brew install ripgrep).

Inspired by mcp-ripgrep (https://github.com/mcollina/mcp-ripgrep)
by Matteo Collina, licensed under MIT.
"""

from __future__ import annotations

# Pack for dot notation: ripgrep.search(), ripgrep.count(), etc.
pack = "ripgrep"

__all__ = ["count", "files", "search", "types"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "cli": [("rg", "brew install ripgrep")],
}

import contextlib
import shutil
import subprocess
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path

from ot.config import get_tool_config
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path
from ot.utils.platform import get_install_hint


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Command timeout in seconds",
    )
    relative_paths: bool = Field(
        default=True,
        description="Output relative paths instead of absolute paths",
    )


def _resolve_path(path: str) -> Path:
    """Resolve a search path relative to project directory.

    Uses SDK resolve_cwd_path() for consistent path resolution.

    Path resolution follows project conventions:
        - Relative paths: resolved relative to project directory (OT_CWD)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory
        - Prefixed paths (CWD/, GLOBAL/, OT_DIR/): resolved to respective dirs

    Args:
        path: Path string (can contain ~ or prefixes)

    Returns:
        Resolved absolute Path
    """
    return resolve_cwd_path(path)


def _to_relative_output(output: str, base_path: Path) -> str:
    """Convert absolute paths in ripgrep output to relative paths.

    Args:
        output: Raw ripgrep output with absolute paths
        base_path: Base path to make paths relative to

    Returns:
        Output with paths converted to relative
    """
    cfg = get_tool_config("ripgrep", Config)
    if not cfg.relative_paths:
        return output

    base_str = str(base_path)
    lines = []
    for line in output.split("\n"):
        if line.startswith(base_str):
            # Convert absolute path to relative
            rel_line = line[len(base_str) :].lstrip("/\\")
            lines.append(rel_line)
        else:
            lines.append(line)
    return "\n".join(lines)


def _check_rg_installed() -> str | None:
    """Check if ripgrep is installed.

    Returns:
        None if installed, error message if not.
    """
    if shutil.which("rg") is None:
        return f"Error: ripgrep (rg) is not installed. {get_install_hint('rg')}"
    return None


def _run_rg(
    args: list[str], cwd: str | None = None, timeout: float | None = None
) -> tuple[bool, str]:
    """Run ripgrep with the given arguments.

    Args:
        args: Command line arguments for rg
        cwd: Working directory for the command
        timeout: Command timeout in seconds (defaults to config)

    Returns:
        Tuple of (success, output). If success is False, output contains error message.
    """
    if timeout is None:
        timeout = get_tool_config("ripgrep", Config).timeout

    with LogSpan(span="ripgrep.exec", args=args[:3] if len(args) > 3 else args) as span:
        try:
            result = subprocess.run(
                ["rg", *args],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )

            # rg returns 1 for no matches (not an error), 2 for actual errors
            if result.returncode == 2:
                error_msg = result.stderr.strip() or "Unknown ripgrep error"
                span.add(returncode=2, error=error_msg)
                # Improve error message for common patterns
                if "regex parse error" in error_msg:
                    return False, f"Error: Invalid regex pattern\n{error_msg}"
                return False, f"Error: {error_msg}"

            span.add(returncode=result.returncode, outputLen=len(result.stdout))
            return True, result.stdout

        except subprocess.TimeoutExpired:
            span.add(error="timeout")
            return False, f"Error: Search timed out after {timeout} seconds"
        except FileNotFoundError:
            span.add(error="not_installed")
            return (
                False,
                f"Error: ripgrep (rg) is not installed. {get_install_hint('rg')}",
            )
        except Exception as e:
            span.add(error=str(e))
            return False, f"Error: {e}"


def search(
    *,
    pattern: str,
    path: str = ".",
    case_sensitive: bool = True,
    fixed_strings: bool = False,
    file_type: str | None = None,
    glob: str | None = None,
    context: int = 0,
    before_context: int = 0,
    after_context: int = 0,
    max_per_file: int | None = None,
    limit: int | None = None,
    word_match: bool = False,
    include_hidden: bool = False,
    invert_match: bool = False,
    multiline: bool = False,
    only_matching: bool = False,
    no_ignore: bool = False,
    heading: bool = False,
) -> str:
    """Search files for patterns using ripgrep.

    Performs fast text/regex search across files. Returns matching lines
    with file paths and line numbers.

    Args:
        pattern: The regex or literal pattern to search for
        path: Directory or file to search in (default: current directory)
        case_sensitive: Match case-sensitively (default: True)
        fixed_strings: Treat pattern as literal string, not regex (default: False)
        file_type: Search only files of this type (e.g., "py", "js", "ts")
        glob: Search only files matching this glob pattern. Note: glob is applied
            relative to `path`. Use `glob="**/*.py"` with `path="."` for absolute
            patterns, or `glob="*.py"` with `path="src/"` for relative patterns.
        context: Number of lines to show before and after each match
        before_context: Number of lines to show before each match (overrides context)
        after_context: Number of lines to show after each match (overrides context)
        max_per_file: Maximum matches per file (passed to rg --max-count)
        limit: Maximum total matching lines to return (post-processed)
        word_match: Match whole words only (default: False)
        include_hidden: Search hidden files and directories (default: False)
        invert_match: Return lines NOT matching the pattern (default: False)
        multiline: Match patterns spanning multiple lines (default: False)
        only_matching: Show only the matched text, not the full line (default: False)
        no_ignore: Don't respect .gitignore files (default: False)
        heading: Group matches by file with headings (default: False)

    Returns:
        Matching lines with file paths and line numbers, or error message.

    Example:
        # Basic search
        ripgrep.search(pattern="TODO", path="src/")

        # Case insensitive search in Python files
        ripgrep.search(pattern="error", path=".", case_sensitive=False, file_type="py")

        # Fixed string search (pattern with special chars)
        ripgrep.search(pattern="[test]", path=".", fixed_strings=True)

        # Search with context
        ripgrep.search(pattern="def main", path=".", context=3, limit=5)

        # Glob patterns are relative to path
        ripgrep.search(pattern="TODO", glob="**/*.py", path=".")  # All .py files
        ripgrep.search(pattern="TODO", glob="*.py", path="src/")  # Only src/*.py

        # Find lines NOT containing a pattern
        ripgrep.search(pattern="import", path=".", invert_match=True, file_type="py")

        # Multiline patterns
        ripgrep.search(pattern="def.*\\n.*return", path=".", multiline=True)
    """
    with LogSpan(span="ripgrep.search", pattern=pattern, path=path) as s:
        # Check rg is installed
        error = _check_rg_installed()
        if error:
            s.add("error", "not_installed")
            return error

        # Resolve path relative to effective cwd
        search_path = _resolve_path(path)
        if not search_path.exists():
            s.add("error", "invalid_path")
            return f"Error: Path does not exist: {search_path}"

        # Build arguments
        args = ["--line-number", "--with-filename"]

        if not case_sensitive:
            args.append("--ignore-case")

        if fixed_strings:
            args.append("--fixed-strings")

        if file_type:
            args.extend(["--type", file_type])

        if glob:
            args.extend(["--glob", glob])

        # Context options: specific before/after take precedence over general context
        if before_context > 0:
            args.extend(["-B", str(before_context)])
        if after_context > 0:
            args.extend(["-A", str(after_context)])
        if context > 0 and before_context == 0 and after_context == 0:
            args.extend(["--context", str(context)])

        if max_per_file:
            args.extend(["--max-count", str(max_per_file)])

        if word_match:
            args.append("--word-regexp")

        if include_hidden:
            args.append("--hidden")

        if invert_match:
            args.append("--invert-match")

        if multiline:
            args.append("--multiline")

        if only_matching:
            args.append("--only-matching")

        if no_ignore:
            args.append("--no-ignore")

        if heading:
            args.append("--heading")

        args.extend([pattern, str(search_path)])

        success, output = _run_rg(args)

        if not success:
            s.add("error", output)
            return output

        if not output.strip():
            s.add("matchCount", 0)
            return "No matches found"

        # Convert to relative paths if configured
        result = _to_relative_output(output.strip(), search_path)

        # Apply total limit if specified (post-process)
        lines = result.split("\n")
        if limit and len(lines) > limit:
            result = "\n".join(lines[:limit])
            result += f"\n... ({len(lines) - limit} more matches truncated)"

        # Count matches
        match_count = min(len(lines), limit) if limit else len(lines)
        s.add("matchCount", match_count)

        return result


def count(
    *,
    pattern: str,
    path: str = ".",
    count_all: bool = False,
    file_type: str | None = None,
    glob: str | None = None,
    include_hidden: bool = False,
    no_ignore: bool = False,
) -> str:
    """Count pattern occurrences in files.

    Returns file paths with match counts per file.

    Args:
        pattern: The regex or literal pattern to count
        path: Directory or file to search in (default: current directory)
        count_all: Count all matches per line, not just matching lines (default: False)
        file_type: Count only in files of this type (e.g., "py", "js")
        glob: Count only in files matching this glob pattern. Note: glob is applied
            relative to `path`.
        include_hidden: Include hidden files and directories (default: False)
        no_ignore: Don't respect .gitignore files (default: False)

    Returns:
        File paths with match counts, or error message.

    Example:
        # Count TODOs in source files
        ripgrep.count(pattern="TODO", path="src/")

        # Count all imports (including multiple per line)
        ripgrep.count(pattern="import", path=".", count_all=True, file_type="py")

        # Count with glob patterns (relative to path)
        ripgrep.count(pattern="TODO", glob="**/*.py", path=".")
        ripgrep.count(pattern="import", glob="*.{js,ts}", path="src/")
    """
    with LogSpan(span="ripgrep.count", pattern=pattern, path=path) as s:
        # Check rg is installed
        error = _check_rg_installed()
        if error:
            s.add("error", "not_installed")
            return error

        # Resolve path relative to effective cwd
        search_path = _resolve_path(path)
        if not search_path.exists():
            s.add("error", "invalid_path")
            return f"Error: Path does not exist: {search_path}"

        # Build arguments
        args = ["--count"]

        if count_all:
            args.append("--count-matches")

        if file_type:
            args.extend(["--type", file_type])

        if glob:
            args.extend(["--glob", glob])

        if include_hidden:
            args.append("--hidden")

        if no_ignore:
            args.append("--no-ignore")

        args.extend([pattern, str(search_path)])

        success, output = _run_rg(args)

        if not success:
            s.add("error", output)
            return output

        if not output.strip():
            s.add("matchCount", 0)
            return "No matches found"

        # Convert to relative paths if configured
        result = _to_relative_output(output.strip(), search_path)

        # Sum total matches
        total = 0
        for line in result.split("\n"):
            if ":" in line:
                with contextlib.suppress(ValueError):
                    total += int(line.split(":")[-1])

        s.add("totalCount", total)
        s.add("fileCount", len(result.split("\n")))

        return result


def files(
    *,
    path: str = ".",
    file_type: str | None = None,
    glob: str | None = None,
    include_hidden: bool = False,
    no_ignore: bool = False,
    sort: str | None = None,
) -> str:
    """List files that would be searched.

    Returns a list of file paths that ripgrep would search based on filters.

    Args:
        path: Directory to list files in (default: current directory)
        file_type: List only files of this type (e.g., "py", "js")
        glob: List only files matching this glob pattern. Note: glob is applied
            relative to `path`.
        include_hidden: Include hidden files and directories (default: False)
        no_ignore: Don't respect .gitignore files (default: False)
        sort: Sort files by: "path", "modified", "accessed", or "created"

    Returns:
        List of file paths, one per line.

    Example:
        # List all Python files
        ripgrep.files(path="src/", file_type="py")

        # List markdown files
        ripgrep.files(path=".", glob="*.md")

        # Glob patterns are relative to path
        ripgrep.files(glob="**/*.py", path=".")         # All .py files from root
        ripgrep.files(glob="test_*.py", path="tests/")  # Test files in tests/

        # List files sorted by modification time
        ripgrep.files(path="src/", file_type="py", sort="modified")

        # Include files normally ignored by .gitignore
        ripgrep.files(path=".", no_ignore=True)
    """
    with LogSpan(span="ripgrep.files", path=path) as s:
        # Check rg is installed
        error = _check_rg_installed()
        if error:
            s.add("error", "not_installed")
            return error

        # Resolve path relative to effective cwd
        search_path = _resolve_path(path)
        if not search_path.exists():
            s.add("error", "invalid_path")
            return f"Error: Path does not exist: {search_path}"

        # Build arguments
        args = ["--files"]

        if file_type:
            args.extend(["--type", file_type])

        if glob:
            args.extend(["--glob", glob])

        if include_hidden:
            args.append("--hidden")

        if no_ignore:
            args.append("--no-ignore")

        if sort:
            args.extend(["--sort", sort])

        args.append(str(search_path))

        success, output = _run_rg(args)

        if not success:
            s.add("error", output)
            return output

        if not output.strip():
            s.add("fileCount", 0)
            return "No files found"

        # Convert to relative paths if configured
        result = _to_relative_output(output.strip(), search_path)

        file_count = len(result.split("\n"))
        s.add("fileCount", file_count)

        return result


def types() -> str:
    """List supported file types.

    Returns all file types that ripgrep recognizes, with their
    associated file extensions and patterns.

    Returns:
        List of file types with extensions.

    Example:
        # Show all supported types
        ripgrep.types()
    """
    with LogSpan(span="ripgrep.types") as s:
        # Check rg is installed
        error = _check_rg_installed()
        if error:
            s.add("error", "not_installed")
            return error

        success, output = _run_rg(["--type-list"])

        if not success:
            s.add("error", output)
            return output

        type_count = len(output.strip().split("\n"))
        s.add("typeCount", type_count)

        return output.strip()
