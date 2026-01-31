"""Shared utilities for document converters.

Provides diff-stable output formatting including:
- YAML frontmatter generation
- TOC generation with line ranges
- Hash-based image naming
- Whitespace normalisation
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from functools import lru_cache

_CHECKSUM_CACHE_MAX_SIZE = 100


@lru_cache(maxsize=_CHECKSUM_CACHE_MAX_SIZE)
def _compute_checksum_cached(
    path_str: str,
    mtime: float,  # noqa: ARG001 - used as cache key
    size: int,  # noqa: ARG001 - used as cache key
) -> str:
    """Cached checksum computation (thread-safe via lru_cache).

    Args:
        path_str: Resolved path string
        mtime: File modification time (for cache invalidation)
        size: File size in bytes (for cache invalidation)

    Returns:
        Checksum in format 'sha256:abc123...'
    """
    path = Path(path_str)
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def compute_file_checksum(path: Path) -> str:
    """Compute SHA256 checksum of a file (with thread-safe caching).

    Results are cached based on path+mtime+size to avoid redundant reads
    when the same file is processed multiple times.

    Args:
        path: Path to file

    Returns:
        Checksum in format 'sha256:abc123...'
    """
    stat = path.stat()
    return _compute_checksum_cached(str(path.resolve()), stat.st_mtime, stat.st_size)


def compute_image_hash(data: bytes) -> str:
    """Compute hash for image naming (first 8 chars of SHA256).

    Args:
        data: Image bytes

    Returns:
        8-character hex hash
    """
    return hashlib.sha256(data).hexdigest()[:8]


def save_image(data: bytes, images_dir: Path, content_type: str) -> Path:
    """Save image with hash-based naming for diff stability.

    Args:
        data: Image bytes
        images_dir: Directory to save image
        content_type: MIME content type (e.g., "image/png", "image/jpeg")

    Returns:
        Path to saved image file
    """
    # Determine extension from content type
    if "jpeg" in content_type or "jpg" in content_type:
        extension = "jpg"
    elif "png" in content_type:
        extension = "png"
    elif "gif" in content_type:
        extension = "gif"
    else:
        extension = "png"

    # Hash-based naming for diff stability
    img_hash = compute_image_hash(data)
    img_name = f"img_{img_hash}.{extension}"
    img_path = images_dir / img_name

    # Only write if not already extracted (dedup by hash)
    if not img_path.exists():
        images_dir.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(data)

    return img_path


def get_mtime_iso(path: Path) -> str:
    """Get file modification time as ISO 8601 string.

    Args:
        path: Path to file

    Returns:
        ISO 8601 timestamp with Z suffix
    """
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_frontmatter(
    *,
    source: str,
    converted: str,
    pages: int | str,
    checksum: str,
) -> str:
    """Generate YAML frontmatter for converted document.

    Args:
        source: Relative path to source file
        converted: ISO 8601 timestamp (source file mtime)
        pages: Page/slide/sheet count (may be prefixed with ~ for estimates)
        checksum: SHA256 hash of source file

    Returns:
        YAML frontmatter block including delimiters
    """
    return f"""---
source: {source}
converted: {converted}
pages: {pages}
checksum: {checksum}
---
"""


def generate_toc(
    headings: Sequence[tuple[int, str, int, int]],
    main_file: str,
    source: str,
    converted: str,
    pages: int | str,
    checksum: str,
) -> str:
    """Generate table of contents as a separate file with line ranges.

    Creates a TOC document with frontmatter and instructions for LLMs
    on how to use the line numbers to navigate the main document.

    Args:
        headings: List of (level, title, start_line, end_line) tuples
            Level 1 = H1, Level 2 = H2, etc.
        main_file: Filename of the main markdown file (for linking)
        source: Original source file path (for reference)
        converted: ISO 8601 timestamp (source file mtime)
        pages: Page/slide/sheet count (may be prefixed with ~ for estimates)
        checksum: SHA256 hash of source file

    Returns:
        Complete markdown TOC document with frontmatter
    """
    lines = [
        "---",
        f"source: {source}",
        f"converted: {converted}",
        f"pages: {pages}",
        f"checksum: {checksum}",
        "---",
        "",
        "# Table of Contents",
        "",
        f"**Document:** [{main_file}]({main_file})",
        "",
        "## How to Use This TOC",
        "",
        "Each entry shows `(lines <start>-<end>)` for the main document.",
        "To read a section efficiently:",
        "",
        "1. Find the section you need below",
        f"2. Use the line range to read only that portion of [{main_file}]({main_file})",
        "3. Line numbers are exact - no offset needed",
        "",
        "---",
        "",
        "## Contents",
        "",
    ]

    if not headings:
        lines.append("*No headings found in document.*")
    else:
        for level, title, start_line, end_line in headings:
            indent = "  " * (level - 1)
            # Create anchor linking to section in main file
            anchor = _slugify(title)
            lines.append(
                f"{indent}- [{title}]({main_file}#{anchor}) (lines {start_line}-{end_line})"
            )

    lines.append("")
    return "\n".join(lines)


def _slugify(text: str) -> str:
    """Convert text to URL-safe anchor.

    Args:
        text: Text to slugify

    Returns:
        Lowercase slug with hyphens
    """
    # Remove non-alphanumeric chars, replace spaces with hyphens
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")


def write_toc_file(
    headings: list[tuple[int, str, int, int]],
    output_dir: Path,
    stem: str,
    source: str,
    converted: str,
    pages: int | str,
    checksum: str,
) -> Path:
    """Write TOC to a separate file with frontmatter.

    Args:
        headings: List of (level, title, start_line, end_line) tuples
        output_dir: Directory for output files
        stem: Base filename (without extension)
        source: Original source file path
        converted: ISO 8601 timestamp (source file mtime)
        pages: Page/slide/sheet count (may be prefixed with ~ for estimates)
        checksum: SHA256 hash of source file

    Returns:
        Path to the written TOC file
    """
    main_file = f"{stem}.md"
    toc_content = generate_toc(headings, main_file, source, converted, pages, checksum)
    toc_path = output_dir / f"{stem}.toc.md"
    toc_path.write_text(toc_content, encoding="utf-8")
    return toc_path


def normalise_whitespace(content: str) -> str:
    """Normalise whitespace for diff-stable output.

    - Converts CRLF to LF
    - Removes trailing whitespace
    - Ensures consistent blank line spacing (max 2 consecutive)
    - Ensures single trailing newline

    Args:
        content: Raw content

    Returns:
        Normalised content
    """
    # Normalise line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in content.split("\n")]

    # Collapse multiple blank lines to max 2
    result_lines: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)

    # Join and ensure single trailing newline
    result = "\n".join(result_lines).rstrip("\n") + "\n"
    return result


class IncrementalWriter:
    """Write content incrementally to track line numbers.

    Buffers content and tracks line numbers for TOC generation.
    """

    def __init__(self) -> None:
        self._buffer = io.StringIO()
        self._line_count = 0
        self._headings: list[tuple[int, str, int, int]] = []
        self._current_heading: tuple[int, str, int] | None = None

    def write(self, text: str) -> None:
        """Write text to buffer."""
        self._buffer.write(text)
        self._line_count += text.count("\n")

    def write_heading(self, level: int, title: str) -> None:
        """Write a heading and track it for TOC.

        Args:
            level: Heading level (1-6)
            title: Heading text
        """
        # Close previous heading
        if self._current_heading:
            prev_level, prev_title, prev_start = self._current_heading
            self._headings.append((prev_level, prev_title, prev_start, self._line_count))

        # Start new heading
        heading_line = self._line_count + 1
        self._current_heading = (level, title, heading_line)

        # Write the heading
        prefix = "#" * level
        self.write(f"{prefix} {title}\n\n")

    def close_heading(self) -> None:
        """Close the current heading section."""
        if self._current_heading:
            prev_level, prev_title, prev_start = self._current_heading
            self._headings.append((prev_level, prev_title, prev_start, self._line_count))
            self._current_heading = None

    def get_content(self) -> str:
        """Get buffered content."""
        return self._buffer.getvalue()

    def get_headings(self) -> list[tuple[int, str, int, int]]:
        """Get collected headings for TOC generation."""
        # Close any open heading
        self.close_heading()
        return self._headings

    @property
    def line_count(self) -> int:
        """Current line count."""
        return self._line_count
