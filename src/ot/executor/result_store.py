"""Large output result store for OneTool.

Stores tool outputs exceeding max_inline_size to disk and provides
a query API for paginated retrieval.

Storage format:
    .onetool/tmp/
    ├── result-{guid}.meta.json    # Always present
    ├── result-{guid}.jsonl        # Structured data (many short lines)
    └── result-{guid}.txt          # Unstructured data (prose, HTML)
"""

from __future__ import annotations

import difflib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ot.config import get_config

StorageFormat = Literal["jsonl", "txt"]


@dataclass
class ResultMeta:
    """Metadata for a stored result."""

    handle: str
    format: StorageFormat
    total_lines: int
    size_bytes: int
    created_at: str
    tool: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "handle": self.handle,
            "format": self.format,
            "total_lines": self.total_lines,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "tool": self.tool,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResultMeta:
        """Create from dictionary."""
        return cls(
            handle=data["handle"],
            format=data["format"],
            total_lines=data["total_lines"],
            size_bytes=data["size_bytes"],
            created_at=data["created_at"],
            tool=data.get("tool", ""),
        )


@dataclass
class StoredResult:
    """Result from storing large output."""

    handle: str
    format: StorageFormat
    total_lines: int
    size_bytes: int
    summary: str
    preview: list[str]
    query: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for MCP response."""
        return {
            "handle": self.handle,
            "format": self.format,
            "total_lines": self.total_lines,
            "size_bytes": self.size_bytes,
            "summary": self.summary,
            "preview": self.preview,
            "query": self.query,
        }


@dataclass
class QueryResult:
    """Result from querying stored output."""

    lines: list[str]
    total_lines: int
    returned: int
    offset: int
    has_more: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "lines": self.lines,
            "total_lines": self.total_lines,
            "returned": self.returned,
            "offset": self.offset,
            "has_more": self.has_more,
        }


@dataclass
class ResultStore:
    """Manages storage and retrieval of large tool outputs."""

    store_dir: Path = field(default_factory=lambda: _get_default_store_dir())

    def __post_init__(self) -> None:
        """Ensure store directory exists."""
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: str,
        *,
        tool: str = "",
        preview_lines: int | None = None,
    ) -> StoredResult:
        """Store large output to disk.

        Auto-detects format based on content structure:
        - jsonl: Many short lines of uniform structure
        - txt: Prose, HTML, or long lines

        Args:
            content: The output content to store
            tool: Name of the tool that generated this output
            preview_lines: Number of preview lines (default from config)

        Returns:
            StoredResult with handle and summary
        """
        # Clean up expired results opportunistically
        self.cleanup()

        # Generate unique handle
        handle = uuid.uuid4().hex[:12]

        # Detect format
        format_type = self._detect_format(content)

        # Split into lines
        lines = content.splitlines()
        total_lines = len(lines)
        size_bytes = len(content.encode("utf-8"))

        # Write content file
        ext = format_type
        content_path = self.store_dir / f"result-{handle}.{ext}"
        content_path.write_text(content, encoding="utf-8")

        # Create and write meta file
        meta = ResultMeta(
            handle=handle,
            format=format_type,
            total_lines=total_lines,
            size_bytes=size_bytes,
            created_at=datetime.now(UTC).isoformat(),
            tool=tool,
        )
        meta_path = self.store_dir / f"result-{handle}.meta.json"
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

        # Generate summary
        summary = self._generate_summary(lines, tool)

        # Get preview lines from config if not specified
        if preview_lines is None:
            config = get_config()
            preview_lines = config.output.preview_lines

        preview = lines[:preview_lines]

        return StoredResult(
            handle=handle,
            format=format_type,
            total_lines=total_lines,
            size_bytes=size_bytes,
            summary=summary,
            preview=preview,
            query=f"ot.result(handle='{handle}', offset=1, limit=50)",
        )

    def query(
        self,
        handle: str,
        *,
        offset: int = 1,
        limit: int = 100,
        search: str = "",
        fuzzy: bool = False,
    ) -> QueryResult:
        """Query stored result with pagination and optional filtering.

        Args:
            handle: The result handle from store()
            offset: Starting line number (1-indexed, matching Claude's Read tool)
            limit: Maximum lines to return
            search: Regex pattern to filter lines (optional)
            fuzzy: Use fuzzy matching instead of regex (optional)

        Returns:
            QueryResult with matching lines

        Raises:
            ValueError: If handle not found or expired
        """
        # Normalize offset (0 treated as 1)
        if offset < 1:
            offset = 1

        # Find and load meta file
        meta = self._load_meta(handle)
        if meta is None:
            raise ValueError(f"Result not found: {handle}")

        # Check TTL
        if self._is_expired(meta):
            # Clean up expired file
            self._delete_result(handle, meta.format)
            raise ValueError(f"Result expired: {handle}")

        # Load content
        content_path = self.store_dir / f"result-{handle}.{meta.format}"
        if not content_path.exists():
            raise ValueError(f"Result file missing: {handle}")

        content = content_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Apply search filter if provided
        if search:
            if fuzzy:
                lines = self._fuzzy_filter(lines, search)
            else:
                try:
                    pattern = re.compile(search, re.IGNORECASE)
                    lines = [line for line in lines if pattern.search(line)]
                except re.error as e:
                    raise ValueError(f"Invalid search pattern: {e}") from e

        total_lines = len(lines)

        # Apply offset/limit (1-indexed)
        start_idx = offset - 1
        end_idx = start_idx + limit
        result_lines = lines[start_idx:end_idx]

        return QueryResult(
            lines=result_lines,
            total_lines=total_lines,
            returned=len(result_lines),
            offset=offset,
            has_more=end_idx < total_lines,
        )

    def cleanup(self) -> int:
        """Remove expired result files.

        Returns:
            Number of files cleaned up
        """
        cleaned = 0
        for meta_path in self.store_dir.glob("result-*.meta.json"):
            try:
                meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                meta = ResultMeta.from_dict(meta_data)

                if self._is_expired(meta):
                    self._delete_result(meta.handle, meta.format)
                    cleaned += 1
            except (json.JSONDecodeError, KeyError, OSError):
                # Invalid meta file - try to clean up
                handle = meta_path.stem.replace("result-", "").replace(".meta", "")
                for ext in ["jsonl", "txt"]:
                    content_path = self.store_dir / f"result-{handle}.{ext}"
                    if content_path.exists():
                        content_path.unlink()
                meta_path.unlink()
                cleaned += 1

        return cleaned

    def _detect_format(self, content: str) -> StorageFormat:
        """Auto-detect storage format based on content structure.

        Returns jsonl for:
        - Many lines (>5)
        - Short average line length (<200 chars)
        - Lines that look like structured data

        Returns txt for:
        - Single blob or few lines
        - Long lines (prose, HTML)
        """
        lines = content.splitlines()

        if len(lines) < 5:
            return "txt"

        # Check average line length
        total_length = sum(len(line) for line in lines)
        avg_length = total_length / len(lines) if lines else 0

        if avg_length > 200:
            return "txt"

        # Check if lines look structured (similar lengths, common prefixes)
        lengths = [len(line) for line in lines[:20]]
        if lengths:
            variance = sum((length - avg_length) ** 2 for length in lengths) / len(lengths)
            # Low variance suggests uniform structure
            if variance < 2000:
                return "jsonl"

        return "txt"

    def _generate_summary(self, lines: list[str], tool: str) -> str:
        """Generate human-readable summary of stored content."""
        total = len(lines)

        if tool:
            return f"{total} lines from {tool}"

        return f"{total} lines stored"

    def _load_meta(self, handle: str) -> ResultMeta | None:
        """Load metadata for a result handle."""
        meta_path = self.store_dir / f"result-{handle}.meta.json"
        if not meta_path.exists():
            return None

        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return ResultMeta.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _is_expired(self, meta: ResultMeta) -> bool:
        """Check if a result has exceeded TTL."""
        config = get_config()
        ttl = config.output.result_ttl

        if ttl <= 0:
            return False  # No expiry

        created = datetime.fromisoformat(meta.created_at)
        age = datetime.now(UTC) - created

        return age.total_seconds() > ttl

    def _delete_result(self, handle: str, format_type: StorageFormat) -> None:
        """Delete result files for a handle."""
        content_path = self.store_dir / f"result-{handle}.{format_type}"
        meta_path = self.store_dir / f"result-{handle}.meta.json"

        if content_path.exists():
            content_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    def _fuzzy_filter(self, lines: list[str], query: str) -> list[str]:
        """Filter lines using fuzzy matching, sorted by match score."""
        scored = []
        query_lower = query.lower()

        for line in lines:
            # Use SequenceMatcher for fuzzy matching
            ratio = difflib.SequenceMatcher(
                None, query_lower, line.lower()
            ).ratio()
            if ratio > 0.3:  # Threshold for fuzzy match
                scored.append((ratio, line))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [line for _, line in scored]


def _get_default_store_dir() -> Path:
    """Get default store directory from config."""
    config = get_config()
    return config.get_result_store_path()


# Global singleton instance
_store: ResultStore | None = None


def get_result_store() -> ResultStore:
    """Get or create the global result store instance."""
    global _store
    if _store is None:
        _store = ResultStore()
    return _store
