"""Bound final output with recoverable private files, never by re-executing."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import secrets
import tempfile
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jmespath
import regex
import yaml
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import TextContent

from onetool.diagnostics import event


def encoded(result: ToolResult) -> bytes:
    return json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
    ).encode()


def limited_json(value: Any, limit: int) -> bytearray:
    """Encode at most limit+1 bytes, without copying/traversing an amplified answer."""
    raw = bytearray()
    for chunk in json.JSONEncoder(ensure_ascii=False, default=str).iterencode(value):
        remaining = limit + 1 - len(raw)
        # A single escaped string chunk can be large; encode only its bounded prefix.
        raw.extend(chunk[:remaining].encode("utf-8", errors="replace")[:remaining])
        if len(raw) > limit:
            break
    return raw


@dataclass(frozen=True)
class ResultEntry:
    path: Path
    kind: str
    format: str
    source: str | None
    is_error: bool
    created: float


class ResultFiles:
    def __init__(
        self, logger: logging.Logger, cap: int, *, protect: Callable[[Any], Any] | None = None
    ):
        self.protect = protect or (lambda value: value)
        self.worker_lock = asyncio.Lock()
        self.logger = logger
        self.cap = cap
        self.hard_limit = 16 * 1024 * 1024
        self.directory_limit = 256 * 1024 * 1024
        self.directory: Path | None = None
        self.files: deque[tuple[Path, int]] = deque()
        self.total = 0
        self.temporary: tempfile.TemporaryDirectory[str] | None = None
        self.handle_limit = 4096
        self.tombstone_limit = 1024
        self.entries: OrderedDict[str, ResultEntry] = OrderedDict()
        self.path_handles: dict[Path, str] = {}
        self.tombstones: OrderedDict[str, str] = OrderedDict()

    def close(self) -> None:
        if self.temporary:
            self.temporary.cleanup()
        self.files.clear()
        self.entries.clear()
        self.path_handles.clear()
        self.tombstones.clear()
        self.total = 0
        self.directory = None
        self.temporary = None

    def bound(
        self,
        result: ToolResult,
        *,
        force: bool = False,
        native: Any = None,
        source: str | None = None,
        format: str | None = None,
    ) -> ToolResult:
        raw = encoded(result)
        if len(raw) <= self.cap and not force:
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
            while self.files and (
                self.total + len(raw) > self.directory_limit
                or len(self.entries) >= self.handle_limit
            ):
                oldest, size = self.files[0]
                oldest.unlink(missing_ok=True)
                self.files.popleft()
                self._forget(oldest, "evicted")
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
        handle = secrets.token_hex(6)
        while handle in self.entries or handle in self.tombstones:
            handle = secrets.token_hex(6)
        kind = type(native).__name__
        detected = format or (
            "json"
            if isinstance(native, dict | list)
            else "markdown"
            if isinstance(native, str) and re.search(r"(?m)^#{1,6} ", native)
            else "text"
        )
        source = (
            source.encode("utf-8", errors="replace")[:1024].decode("utf-8", errors="ignore")
            if source
            else None
        )
        self.entries[handle] = ResultEntry(
            path, kind, detected, source, result.is_error, time.time()
        )
        self.path_handles[path] = handle
        receipt: dict[str, Any] = {
            "handle": handle,
            "path": str(path),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "message": (
                "Execution completed. Use onetool_results read/grep/query or results.read(handle). "
                "The path also works with your file tools. Do not repeat the call."
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

    def _forget(self, path: Path, reason: str) -> None:
        handle = self.path_handles.pop(path, None)
        if handle is not None:
            self.entries.pop(handle, None)
            self.tombstones[handle] = reason
            while len(self.tombstones) > self.tombstone_limit:
                self.tombstones.popitem(last=False)

    def _entry(self, handle: str | None) -> ResultEntry:
        if handle in self.entries:
            assert handle is not None
            return self.entries[handle]
        reason = self.tombstones.get(handle or "")
        raise ToolError(
            f"{reason} handle" if reason else "unknown handle (expired or never issued)"
        )

    def _snapshot(self, handle: str | None) -> tuple[ResultEntry, dict[str, Any], str]:
        entry = self._entry(handle)
        try:
            envelope = json.loads(entry.path.read_text())
        except (OSError, ValueError):
            raise ToolError("Stored result unavailable") from None
        text = "\n".join(block["text"] for block in envelope["content"] if block["type"] == "text")
        return entry, envelope, text

    def fit(self, data: dict[str, Any]) -> dict[str, Any]:
        # JMESPath can repeat references: never normalize/serialize an unbounded answer.
        try:
            raw = limited_json(data, self.cap)
            if len(raw) <= self.cap:
                data = json.loads(raw, parse_constant=str)
                if len(encoded(ToolResult(content=data, structured_content=data))) <= self.cap:
                    return data
                if "handle" in data and "path" in data:
                    while data.get("preview"):
                        data["preview"] = data["preview"][: len(data["preview"]) // 2]
                        if (
                            len(encoded(ToolResult(content=data, structured_content=data)))
                            <= self.cap
                        ):
                            return data
        except (TypeError, ValueError, RecursionError):
            return {"truncated": True, "message": "Result cannot be encoded; narrow the selection."}
        preview = bytes(raw[: self.cap // 4]).decode("utf-8", errors="ignore")
        clipped = {
            "truncated": True,
            "preview": preview,
            "message": "Narrow the selection or page limit; do not repeat the upstream call.",
            **{key: data[key] for key in ("is_error", "valid") if type(data.get(key)) is bool},
        }
        while len(encoded(ToolResult(content=clipped, structured_content=clipped))) > self.cap:
            preview = preview[: len(preview) // 2]
            clipped["preview"] = preview
        return clipped

    @staticmethod
    def _typed(entry: ResultEntry, envelope: dict[str, Any]) -> Any:
        value = envelope.get("structured_content")
        if value is not None:
            if entry.kind == "list" and set(value) == {"result"}:
                return value["result"]
            return value
        if entry.kind == "list":
            # Provenance identifies the native renderer's selected list, not arbitrary text.
            return json.loads(envelope["content"][-1]["text"])
        raise ToolError("No structured value; use read or grep")

    @staticmethod
    def _line(line: str) -> str:
        line = line.rstrip("\n\r")
        return line if len(line) <= 500 else line[:500] + f"[+{len(line) - 500} chars]"

    @staticmethod
    def _prepare_value(value: Any) -> tuple[Any, str, str]:
        from onetool.sandbox import safe_value

        value = safe_value(value)
        if isinstance(value, dict | list):
            return value, json.dumps(value, ensure_ascii=False, indent=2), "json"
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict | list):
                    parsed = safe_value(parsed)
                    return parsed, json.dumps(parsed, ensure_ascii=False, indent=2), "json"
            except (ValueError, RecursionError):
                pass
            if re.search(r"(?m)^#{1,6} ", value):
                return value, value, "markdown"
            # Explicit write requests format detection; auto-offloaded MCP text is never parsed.
            try:
                if not any(
                    isinstance(token, yaml.tokens.AliasToken | yaml.tokens.AnchorToken)
                    for token in yaml.scan(value)
                ):
                    parsed = yaml.safe_load(value)
                    if isinstance(parsed, dict | list):
                        return safe_value(parsed), value, "yaml"
            except (yaml.YAMLError, RecursionError):
                pass
            return value, value, "text"
        return value, json.dumps(value, ensure_ascii=False), "text"

    def _write(self, value: Any, source: str | None, *, is_error: bool = False) -> dict[str, Any]:
        try:
            raw = limited_json(value, self.hard_limit)
            if len(raw) > self.hard_limit:
                raise ToolError(
                    "Result exceeds 16 MiB; not retained. Do not replay an upstream call."
                )
            value = json.loads(raw, parse_constant=str)
        except (TypeError, ValueError, RecursionError):
            raise ToolError("Result cannot be retained; do not replay an upstream call") from None
        value = self.protect(value)
        source = self.protect(source)
        native, text, format = self._prepare_value(value)
        structured = (
            native
            if isinstance(native, dict)
            else {"result": native}
            if isinstance(native, list)
            else None
        )
        result = self.bound(
            ToolResult(content=text, structured_content=structured, is_error=is_error),
            force=True,
            native=native,
            source=source,
            format=format,
        )
        if not result.structured_content or "handle" not in result.structured_content:
            raise ToolError("Result could not be retained; do not repeat an upstream call")
        return self.fit(result.structured_content)

    def _delete(self, handle: str) -> None:
        entry = self._entry(handle)
        entry.path.unlink(missing_ok=True)
        self._forget(entry.path, "deleted")
        self.files = deque((p, size) for p, size in self.files if p != entry.path)
        self.total = sum(size for _, size in self.files)

    def _toc(self, entry: ResultEntry, envelope: dict[str, Any], text: str) -> list[dict[str, Any]]:
        if entry.format == "markdown":
            headings: list[dict[str, Any]] = []
            for number, line in enumerate(io.StringIO(text), 1):
                match = re.match(r"^(#{1,6})\s+(.+)", line)
                if match:
                    headings.append(
                        {
                            "section": len(headings) + 1,
                            "line": number,
                            "level": len(match[1]),
                            "title": match[2].strip(),
                        }
                    )
                    if len(headings) >= 500:
                        break
            return headings
        try:
            value = self._typed(entry, envelope)
        except ToolError:
            return []
        if isinstance(value, list):
            return [{"key": "[array]", "type": "list", "size": len(value)}]
        return (
            [
                {
                    "key": str(key),
                    "type": type(item).__name__,
                    **({"size": len(item)} if isinstance(item, dict | list) else {}),
                }
                for key, item in list(value.items())[:500]
            ]
            if isinstance(value, dict)
            else []
        )

    def _grep(
        self,
        text: str,
        pattern: str,
        context: int,
        limit: int,
        case_sensitive: bool,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        compiled = regex.compile(pattern, flags=0 if case_sensitive else regex.IGNORECASE)
        before: deque[tuple[int, str]] = deque(maxlen=context)
        selected: dict[int, str] = {}
        matches = []
        after = 0
        used = 0
        truncated = False
        for number, line in enumerate(io.StringIO(text), 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if compiled.search(line, timeout=remaining):
                matches.append(number)
                for i, prior in before:
                    selected[i] = self._line(prior)
                selected[number] = self._line(line)
                after = context
            elif after:
                selected[number] = self._line(line)
                after -= 1
            before.append((number, line))
            used += len(line.encode()) if number in selected else 0
            if len(matches) >= limit or used >= self.cap // 2:
                truncated = True
                break
        output = []
        previous = 0
        for number, line in sorted(selected.items()):
            if previous and number > previous + 1:
                output.append("---")
            output.append(f"{number}: {line}")
            previous = number
        return {"matches": matches, "text": "\n".join(output), "truncated": truncated}

    async def worker(self, work: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        await self.worker_lock.acquire()
        try:
            future = asyncio.create_task(asyncio.to_thread(work))
        except BaseException:
            self.worker_lock.release()
            raise

        def finished(task: asyncio.Task[dict[str, Any]]) -> None:
            self.worker_lock.release()
            if not task.cancelled():
                task.exception()  # Consume failures even when the caller has already cancelled.

        future.add_done_callback(finished)
        return await asyncio.shield(future)  # Cancel caller promptly; worker retains the lock.

    def query(self, handle: str | None, expression: str | None) -> dict[str, Any]:
        if not isinstance(expression, str) or len(expression.encode()) > 4096:
            raise ToolError("query needs an expression of at most 4 KiB")
        entry, envelope, _ = self._snapshot(handle)
        native = self._typed(entry, envelope)
        try:
            answer = jmespath.search(expression, native)
        except (jmespath.exceptions.JMESPathError, RecursionError):
            raise ToolError("Invalid query expression") from None
        return self.fit({"handle": handle, "value": answer, "is_error": entry.is_error})

    def search(
        self,
        handle: str | None,
        pattern: str | None,
        context: int,
        limit: int,
        case_sensitive: bool,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if not isinstance(pattern, str) or len(pattern.encode()) > 1024:
            raise ToolError("grep needs a pattern of at most 1 KiB")
        if type(context) is not int or not 0 <= context <= 50:
            raise ToolError("context must be 0 through 50")
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 1:
            raise ToolError("grep timeout must be greater than zero and at most 1 second")
        _, _, text = self._snapshot(handle)
        try:
            data = self._grep(text, pattern, context, limit, case_sensitive, timeout_seconds)
        except TimeoutError:
            raise ToolError("Result search timed out; narrow the search") from None
        except regex.error:
            raise ToolError("Invalid search pattern") from None
        return self.fit({"handle": handle, **data})

    async def action(
        self,
        action: str,
        handle: str | None = None,
        *,
        value: Any = None,
        source: str | None = None,
        offset: int = 0,
        limit: int = 100,
        tail: bool = False,
        pattern: str | None = None,
        context: int = 0,
        case_sensitive: bool = False,
        timeout_seconds: float = 1,
        expression: str | None = None,
        select: str | None = None,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 500 or type(offset) is not int or offset < 0:
            raise ToolError("offset must be nonnegative; limit must be 1 through 500")
        if action == "list":
            return self.fit(
                {
                    "results": [
                        {
                            "handle": h,
                            "format": e.format,
                            "source": e.source,
                            "is_error": e.is_error,
                        }
                        for h, e in self.entries.items()
                    ]
                }
            )
        if action == "write":
            return self._write(value, source)
        if action == "purge":
            count = len(self.entries)
            for h in list(self.entries):
                self._delete(h)
            return {"deleted": count}
        if action == "query":
            return await self.worker(lambda: self.query(handle, expression))
        if action == "grep":
            return await self.worker(
                lambda: self.search(
                    handle,
                    pattern,
                    context,
                    limit,
                    case_sensitive,
                    timeout_seconds,
                )
            )
        entry, envelope, text = self._snapshot(handle)
        assert handle is not None
        if action == "inspect":
            return self.fit(
                {
                    "handle": handle,
                    "format": entry.format,
                    "source": entry.source,
                    "is_error": entry.is_error,
                    "size": entry.path.stat().st_size,
                    "lines": text.count("\n") + bool(text and not text.endswith("\n")),
                }
            )
        if action == "delete":
            self._delete(handle)
            return {"deleted": handle}
        if action == "append":
            if not isinstance(value, str):
                raise ToolError("append value must be text")
            receipt = self._write(
                text + "\n" + value, source or entry.source, is_error=entry.is_error
            )
            temporary = receipt["handle"]
            new_entry = self.entries.pop(temporary)
            if handle in self.entries:
                self._delete(handle)
            self.tombstones.pop(handle, None)
            self.entries[handle] = new_entry
            self.path_handles[new_entry.path] = handle
            return self.fit({**receipt, "handle": handle})
        if action == "toc":
            return self.fit({"handle": handle, "sections": self._toc(entry, envelope, text)})
        start, end = offset + 1, offset + limit
        if action == "slice":
            if not isinstance(select, str):
                raise ToolError("slice needs N:M, #N or a heading")
            if re.fullmatch(r"\d+:\d+", select):
                start, end = map(int, select.split(":"))
                if start < 1 or end < start:
                    raise ToolError("Invalid line range")
            else:
                headings = self._toc(entry, envelope, text)
                found = next(
                    (
                        i
                        for i, h in enumerate(headings)
                        if (
                            select == "#" + str(i + 1)
                            if re.fullmatch(r"#\d+", select)
                            else select.casefold() in h.get("title", "").casefold()
                        )
                    ),
                    None,
                )
                if found is None or entry.format != "markdown":
                    raise ToolError("Markdown section not found")
                start = headings[found]["line"]
                end = next(
                    (
                        h["line"] - 1
                        for h in headings[found + 1 :]
                        if h["level"] <= headings[found]["level"]
                    ),
                    text.count("\n") + 1,
                )
        elif action != "read":
            raise ToolError("Unknown results action")
        lines: list[str] | deque[str] = deque(maxlen=limit) if tail else []
        for number, line in enumerate(io.StringIO(text), 1):
            if tail or start <= number <= end:
                lines.append(self._line(line))
            if not tail and (number >= end or len(lines) >= 500):
                break
        return self.fit({"handle": handle, "text": "\n".join(lines), "is_error": entry.is_error})
