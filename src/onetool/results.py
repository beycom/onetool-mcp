"""Bound final output with recoverable private files, never by re-executing."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from collections import deque
from pathlib import Path
from typing import Any

from fastmcp.tools import ToolResult
from mcp.types import TextContent

from onetool.diagnostics import event


def encoded(result: ToolResult) -> bytes:
    return json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
    ).encode()


class ResultFiles:
    def __init__(self, logger: logging.Logger, cap: int):
        self.logger = logger
        self.cap = cap
        self.hard_limit = 16 * 1024 * 1024
        self.directory_limit = 256 * 1024 * 1024
        self.directory: Path | None = None
        self.files: deque[tuple[Path, int]] = deque()
        self.total = 0
        self.temporary: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.temporary:
            self.temporary.cleanup()
        self.files.clear()
        self.total = 0
        self.directory = None
        self.temporary = None

    def bound(self, result: ToolResult) -> ToolResult:
        raw = encoded(result)
        if len(raw) <= self.cap:
            return result
        if len(raw) > self.hard_limit:
            return ToolResult(
                content=(
                    "Execution may have completed. Result exceeds 16 MiB and was not retained. "
                    "Do not replay the call."
                ),
                is_error=True,
            )
        try:
            if self.directory is None:
                self.temporary = tempfile.TemporaryDirectory(prefix="onetool-results-")
                self.directory = Path(self.temporary.name)
                self.directory.chmod(0o700)
            while self.files and self.total + len(raw) > self.directory_limit:
                oldest, size = self.files.popleft()
                oldest.unlink(missing_ok=True)
                self.total -= size
                event(self.logger, "result_evicted")
            fd, name = tempfile.mkstemp(suffix=".json", dir=self.directory)
            path = Path(name)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            self.files.append((path, len(raw)))
            self.total += len(raw)
        except OSError:
            return ToolResult(
                content=(
                    "Execution completed, but the result file could not be written. "
                    "Do not replay the call."
                ),
                is_error=True,
            )
        receipt: dict[str, Any] = {
            "path": str(path),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "message": (
                "Execution completed. Read the file with your own tools. Do not repeat the call."
            ),
        }
        # Serialized JSON escaping and the receipt itself count toward the inline cap.
        low, high = 0, min(len(raw), self.cap)
        bounded = self.receipt(receipt, "", result.is_error)
        while low <= high:
            middle = (low + high) // 2
            candidate = self.receipt(
                receipt, raw[:middle].decode("utf-8", errors="ignore"), result.is_error
            )
            if len(encoded(candidate)) <= self.cap:
                bounded = candidate
                low = middle + 1
            else:
                high = middle - 1
        event(self.logger, "result_saved", outcome="error" if result.is_error else "success")
        return bounded

    @staticmethod
    def receipt(fields: dict[str, Any], preview: str, is_error: bool) -> ToolResult:
        data = {**fields, "preview": preview}
        return ToolResult(
            content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
            structured_content=data,
            is_error=is_error,
        )
