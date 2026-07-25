"""ctx-backed implementation of the generic result-store interface."""

from __future__ import annotations

from typing import Any

from ot.executor.result_store import QueryResult, StoredResult


class CtxResultStoreBackend:
    """Store large outputs in the immutable ctx record backend."""

    def store(
        self,
        content: str,
        *,
        tool: str = "",
        preview_lines: int | None = None,
    ) -> StoredResult:
        """Store content in ctx and return neutral metadata."""
        from ot.config import get_config
        from ot.ctx.write import ctx_write

        config_obj = get_config()
        if preview_lines is None:
            preview_lines = config_obj.output.preview_lines

        write_result = ctx_write(content, source=tool, verbose=True)
        lines = content.splitlines()
        raw_preview = lines[:preview_lines]
        preview_max_chars = config_obj.output.preview_max_chars
        if preview_max_chars > 0:
            raw_preview = [
                line[:preview_max_chars] + "…" if len(line) > preview_max_chars else line
                for line in raw_preview
            ]

        total_lines = int(write_result["total_lines"])
        return StoredResult(
            handle=str(write_result["handle"]),
            total_lines=total_lines,
            size_bytes=int(write_result["size_bytes"]),
            summary=f"{total_lines} lines from {tool}" if tool else f"{total_lines} lines stored",
            preview="\n".join(raw_preview),
            status=str(write_result.get("status", "pending")),
            content_type=str(write_result.get("content_type", "text")),
        )

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
    ) -> QueryResult:
        """Query ctx-stored output."""
        if search:
            if fuzzy:
                raise ValueError(
                    "fuzzy=True is no longer supported; "
                    "use ot.result(handle=..., search='pattern') for regex search."
                )
            from ot.ctx import grep

            result = grep.ctx_grep(handle, search, context=context)
            if "error" in result:
                raise ValueError(result["error"])
            all_lines = result["content"].splitlines() if result["content"] else []
            total = len(all_lines)
            if tail > 0:
                offset = max(1, total - tail + 1)
                limit = tail
            start = offset - 1
            end = start + limit
            chunk = all_lines[start:end]
            returned = len(chunk)
            next_query = ""
            if end < total:
                next_offset = offset + returned
                next_query = (
                    f"ot.result(handle='{handle}', search={search!r}, "
                    f"offset={next_offset}, limit={limit})"
                )
            return QueryResult(
                content="\n".join(chunk),
                total_lines=total,
                returned=returned,
                offset=offset,
                has_more=end < total,
                handle=handle,
                limit=limit,
                total_size_bytes=0,
                next_query=next_query,
            )

        from ot.ctx import read

        result = read.ctx_read(handle, offset=offset, limit=limit, tail=tail)
        if "error" in result:
            raise ValueError(result["error"])

        next_query = ""
        if result.get("has_more"):
            next_offset = int(result["offset"]) + int(result["returned"])
            next_query = f"ot.result(handle='{handle}', offset={next_offset}, limit={limit})"

        return QueryResult(
            content=result["content"],
            total_lines=int(result["total_lines"]),
            returned=int(result["returned"]),
            offset=int(result["offset"]),
            has_more=bool(result["has_more"]),
            handle=handle,
            limit=limit,
            total_size_bytes=int(result.get("total_size_bytes", 0)),
            next_query=next_query,
        )

    def cleanup(self) -> int:
        """Delete expired ctx entries."""
        from ot.ctx.maintenance import ctx_purge

        result = ctx_purge()
        return int(result.get("deleted", 0))

    def format_store_response(self, stored: Any) -> dict[str, Any]:
        """Format runner response with the universal ot.result follow-up hint.

        Uses ot.result(handle=...) — always present in the base install — rather than
        ctx.* commands, which only exist when the optional [util] extra is installed.
        """
        if not isinstance(stored, StoredResult):
            raise TypeError("ctx result store expected StoredResult")
        response = stored.to_dict()
        response["next_commands"] = [f"ot.result(handle='{stored.handle}')"]
        return response


def register_services(registry: Any) -> None:
    """Register ctx result-store services."""
    registry.register_result_store(CtxResultStoreBackend())
