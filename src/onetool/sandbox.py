"""One public Monty provider for exact tool calls, bounded prints and batches.

Public seam proved by P18. Upstream drafts: [gateway]-v4/pocs/upstream-gaps.md.
"""

from __future__ import annotations

import ast
import asyncio
import difflib
import json
import keyword
import math
import textwrap
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import anyio
import yaml
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import TextContent
from pydantic_monty import AsyncMonty, ClassInstance, MontyRuntimeError, MontySyntaxError

from onetool.operations import UnknownOutcome

if TYPE_CHECKING:
    from onetool.gateway import Gateway

FORMATS = frozenset({"json", "json-indent", "yaml", "yaml-block", "text"})


def prepare(code: str) -> str:
    """Remove one whole-submission fence and common indent, retaining source lines."""
    lines = code.splitlines()
    nonblank = [i for i, line in enumerate(lines) if line.strip()]
    if nonblank:
        first, last = nonblank[0], nonblank[-1]
        if lines[first].strip() in {"```", "```py", "```python"} and lines[last].strip() == "```":
            lines[first] = lines[last] = ""
    source = textwrap.dedent("\n".join(lines))
    if not source.strip():
        raise ToolError("Code is empty")
    return source


def safe_value(value: Any) -> Any:
    """JSON-safe final values without non-finite numbers, Python tags or surrogates."""
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode()
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(safe_value(key)): safe_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [safe_value(item) for item in value]
    return str(value)


@dataclass
class Presentation:
    cap: int
    chunks: list[str] = field(default_factory=list)
    used: int = 0
    truncated: bool = False
    format: str = "json"
    value: Any = None

    def capture(self, stream: str, text: str) -> None:
        raw = text.encode("utf-8", errors="replace")
        room = max(0, self.cap - self.used - 40)
        piece = raw[:room].decode("utf-8", errors="ignore")
        self.used += len(piece.encode())
        if piece:
            self.chunks.append(piece)
        self.truncated |= len(raw) > room

    def printed(self) -> str:
        notice = "[Printed output truncated]\n" if self.truncated else ""
        return notice + "".join(self.chunks)


class CallBudgetExceeded(ToolError):
    """No further tool invocation was dispatched."""


class OneToolSandbox:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway
        self.presentation: ContextVar[Presentation | None] = ContextVar(
            "presentation", default=None
        )

    async def run(
        self,
        code: str,
        *,
        inputs: dict[str, Any] | None = None,
        external_functions: dict[str, Callable[..., Any]] | None = None,
    ) -> Any:
        from onetool.gateway import Catalog

        source = prepare(code)
        # A literal bad format is rejected before any statement can have side effects.
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None  # Monty's parser owns syntax diagnostics.
        for node in ast.walk(tree) if tree else ():
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "set_format"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value not in FORMATS
            ):
                raise ToolError("Unknown format; use " + ", ".join(sorted(FORMATS)))
        gateway = self.gateway
        execution = gateway.config.model.execution
        state = self.presentation.get() or Presentation(execution.max_output_bytes)
        tools: dict[str, Any] = {}
        catalog_loaded = False
        catalog_lock = asyncio.Lock()

        async def ensure_catalog() -> None:
            nonlocal catalog_loaded
            async with catalog_lock:
                if not catalog_loaded:
                    tools.update({tool.name: tool for tool in await Catalog(gateway).list_tools()})
                    catalog_loaded = True

        if tree and any(
            isinstance(node, ast.Name) and node.id in gateway.backends for node in ast.walk(tree)
        ):
            await ensure_catalog()
        original = (external_functions or {})["call_tool"]
        pending: set[asyncio.Task[Any]] = set()
        finished = False
        count = 0

        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            nonlocal count
            if finished:
                raise asyncio.CancelledError
            task = asyncio.current_task()
            assert task is not None
            pending.add(task)
            try:
                if (
                    not isinstance(name, str)
                    or not isinstance(arguments, dict)
                    or not all(isinstance(key, str) for key in arguments)
                ):
                    raise ToolError(
                        "call_tool needs an exact name and string-keyed argument mapping"
                    )
                await ensure_catalog()
                if name not in tools:
                    suggestions = difflib.get_close_matches(name, list(tools), n=3)
                    raise ToolError(f"Unknown tool {name}; exact suggestions: {suggestions}")
                schema = tools[name].parameters
                properties = schema.get("properties", {})
                # Open/free-form schemas belong to the upstream validator (G003).
                unknown = (
                    set(arguments) - properties.keys()
                    if "properties" in schema and schema.get("additionalProperties") is False
                    else set()
                )
                if unknown:
                    suggestions = difflib.get_close_matches(
                        sorted(unknown)[0], list(properties), n=3
                    )
                    raise ToolError(
                        f"Unknown parameter {sorted(unknown)}; exact suggestions: {suggestions}"
                    )
                if count >= execution.max_tool_calls:
                    raise CallBudgetExceeded("Tool call limit exceeded; call was not dispatched")
                count += 1
                return await original(name, arguments)
            finally:
                pending.discard(task)

        def method(name: str) -> Callable[..., Any]:
            async def invoke(*args: Any, **kwargs: Any) -> Any:
                if args:
                    raise ToolError(
                        "Use keyword arguments: "
                        + ", ".join(tools[name].parameters.get("properties", {}))
                    )
                return await call_tool(name, kwargs)

            return invoke

        namespaces: dict[str, dict[str, Any]] = {}
        for name in tools:
            server = max((s for s in gateway.backends if name.startswith(s + "_")), key=len)
            member = name[len(server) + 1 :]
            if (
                member.isidentifier()
                and not keyword.iskeyword(member)
                and not member.startswith("_")
            ):
                namespaces.setdefault(server, {})[member] = method(name)

        def set_format(value: str) -> None:
            if finished:
                raise asyncio.CancelledError
            if not isinstance(value, str) or value not in FORMATS:
                raise ToolError("Unknown format; use " + ", ".join(sorted(FORMATS)))
            state.format = value

        async def call_tools(calls: list[Any], *, concurrency: int = 4) -> list[dict[str, Any]]:
            if (
                type(concurrency) is not int
                or not 1 <= concurrency <= 16
                or not isinstance(calls, list)
            ):
                raise ToolError("calls must be a list; concurrency must be an integer from 1 to 16")
            parsed = []
            for item in calls:
                if isinstance(item, dict) and set(item) == {"tool", "arguments"}:
                    name, arguments = item["tool"], item["arguments"]
                elif isinstance(item, list | tuple) and len(item) == 2:
                    name, arguments = item
                else:
                    raise ToolError("Each call must contain tool and arguments")
                if (
                    not isinstance(name, str)
                    or not isinstance(arguments, dict)
                    or not all(isinstance(k, str) for k in arguments)
                ):
                    raise ToolError("Each call needs a tool name and an argument mapping")
                parsed.append((name, arguments))
            if parsed:
                await ensure_catalog()
            outcomes = [
                dict(index=i, tool=n, status="cancelled", error="Not dispatched")
                for i, (n, _) in enumerate(parsed)
            ]
            cursor = 0

            async def worker() -> None:
                nonlocal cursor
                while cursor < len(parsed):
                    i = cursor
                    cursor += 1
                    name, arguments = parsed[i]
                    if count >= execution.max_tool_calls:
                        continue
                    try:
                        value = await call_tool(name, arguments)
                        outcomes[i] = dict(index=i, tool=name, status="ok", value=value)
                    except CallBudgetExceeded:
                        continue
                    except asyncio.CancelledError:
                        outcomes[i] = dict(
                            index=i,
                            tool=name,
                            status="unknown",
                            error="Interrupted; outcome unknown. Do not replay.",
                        )
                        raise
                    except Exception as exc:
                        cause: BaseException | None = exc
                        unknown = False
                        while cause is not None:
                            unknown |= isinstance(cause, UnknownOutcome)
                            cause = cause.__cause__
                        outcomes[i] = dict(
                            index=i,
                            tool=name,
                            status="unknown" if unknown else "error",
                            error=gateway.redact(str(exc)),
                        )

            tasks = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(parsed)))]
            try:
                deadline = gateway.deadline.get()
                await asyncio.wait(
                    tasks, timeout=max(0, deadline - time.monotonic() - 0.03) if deadline else None
                ) if tasks else None
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                with anyio.CancelScope(shield=True):
                    await asyncio.gather(*tasks, return_exceptions=True)
            return outcomes

        async def guarded_batch(calls: list[Any], *, concurrency: int = 4) -> list[dict[str, Any]]:
            if finished:
                raise asyncio.CancelledError
            task = asyncio.current_task()
            assert task is not None
            pending.add(task)
            try:
                return await call_tools(calls, concurrency=concurrency)
            finally:
                pending.discard(task)

        lookup: dict[str, Any] = {
            **(external_functions or {}),
            "call_tool": call_tool,
            "call_tools": guarded_batch,
            "set_format": set_format,
        }
        lookup.update(
            {
                name: ClassInstance(SimpleNamespace(**attrs), allowed_methods=set(attrs))
                for name, attrs in namespaces.items()
            }
        )

        async def feed() -> Any:
            async with (
                AsyncMonty() as pool,
                pool.checkout(
                    limits={
                        "max_feed_duration_secs": execution.timeout_seconds,
                        "max_memory": 100_000_000,
                    },
                    script_name="submitted.py",
                ) as session,
            ):
                return await session.feed_run(
                    source, inputs=inputs, external_lookup=lookup, print_callback=state.capture
                )

        # Monty #821 can leave callbacks alive after exit. Keep native provider safety.
        # https://github.com/pydantic/monty/issues/821
        future = asyncio.ensure_future(feed())
        try:
            state.value = safe_value(await future)
            if isinstance(state.value, list) and not state.value:
                return ToolResult(content="[]")
            return state.value
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as exc:
            message = (
                exc.display() if isinstance(exc, MontyRuntimeError | MontySyntaxError) else str(exc)
            )
            if isinstance(exc, MontyRuntimeError) and isinstance(
                exc.exception(), NameError | AttributeError
            ):
                candidates = (
                    list(gateway.backends)
                    if isinstance(exc.exception(), NameError)
                    else list(tools)
                )
                requested = ""
                if tree:
                    for node in ast.walk(tree):
                        if (
                            isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and isinstance(node.func.value, ast.Name)
                        ):
                            requested = (
                                node.func.value.id
                                if isinstance(exc.exception(), NameError)
                                else node.func.value.id + "_" + node.func.attr
                            )
                suggestions = difflib.get_close_matches(requested, candidates, n=3)
                message += (
                    "\nExact suggestions: " + ", ".join(suggestions)
                    if suggestions
                    else "\nNo close exact names. Use search/get_schema."
                )
            return ToolResult(content=safe_value(message), is_error=True)
        finally:
            finished = True
            tasks = tuple(pending)
            for task in tasks:
                task.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def compose(result: ToolResult, state: Presentation) -> ToolResult:
        printed = state.printed()
        if not printed:
            return result
        return result.model_copy(
            update={"content": [TextContent(type="text", text=printed), *result.content]}
        )

    @staticmethod
    def render(result: ToolResult, state: Presentation) -> ToolResult:
        if (
            state.format == "json"
            or result.is_error
            or (result.structured_content or {}).get("path")
        ):
            return result
        value = state.value
        if state.format == "json-indent":
            text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        elif state.format.startswith("yaml"):
            text = yaml.safe_dump(
                value, allow_unicode=True, default_flow_style=state.format == "yaml"
            ).strip()
        else:
            text = str(value)
        return result.model_copy(
            update={"content": [TextContent(type="text", text=state.printed() + text)]}
        )
