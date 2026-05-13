"""Backend-neutral large output result-store types and accessors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ot.services import ResultStoreBackend, get_services


@dataclass
class StoredResult:
    """Result from storing large output."""

    handle: str
    total_lines: int
    size_bytes: int
    summary: str
    preview: str
    status: str = "ready"
    content_type: str = "text"

    def to_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for MCP response."""
        return {
            "handle": self.handle,
            "total_lines": self.total_lines,
            "size_bytes": self.size_bytes,
            "summary": self.summary,
            "preview": self.preview,
            "status": self.status,
            "content_type": self.content_type,
        }


@dataclass
class QueryResult:
    """Result from querying stored output."""

    content: str
    total_lines: int
    returned: int
    offset: int
    has_more: bool
    handle: str = ""
    limit: int = 100
    total_size_bytes: int = 0
    next_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response."""
        end = self.offset + self.returned - 1
        pct = int((end / self.total_lines) * 100) if self.total_lines > 0 else 100
        result: dict[str, Any] = {
            "content": self.content,
            "total_lines": self.total_lines,
            "returned": self.returned,
            "offset": self.offset,
            "has_more": self.has_more,
            "progress": f"lines {self.offset}-{end} of {self.total_lines} ({pct}%)",
            "total_size_bytes": self.total_size_bytes,
        }
        if self.next_query:
            result["next_query"] = self.next_query
        elif self.has_more and self.handle:
            next_offset = self.offset + self.returned
            result["next_query"] = (
                f"ot.result(handle='{self.handle}', offset={next_offset}, limit={self.limit})"
            )
        return result


class ResultStore:
    """Compatibility wrapper over the registered result-store backend."""

    def _backend(self) -> ResultStoreBackend:
        from ot.ctx.result_backend import CtxResultStoreBackend

        backend = get_services().result_store_backend
        if backend is not None and backend is not self:
            return backend
        return CtxResultStoreBackend()

    def store(
        self,
        content: str,
        *,
        tool: str = "",
        preview_lines: int | None = None,
    ) -> Any:
        """Store content through the active backend."""
        return self._backend().store(content, tool=tool, preview_lines=preview_lines)

    def query(
        self,
        handle: str,
        *,
        offset: int = 1,
        limit: int = 100,
        search: str = "",
        fuzzy: bool = False,
        tail: int = 0,
        context: int = 0,
    ) -> Any:
        """Query content through the active backend."""
        return self._backend().query(
            handle,
            offset=offset,
            limit=limit,
            search=search,
            fuzzy=fuzzy,
            tail=tail,
            context=context,
        )

    def cleanup(self) -> int:
        """Clean expired content through the active backend."""
        return self._backend().cleanup()

    def format_store_response(self, stored: Any) -> dict[str, Any]:
        """Format stored-result metadata through the active backend."""
        return self._backend().format_store_response(stored)


def get_result_store() -> ResultStoreBackend:
    """Return the registered result-store backend."""
    backend = get_services().result_store_backend
    if backend is None:
        # ctx is the built-in result backend for large outputs. The dependency is
        # isolated here so executor callers target the backend-neutral interface.
        backend = ResultStore()
        get_services().register_result_store(backend)
    return backend
