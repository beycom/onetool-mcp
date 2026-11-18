"""One process, native proxy providers and CodeMode. No execution engine.

Public-API wiring is proved in planning/features/ready/[gateway]-v4/pocs/.
The small catalog/lifecycle stand-ins correspond to upstream-gaps.md there.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from fastmcp import FastMCP
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from fastmcp.experimental.transforms.code_mode import CodeMode, GetSchemas, Search
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt
from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.providers import FastMCPProvider, Provider
from fastmcp.server.providers.proxy import ProxyProvider, StatefulProxyClient
from fastmcp.server.transforms import Namespace, ToolTransform, Transform
from fastmcp.tools import Tool, ToolResult
from fastmcp.tools.tool_transform import ToolTransformConfig
from fastmcp.utilities.versions import VersionSpec
from key_value.aio.stores.keyring import KeyringStore
from mcp import types as mt
from mcp.shared.exceptions import MCPError

from onetool import __version__
from onetool.config import HttpServer, LoadedConfig, StdioServer
from onetool.diagnostics import Redactor, event, failure_details, logging_context
from onetool.operations import Operations, UnknownOutcome
from onetool.results import ResultFiles, encoded
from onetool.sandbox import OneToolSandbox, Presentation
from onetool.secrets import secure_keyring


def interruption(exc: BaseException) -> str | None:
    """Upstream wraps transport exceptions in ToolError; inspect typed causes only."""
    seen: set[int] = set()
    while id(exc) not in seen:
        seen.add(id(exc))
        if (
            isinstance(exc, TimeoutError)
            or isinstance(exc, MCPError)
            and exc.code == mt.REQUEST_TIMEOUT
        ):
            return "timeout"
        if (
            isinstance(exc, ConnectionError)
            or isinstance(exc, MCPError)
            and exc.code == mt.CONNECTION_CLOSED
        ):
            return "connection_lost"
        cause = exc.__cause__ or exc.__context__
        if cause is None:
            return None
        exc = cause
    return None


class StorageUnavailable(ToolError):
    """A safe authentication error, with no credential or upstream payload."""

    category = "authentication"


def oauth_storage(name: str) -> KeyringStore:
    """Check system storage before OAuth can turn a failed read into a new login."""
    import keyring

    try:
        backend = keyring.get_keyring()
        if not secure_keyring(backend):
            raise RuntimeError("no supported secure keyring")
        # KeyringStore swallows read errors. Probe availability without any token write.
        keyring.get_password("onetool-mcp", "storage-availability-check")
    except Exception:
        raise StorageUnavailable(
            f"{name}: OAuth token storage unavailable; configure a system keyring. "
            "No plaintext fallback."
        ) from None
    return KeyringStore(service_name="onetool-mcp")


class MetadataClient(StatefulProxyClient[Any]):
    """Observe public metadata while connected; P21 proves context lifetime."""

    observe: Callable[[Any], None]

    async def __aenter__(self) -> Any:
        client = await super().__aenter__()  # type: ignore[no-untyped-call]  # Public upstream hook lacks annotations.
        self.observe(client)
        return client


class CurationWarnings(Transform):
    def __init__(self, backend: Backend):
        self.backend = backend

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        unknown = set(self.backend.config.tools) - {tool.name for tool in tools}
        self.backend.warnings = [f"Unknown curation target: {name}" for name in sorted(unknown)]
        return tools


class Backend:
    def __init__(
        self,
        gateway: Gateway,
        name: str,
        config: StdioServer | HttpServer,
        loaded_config: LoadedConfig | None = None,
    ):
        self.gateway = gateway
        self.name = name
        self.config = config
        self.loaded_config = loaded_config or gateway.config
        self.state = "lazy" if config.enabled else "disabled"
        self.session_enabled: bool | None = None
        self.accepting = True
        self.active: set[asyncio.Task[Any]] = set()
        self.draining: set[asyncio.Task[Any]] = set()
        self.tool_count: int | None = None
        self.last_error: str | None = None
        self.failure_info: dict[str, str] | None = None
        self.native_instructions: str | None = None
        self.instructions_truncated = False
        self.warnings: list[str] = []
        self.observed_tools: list[Tool] = []
        self.observed_at: float | None = None
        self.capabilities: dict[str, bool] = {}
        if name in self.loaded_config.server_errors:
            self.state = "error"
            self.last_error = self.loaded_config.server_errors[name]
        self.client: StatefulProxyClient[Any] | None = None
        proxy = FastMCP(
            name,
            providers=[ProxyProvider(self.get_client, cache_ttl=0)],
            middleware=[BackendCalls(self)],
        )
        proxy.provider_error_strategy = "raise"
        proxy.add_transform(CurationWarnings(self))
        if config.tools:
            transforms = {
                name: ToolTransformConfig.model_validate(item.model_dump(exclude_unset=True))
                for name, item in config.tools.items()
            }
            proxy.add_transform(ToolTransform(transforms))
        if config.include_tags is not None:
            proxy.enable(tags=set(config.include_tags), only=True)
        if config.exclude_tags is not None:
            proxy.disable(tags=set(config.exclude_tags))
        self.provider = FastMCPProvider(proxy).wrap_transform(Namespace(name))

    @property
    def enabled(self) -> bool:
        return self.config.enabled if self.session_enabled is None else self.session_enabled

    def get_client(self) -> Any:
        if self.client is None:
            config = self.loaded_config.resolve_server(self.name)
            self.config = config
            self.gateway.refresh_redaction()
            if isinstance(config, StdioServer):
                env = {**os.environ, **config.env} if config.inherit_env else config.env
                target: dict[str, Any] = {
                    "transport": "stdio",
                    "command": config.command,
                    "args": config.args,
                    "cwd": config.cwd,
                    "env": env,
                }
            else:
                target = {"transport": "http", "url": config.url, "headers": config.headers}
                if config.auth:
                    target["auth"] = OAuth(
                        mcp_url=config.url,
                        scopes=config.auth.scopes,
                        token_storage=oauth_storage(self.name),
                    )
            # Public canonical conversion, with the one unsupported config option applied
            # through the public transport. P10 proves both stderr and OAuth wiring.
            transport = (
                MCPConfig.from_dict({"mcpServers": {self.name: target}})
                .mcpServers[self.name]
                .to_transport()
            )
            if isinstance(transport, StdioTransport):
                # A backend can print secrets or payloads. Do not retain raw startup stderr.
                transport.log_file = Path(os.devnull)
            client = MetadataClient(transport, timeout=config.timeout_seconds, mode="auto")
            client.observe = self.observe_metadata
            self.client = client
        return self.client.new_stateful()

    def observe_metadata(self, client: Any) -> None:
        raw = self.gateway.redact(client.instructions or "").encode("utf-8", errors="replace")
        self.instructions_truncated = len(raw) > 8192
        self.native_instructions = (
            raw[:8150].decode("utf-8", errors="ignore") + "\n[Instructions truncated]"
            if self.instructions_truncated
            else raw.decode() or None
        )

        capabilities = client.server_capabilities
        if capabilities is not None:
            self.capabilities = {
                "resources": bool(capabilities.resources),
                "prompts": bool(capabilities.prompts),
            }

    def observe_tools(self, tools: Sequence[Tool]) -> None:
        self.observed_tools = list(tools)
        self.observed_at = time.monotonic()

    async def close(self) -> None:
        if self.client:
            # The public upstream method has no return annotation.
            await self.client.clear()  # type: ignore[no-untyped-call]
            await self.client.transport.close()
            self.client = None
        self.state = "lazy" if self.config.enabled else "disabled"
        self.tool_count = None
        self.last_error = None
        self.observed_tools.clear()
        self.observed_at = None
        self.native_instructions = None
        self.capabilities.clear()
        self.warnings.clear()

    def failure(self, exc: Exception) -> None:
        self.state = "error"
        self.last_error = self.gateway.redact(f"{self.name}: {type(exc).__name__}: {exc}")[:300]
        self.failure_info = self.gateway.note_failure(exc)


class BackendCalls(Middleware):
    def __init__(self, backend: Backend):
        self.backend = backend

    def timeout(self) -> float:
        timeout = self.backend.config.timeout_seconds
        deadline = self.backend.gateway.deadline.get()
        return min(timeout, max(0, deadline - time.monotonic())) if deadline else timeout

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        backend = self.backend
        try:
            async with asyncio.timeout(self.timeout()):
                tools = await call_next(context)
            backend.state, backend.last_error, backend.tool_count = "ready", None, len(tools)
            return tools
        except Exception as exc:
            backend.failure(exc)
            event(
                backend.gateway.logger,
                "catalog_unavailable",
                level=logging.WARNING,
                server=backend.name,
                error_category=type(exc).__name__,
                outcome="unavailable",
            )
            raise ToolError(f"{backend.name}: catalog unavailable ({type(exc).__name__})") from None

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        backend = self.backend
        gateway = backend.gateway
        start = time.monotonic()
        fields = {
            "request_id": gateway.request_id.get(),
            "server": backend.name,
            "tool": context.message.name,
        }
        if not backend.enabled or not backend.accepting:
            raise ToolError(f"{backend.name}: server is disabled or changing; not dispatched")
        task = asyncio.current_task()
        assert task is not None
        backend.active.add(task)
        try:
            async with asyncio.timeout(self.timeout()):
                result = await call_next(context)
            backend.state, backend.last_error = "ready", None
            event(
                gateway.logger,
                "tool_completed",
                level=logging.DEBUG,
                **fields,
                duration=time.monotonic() - start,
                outcome="error" if result.is_error else "success",
            )
            if result.is_error:
                return gateway.sanitize_error(result)
            return result
        except TimeoutError as exc:
            backend.failure(exc)
            event(
                gateway.logger,
                "tool_timeout",
                level=logging.WARNING,
                **fields,
                duration=time.monotonic() - start,
                outcome="unknown",
                error_category="timeout",
            )
            raise UnknownOutcome(
                f"{backend.name}/{context.message.name}: timeout; "
                "dispatched outcome unknown. Do not replay.",
                category="timeout",
            ) from None
        except asyncio.CancelledError:
            event(
                gateway.logger,
                "tool_cancelled",
                level=logging.WARNING,
                **fields,
                duration=time.monotonic() - start,
                outcome="unknown",
                error_category="cancelled",
            )
            if task in backend.draining:
                gateway.note_failure(UnknownOutcome("Interrupted dispatched call"))
                task.uncancel()
                raise UnknownOutcome(
                    f"{backend.name}: dispatched outcome unknown. Do not replay."
                ) from None
            raise
        except ToolError as exc:
            category = interruption(exc)
            if category:
                backend.failure(exc)
                gateway.note_failure(
                    UnknownOutcome(
                        "Interrupted dispatched call",
                        category="timeout" if category == "timeout" else "outcome_unknown",
                    )
                )
                event(
                    gateway.logger,
                    "tool_interrupted",
                    level=logging.WARNING,
                    **fields,
                    duration=time.monotonic() - start,
                    outcome="unknown",
                    error_category=category,
                )
                raise UnknownOutcome(
                    f"{backend.name}/{context.message.name}: {category}; "
                    "dispatched outcome unknown. Do not replay."
                ) from None
            event(
                gateway.logger,
                "tool_failed",
                level=logging.WARNING,
                **fields,
                duration=time.monotonic() - start,
                outcome="error",
                error_category="tool_error",
            )
            raise ToolError(gateway.redact(str(exc))) from None
        except Exception as exc:
            backend.failure(exc)
            gateway.note_failure(UnknownOutcome("Interrupted dispatched call"))
            event(
                gateway.logger,
                "tool_interrupted",
                level=logging.WARNING,
                **fields,
                duration=time.monotonic() - start,
                outcome="unknown",
                error_category=type(exc).__name__,
            )
            raise UnknownOutcome(
                f"{backend.name}/{context.message.name}: interrupted ({type(exc).__name__}); "
                "dispatched outcome unknown. Do not replay."
            ) from None
        finally:
            backend.active.discard(task)
            backend.draining.discard(task)


class Catalog(Provider):
    """Replaceable native providers; reject namespace collisions before deduplication."""

    def __init__(self, gateway: Gateway):
        super().__init__()
        self.gateway = gateway

    async def _get_tool(self, name: str, version: VersionSpec | None = None) -> Tool | None:
        # Native aggregate lookup also asks mounted providers about admin names.
        if name.startswith("onetool_"):
            return None
        prefix, separator, _ = name.rpartition("_")
        while separator:
            backend = self.gateway.backends.get(prefix)
            if backend is not None and backend.enabled:
                if any(
                    prefix.startswith(other.name + "_") and other.enabled
                    for other in self.gateway.backends.values()
                ):
                    return await super()._get_tool(name, version)
                return await backend.provider.get_tool(name, version)
            prefix, separator, _ = prefix.rpartition("_")
        return None

    async def _list_tools(self) -> Sequence[Tool]:
        if not self.live_request():
            return []
        # Per-execute memo only; see upstream-gaps.md#per-call-codemode-catalog-resolution.
        memo = self.gateway.catalog_memo.get()
        if memo is not None and "tools" in memo:
            return memo["tools"]
        backends = [backend for backend in self.gateway.backends.values() if backend.enabled]
        results = await asyncio.gather(
            *(backend.provider.list_tools() for backend in backends), return_exceptions=True
        )
        names: dict[str, str] = {}
        tools: list[Tool] = []
        for backend, result in zip(backends, results, strict=True):
            if isinstance(result, BaseException):
                continue
            backend.observe_tools(result)
            for tool in result:
                if tool.name in names:
                    first = names[tool.name]
                    raise ToolError(
                        f"Namespace collision: {first}/{tool.name[len(first) + 1 :]} and "
                        f"{backend.name}/{tool.name[len(backend.name) + 1 :]}"
                    )
                names[tool.name] = backend.name
                tools.append(tool)
        if memo is not None:
            memo["tools"] = tools
        return tools

    def live_request(self) -> bool:
        return self.gateway.catalog_allowed.get()

    async def _list_resources(self) -> Sequence[Resource]:
        return await self.aggregate(lambda provider: provider.list_resources())

    async def _list_resource_templates(self) -> Sequence[ResourceTemplate]:
        return await self.aggregate(lambda provider: provider.list_resource_templates())

    async def _list_prompts(self) -> Sequence[Prompt]:
        return await self.aggregate(lambda provider: provider.list_prompts())

    async def aggregate[T](self, call: Callable[[Provider], Awaitable[Sequence[T]]]) -> list[T]:
        if not self.live_request():
            return []
        results = await asyncio.gather(
            *(
                call(backend.provider)
                for backend in self.gateway.backends.values()
                if backend.enabled
            ),
            return_exceptions=True,
        )
        return [
            component
            for result in results
            if not isinstance(result, BaseException)
            for component in result
        ]


class GatewayCalls(Middleware):
    def __init__(self, gateway: Gateway):
        self.gateway = gateway

    async def on_request(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        name = (
            context.message.get("name", "")
            if isinstance(context.message, dict)
            else getattr(context.message, "name", "")
        )
        allowed = context.method in {
            "tools/list",
            "tools/call",
            "resources/list",
            "resources/templates/list",
            "resources/read",
            "prompts/list",
            "prompts/get",
        } and not str(name).startswith("onetool_")
        token = self.gateway.catalog_allowed.set(allowed)
        try:
            return await call_next(context)
        finally:
            self.gateway.catalog_allowed.reset(token)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        gateway = self.gateway
        request_id = context.fastmcp_context.request_id if context.fastmcp_context else "-"
        token = gateway.request_id.set(request_id)
        failure_token = gateway.failure_context.set({})
        start = time.monotonic()
        try:
            if context.message.name != "execute":
                result = await call_next(context)
                event(
                    gateway.logger,
                    "request_completed",
                    request_id=request_id,
                    tool=context.message.name,
                    outcome="error" if result.is_error else "success",
                    duration=time.monotonic() - start,
                )
                return gateway.protect_result(gateway.sanitize_error(result))
            deadline = time.monotonic() + gateway.config.model.execution.timeout_seconds
            deadline_token = gateway.deadline.set(deadline)
            memo_token = gateway.catalog_memo.set({})
            presentation = Presentation(gateway.config.model.execution.max_output_bytes)
            presentation_token = gateway.sandbox.presentation.set(presentation)
            try:
                async with gateway.operations.execution(), asyncio.timeout_at(deadline):
                    result = await call_next(context)
            except TimeoutError:
                gateway.note_failure(TimeoutError())
                event(
                    gateway.logger,
                    "execution_timeout",
                    level=logging.WARNING,
                    request_id=request_id,
                    tool="execute",
                    outcome="unknown",
                    error_category="timeout",
                )
                result = ToolResult(
                    content=(
                        "Execution timed out; dispatched call outcomes are unknown. Do not replay."
                    ),
                    is_error=True,
                )
            except asyncio.CancelledError:
                gateway.note_failure(asyncio.CancelledError())
                event(
                    gateway.logger,
                    "execution_cancelled",
                    level=logging.WARNING,
                    request_id=request_id,
                    tool="execute",
                    outcome="unknown",
                    error_category="cancelled",
                )
                task = asyncio.current_task()
                if task in gateway.operations.draining:
                    gateway.operations.draining.discard(task)
                    assert task is not None
                    task.uncancel()
                    raise ToolError(
                        "Execution cancelled; dispatched call outcomes are unknown. Do not replay."
                    ) from None
                raise
            except ToolError as exc:
                gateway.note_failure(exc, fallback="config")
                result = ToolResult(content=gateway.redact(str(exc)), is_error=True)
            finally:
                gateway.deadline.reset(deadline_token)
                gateway.catalog_memo.reset(memo_token)
                gateway.sandbox.presentation.reset(presentation_token)
            event(
                gateway.logger,
                "execution_completed",
                level=logging.DEBUG,
                request_id=request_id,
                tool="execute",
                duration=time.monotonic() - start,
                outcome="error" if result.is_error else "success",
            )
            if result.is_error and gateway.failure_context.get():
                result = result.model_copy(
                    update={
                        "meta": {**(result.meta or {}), "onetool": gateway.failure_context.get()}
                    }
                )
            result = gateway.sandbox.compose(gateway.sanitize_error(result), presentation)
            result = gateway.protect_result(result)
            presentation.value = gateway.protect_value(presentation.value)
            bounded = gateway.results.bound(result, native=presentation.value)
            if bounded is not result:
                return bounded  # Reuse the first receipt/error; never retain the same result twice.
            rendered = gateway.protect_result(gateway.sandbox.render(bounded, presentation))
            if presentation.format != "json" and len(encoded(rendered)) > gateway.results.cap:
                return gateway.results.bound(result, force=True, native=presentation.value)
            return rendered
        finally:
            gateway.request_id.reset(token)
            gateway.failure_context.reset(failure_token)


class Gateway:
    def __init__(self, config: LoadedConfig, logger: logging.Logger, redact: Redactor):
        self.config = config
        self.logger = logger
        self.redact = redact
        self.start_time = datetime.now(UTC).isoformat()
        self.revision = 1
        self.deadline: ContextVar[float | None] = ContextVar("execution_deadline", default=None)
        self.request_id: ContextVar[str] = ContextVar("request_id", default="-")
        self.failure_context: ContextVar[dict[str, str] | None] = ContextVar(
            "failure_context", default=None
        )
        self.last_failure: dict[str, str] | None = None
        self.catalog_allowed: ContextVar[bool] = ContextVar("catalog_allowed", default=False)
        self.catalog_memo: ContextVar[dict[str, Sequence[Tool]] | None] = ContextVar(
            "catalog_memo", default=None
        )
        self.results = ResultFiles(
            logger, config.model.execution.max_output_bytes, protect=self.protect_value
        )
        self.operations = Operations(self)
        self.backends = self.build_backends(config)
        self.sandbox = OneToolSandbox(self)
        from onetool.discovery import Discovery

        self.discovery = Discovery(self)
        from onetool.preflight import Preflight

        self.preflight = Preflight(self)
        execution = config.model.execution
        code = FastMCP(
            "tools",
            providers=[Catalog(self)],
            transforms=[
                CodeMode(
                    sandbox_provider=self.sandbox,
                    discovery_tools=[
                        Search(),
                        GetSchemas(),
                        self.discovery.factory,
                        self.preflight.factory,
                    ],
                    max_tool_calls=execution.max_tool_calls,
                    wall_clock_timeout_secs=execution.timeout_seconds,
                )
            ],
        )
        code.provider_error_strategy = "raise"
        self.server = FastMCP(
            "OneTool",
            version=__version__,
            instructions=self.instructions(),
            lifespan=self.lifespan,
            middleware=[GatewayCalls(self)],
        )
        self.server.provider_error_strategy = "raise"
        self.server.mount(code)
        self.server.tool(self.status, name="onetool_status")
        self.server.tool(self.reload, name="onetool_reload")
        self.server.tool(self.servers, name="onetool_servers")
        self.server.tool(self.result_action, name="onetool_results")

    def note_failure(self, exc: BaseException, *, fallback: str = "unavailable") -> dict[str, str]:
        data = failure_details(exc, fallback=fallback)
        self.last_failure = data
        context = self.failure_context.get()
        if context is not None:
            context.update(data)
        return data

    def variable_snapshots(self) -> list[Any]:
        snapshots = [self.config.variables]
        snapshots.extend(
            backend.loaded_config.variables for backend in getattr(self, "backends", {}).values()
        )
        return [snapshot for snapshot in snapshots if snapshot is not None]

    def refresh_redaction(self) -> None:
        values = set(self.config.secret_values)
        for snapshot in self.variable_snapshots():
            values.update(snapshot.masks)
        self.redact.values = tuple(sorted(values, key=len, reverse=True))

    def protect_value(self, value: Any) -> Any:
        protected = {
            secret for snapshot in self.variable_snapshots() for secret in snapshot.protected
        }
        if not protected:
            return value
        redact = Redactor(tuple(sorted(protected, key=len, reverse=True)))

        def clean(item: Any) -> Any:
            if isinstance(item, str):
                return redact(item)
            if isinstance(item, list):
                return [clean(part) for part in item]
            if isinstance(item, dict):
                handle = item.get("handle")
                owned = isinstance(handle, str) and handle in self.results.entries
                return {
                    clean(key): (
                        part if owned and key in {"handle", "path", "sha256"} else clean(part)
                    )
                    for key, part in item.items()
                }
            return item

        return clean(value)

    def protect_result(self, result: ToolResult) -> ToolResult:
        return result.model_copy(
            update={
                "content": [
                    block.model_copy(update={"text": self.protect_value(block.text)})
                    if isinstance(block, mt.TextContent)
                    else block
                    for block in result.content
                ],
                "structured_content": self.protect_value(result.structured_content),
                "meta": self.protect_value(result.meta),
            }
        )

    def instructions(self) -> str:
        text = self.config.model.instructions
        sections = [
            f"## {name}\n{server.instructions}"
            for name, server in self.config.model.servers.items()
            if server.enabled and server.instructions
        ]
        return cast(
            str,
            self.protect_value(
                text
                + ("\n\nMCP Server Instructions\n\n" + "\n\n".join(sections) if sections else "")
            ),
        )

    def build_backends(self, config: LoadedConfig) -> dict[str, Backend]:
        return {name: Backend(self, name, server) for name, server in config.model.servers.items()}

    @asynccontextmanager
    async def lifespan(self, server: FastMCP[Any]) -> AsyncIterator[None]:
        event(self.logger, "gateway_started")
        try:
            yield
        finally:
            self.operations.accepting = False
            try:
                async with asyncio.timeout(5):
                    await self.close_backends()
            finally:
                self.results.close()
                event(self.logger, "gateway_stopped")

    async def close_backends(self) -> None:
        await asyncio.gather(*(backend.close() for backend in self.backends.values()))

    def sanitize_error(self, result: ToolResult) -> ToolResult:
        if not result.is_error:
            return result

        # Error text can contain configured credential values supplied by a backend.
        def clean(value: Any) -> Any:
            if isinstance(value, str):
                return self.redact(value)
            if isinstance(value, list):
                return [clean(item) for item in value]
            if isinstance(value, dict):
                return {self.redact(key): clean(item) for key, item in value.items()}
            return value

        content = [
            block.model_copy(update={"text": self.redact(block.text)})
            if isinstance(block, mt.TextContent)
            else block
            for block in result.content
        ]
        return result.model_copy(
            update={
                "content": content,
                "structured_content": clean(result.structured_content),
                "meta": clean(result.meta),
            }
        )

    async def status(self, check: str | None = None) -> dict[str, Any]:
        """Report runtime/config/availability and lazy cached sandbox import probes."""
        imports = await self.sandbox.probe_imports(
            [check]
            if check
            else [
                "json",
                "re",
                "datetime",
                "csv",
                "collections",
                "itertools",
                "math",
                "statistics",
                "base64",
                "hashlib",
                "difflib",
                "textwrap",
                "html",
                "urllib.parse",
                "uuid",
                "functools",
                "operator",
                "string",
                "typing",
                "dataclasses",
                "decimal",
                "random",
                "time",
                "zoneinfo",
                "copy",
                "heapq",
                "bisect",
                "enum",
                "fractions",
                "asyncio",
            ]
        )
        return self.status_snapshot(imports)

    def status_snapshot(self, imports: dict[str, bool] | None = None) -> dict[str, Any]:
        warnings = [
            f"{name}: {warning}"
            for name, backend in self.backends.items()
            for warning in backend.warnings
        ]
        warnings.extend(
            f"{name}: {backend.state}; use onetool_servers status/enable"
            for name, backend in self.backends.items()
            if backend.enabled and backend.state != "ready"
        )
        data = {
            "state": "degraded"
            if any(b.enabled and b.state != "ready" for b in self.backends.values())
            else "ok",
            "warnings": warnings,
            "last_failure": self.last_failure,
            "sandbox": {
                "imports": imports or dict(self.sandbox.import_cache),
                "unsupported_syntax": ["generators/yield"],
                "limits": {**self.config.model.execution.model_dump(), "max_memory": 100_000_000},
            },
            "runtime": {
                "onetool": __version__,
                "fastmcp": version("fastmcp"),
                "mcp": version("mcp"),
                "python": platform.python_version(),
                "os": platform.system(),
                "architecture": platform.machine(),
                "mode": "frozen" if getattr(sys, "frozen", False) else "source",
                "executable": sys.executable,
                "config": str(self.config.path),
                "pid": os.getpid(),
                "start_time": self.start_time,
                "config_revision": self.revision,
            },
            "servers": {
                name: {
                    "transport": backend.config.transport,
                    "configured_enabled": backend.config.enabled,
                    "session_enabled": backend.enabled,
                    "state": backend.state,
                    "tool_count": backend.tool_count,
                    "last_error": backend.last_error,
                    "description": backend.config.description,
                    "source": backend.config.source,
                    "instructions": backend.native_instructions,
                    "warnings": backend.warnings,
                    "instructions_truncated": backend.instructions_truncated,
                    "failure": backend.failure_info,
                }
                for name, backend in self.backends.items()
            },
            "config": {
                "execution": self.config.model.execution.model_dump(),
                "logging": self.config.model.logging.model_dump(),
                "server_timeouts": {
                    name: backend.config.timeout_seconds for name, backend in self.backends.items()
                },
                "environment": self.config.redacted_env(),
                "sources": [str(source) for source in self.config.sources],
                "server_sources": {
                    name: str(source) for name, source in self.config.server_sources.items()
                },
                "secrets_file": str(self.config.secrets_path) if self.config.secrets_path else None,
            },
        }

        return cast(dict[str, Any], self.protect_value(data))

    async def reload(self) -> dict[str, object]:
        """Validate config and reset all upstream state. Execution/logging require restart."""
        return await self.operations.reload()

    async def result_action(
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
        """Read/search/query or manage only this process's owned result handles."""
        data = await self.results.action(
            action,
            handle,
            value=value,
            source=source,
            offset=offset,
            limit=limit,
            tail=tail,
            pattern=pattern,
            context=context,
            case_sensitive=case_sensitive,
            timeout_seconds=timeout_seconds,
            expression=expression,
            select=select,
        )

        return self.results.fit(cast(dict[str, Any], self.protect_value(data)))

    async def servers(self, action: str, name: str | None = None) -> dict[str, Any]:
        """List/status configured servers or enable/disable/restart one for this session."""
        return await self.operations.servers(action, name)


def serve(config: LoadedConfig) -> None:
    with logging_context(config) as (logger, redact):
        gateway = Gateway(config, logger, redact)
        gateway.server.run(transport="stdio", show_banner=False, log_level="CRITICAL")
