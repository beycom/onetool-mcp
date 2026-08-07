"""Proxy result-conversion, thread-safety, and cancel tests (p12 core-flow-hardening).

Covers EmbeddedResource handling and structured fallback (D12), restrained JSON
coercion (D13), list_tools snapshot-under-lock (D15), and future.cancel() on the
sync-call timeout path (D-c1).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import httpx
import pytest
from mcp import types
from mcp.shared.exceptions import McpError

from ot.proxy.manager import ProxyManager


def _text_content(text: str) -> MagicMock:
    part = MagicMock(spec=types.TextContent)
    part.text = text
    return part


def _tool_mock(name: str = "t") -> MagicMock:
    # `name` is a reserved Mock kwarg, so it must be assigned after construction.
    tool = MagicMock(spec=types.Tool)
    tool.name = name
    tool.description = "desc"
    tool.inputSchema = {}
    return tool


async def _call(manager: ProxyManager, result: object) -> object:
    client = MagicMock()
    client.call_tool = AsyncMock(return_value=result)
    manager._clients["srv"] = client
    return await manager.call_tool("srv", "tool", {}, timeout=5.0)


@pytest.mark.unit
@pytest.mark.core
class TestProxyResultConversion:
    """D12/D13: correct extraction of proxied results."""

    async def test_embedded_resource_text_surfaced(self) -> None:
        """D12: an EmbeddedResource payload is surfaced, not reported empty."""
        res = MagicMock(spec=types.EmbeddedResource)
        res.resource = MagicMock()
        res.resource.text = "embedded payload"
        result = MagicMock()
        result.content = [res]
        assert await _call(ProxyManager(), result) == "embedded payload"

    async def test_structured_content_fallback(self) -> None:
        """D12: empty content falls back to structured_content."""
        result = MagicMock()
        result.content = []
        result.structured_content = {"key": "value"}
        assert await _call(ProxyManager(), result) == {"key": "value"}

    async def test_plain_string_not_coerced(self) -> None:
        """D13: '007' stays the string '007', not the int 7."""
        result = MagicMock()
        result.content = [_text_content("007")]
        assert await _call(ProxyManager(), result) == "007"

    async def test_json_array_still_parsed(self) -> None:
        """D13: text that structurally looks like JSON is still parsed."""
        result = MagicMock()
        result.content = [_text_content("[1,2]")]
        assert await _call(ProxyManager(), result) == [1, 2]

    async def test_json_object_still_parsed(self) -> None:
        result = MagicMock()
        result.content = [_text_content('{"a":1}')]
        assert await _call(ProxyManager(), result) == {"a": 1}

    async def test_binary_content_marker_preserved(self) -> None:
        content = MagicMock()
        content.data = b"binary"
        result = MagicMock()
        result.content = [content]
        assert await _call(ProxyManager(), result) == "[Binary content: MagicMock]"

    async def test_upstream_error_raises_with_text_intact(self) -> None:
        result = MagicMock()
        result.content = [_text_content("missing required account_id")]
        result.is_error = True

        with pytest.raises(RuntimeError, match="missing required account_id"):
            await _call(ProxyManager(), result)


@pytest.mark.unit
@pytest.mark.core
class TestListToolsThreadSafety:
    """D15: list_tools(server=None) is safe under concurrent mutation."""

    def test_no_dict_changed_size_error(self) -> None:
        manager = ProxyManager()
        tool = _tool_mock()
        for i in range(5):
            manager._tools_by_server[f"s{i}"] = [tool]

        errors: list[BaseException] = []
        stop = threading.Event()

        def mutate() -> None:
            i = 0
            while not stop.is_set():
                with manager._mutation_lock:
                    manager._tools_by_server[f"x{i % 20}"] = [tool]
                    manager._tools_by_server.pop(f"x{(i + 5) % 20}", None)
                i += 1

        def read() -> None:
            try:
                for _ in range(200):
                    manager.list_tools()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        mutator = threading.Thread(target=mutate)
        mutator.start()
        try:
            read()
        finally:
            stop.set()
            mutator.join()

        assert errors == []


@pytest.mark.unit
@pytest.mark.core
class TestCallToolSyncCancel:
    """D-c1: the scheduled coroutine is cancelled when the sync wait times out."""

    def test_future_cancelled_on_timeout(self) -> None:
        manager = ProxyManager()
        manager._loop = MagicMock()
        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        def _fake_schedule(coro, loop):  # noqa: ANN001, ANN202
            coro.close()  # avoid "coroutine was never awaited" warning
            return mock_future

        with patch("asyncio.run_coroutine_threadsafe", side_effect=_fake_schedule):
            with pytest.raises(concurrent.futures.TimeoutError):
                manager.call_tool_sync("srv", "tool", {}, timeout=1.0)

        mock_future.cancel.assert_called_once()

    @pytest.mark.parametrize("operation", ["resources", "prompts"])
    def test_discovery_future_cancelled_on_timeout(self, operation: str) -> None:
        manager = ProxyManager()
        manager._loop = MagicMock()
        manager._loop.is_running.return_value = True
        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        def _fake_schedule(coro, loop):  # noqa: ANN001, ANN202
            coro.close()
            return mock_future

        with patch("asyncio.run_coroutine_threadsafe", side_effect=_fake_schedule):
            with pytest.raises(concurrent.futures.TimeoutError):
                if operation == "resources":
                    manager.list_resources_sync("srv", timeout=1.0)
                else:
                    manager.list_prompts_sync("srv", timeout=1.0)

        mock_future.cancel.assert_called_once()

    def test_connect_timeout_invalidates_generation_and_cancels(self) -> None:
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        manager._loop = MagicMock()
        manager._loop.is_running.return_value = True
        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        def _fake_schedule(coro, loop):  # noqa: ANN001, ANN202
            coro.close()
            return mock_future

        config = McpServerConfig(type="stdio", command="uvx")
        with patch("asyncio.run_coroutine_threadsafe", side_effect=_fake_schedule):
            with pytest.raises(concurrent.futures.TimeoutError):
                manager.connect_additional_sync("srv", config)

        assert manager._server_generations["srv"] > 0
        mock_future.cancel.assert_called_once()


@pytest.mark.unit
@pytest.mark.core
class TestCallToolDeadlines:
    """One tool deadline covers gate waiting and downstream execution."""

    @pytest.mark.asyncio
    async def test_timeout_while_waiting_for_call_gate(self) -> None:
        manager = ProxyManager()
        client = MagicMock()
        client.call_tool = AsyncMock()
        manager._clients["srv"] = client
        lock = asyncio.Lock()
        await lock.acquire()
        manager._call_locks["srv"] = lock

        try:
            with pytest.raises(TimeoutError, match="timed out"):
                await manager.call_tool("srv", "tool", timeout=0.01)
        finally:
            lock.release()

        client.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_timeout_cancels_downstream_request(self) -> None:
        manager = ProxyManager()
        started = asyncio.Event()
        cancelled = asyncio.Event()
        client = MagicMock()

        async def blocked_call(*_args: object, **_kwargs: object) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        client.call_tool = AsyncMock(side_effect=blocked_call)
        manager._clients["srv"] = client

        with pytest.raises(TimeoutError, match="timed out"):
            await manager.call_tool("srv", "tool", timeout=0.01)

        assert started.is_set()
        assert cancelled.is_set()
        client.call_tool.assert_awaited_once()

    def test_oauth_connect_timeout_includes_callback_and_cleanup(self) -> None:
        from ot.proxy.manager import (
            OAUTH_CALLBACK_TIMEOUT_SECONDS,
            RUNTIME_CONNECT_TIMEOUT_SECONDS,
            TIMEOUT_CLEANUP_MARGIN_SECONDS,
        )

        assert OAUTH_CALLBACK_TIMEOUT_SECONDS == 300.0
        assert RUNTIME_CONNECT_TIMEOUT_SECONDS == (
            OAUTH_CALLBACK_TIMEOUT_SECONDS + TIMEOUT_CLEANUP_MARGIN_SECONDS
        )

    @pytest.mark.asyncio
    async def test_sync_discovery_rejects_owner_loop_without_blocking(self) -> None:
        manager = ProxyManager()
        manager._loop = asyncio.get_running_loop()

        with pytest.raises(RuntimeError, match="Cannot synchronously wait"):
            manager.list_resources_sync("srv", timeout=1.0)


@pytest.mark.unit
@pytest.mark.core
class TestConnectErrorSanitization:
    """p14: connect-error strings are scrubbed of credential material before storage."""

    @pytest.mark.parametrize(
        ("message", "sentinels"),
        [
            (
                'request failed: Authorization: "Bearer quoted-auth-sentinel"',
                ("quoted-auth-sentinel",),
            ),
            (
                "request failed: aUtHoRiZaTiOn='Basic mixed-case-sentinel'",
                ("mixed-case-sentinel",),
            ),
            (
                "request failed: Bearer bare-bearer-sentinel",
                ("bare-bearer-sentinel",),
            ),
            (
                'oauth: {"access_token":"access-sentinel",'
                '"refresh_token":"refresh-sentinel","id_token":"id-sentinel",'
                '"client_secret":"client-sentinel"}',
                (
                    "access-sentinel",
                    "refresh-sentinel",
                    "id-sentinel",
                    "client-sentinel",
                ),
            ),
            (
                "oauth: token=form-token-sentinel&X-API-Key=api-key-sentinel&status=401",
                ("form-token-sentinel", "api-key-sentinel"),
            ),
        ],
    )
    def test_credential_forms_are_redacted(
        self, message: str, sentinels: tuple[str, ...]
    ) -> None:
        from ot.proxy.manager import _sanitize_connect_error

        output = _sanitize_connect_error(message)

        assert all(sentinel not in output for sentinel in sentinels)

    def test_bearer_token_redacted(self) -> None:
        from ot.proxy.manager import _sanitize_connect_error

        msg = "connection failed: Authorization: Bearer sk-secret123 rejected"
        out = _sanitize_connect_error(msg)
        assert "sk-secret123" not in out
        assert "connection failed" in out

    def test_raw_shape_token_redacted_without_keyword(self) -> None:
        """A bare secret-shaped literal (no authorization/bearer/token keyword nearby)
        must still be caught by the redact_secrets() shape-based first pass."""
        from ot.proxy.manager import _sanitize_connect_error

        msg = "connection failed: upstream rejected sk-abc123def456ghi789jklmno"
        out = _sanitize_connect_error(msg)
        assert "sk-abc123def456ghi789jklmno" not in out
        assert "connection failed" in out

    def test_keyword_form_still_redacted(self) -> None:
        """Keyword-gated second pass still catches keyword-prefixed opaque tokens
        that the shape-based patterns don't recognize."""
        from ot.proxy.manager import _sanitize_connect_error

        msg = "connection failed: authorization: Bearer xyz rejected"
        out = _sanitize_connect_error(msg)
        assert "xyz" not in out
        assert "connection failed" in out

    def test_oauth_error_details_are_preserved(self) -> None:
        """OAuth status and structured error details are safe diagnostics."""
        from ot.proxy.manager import _sanitize_connect_error

        msg = (
            'Token exchange failed (400): {"error":"invalid_request",'
            '"error_description":"Client must not use multiple authentication methods"}'
        )

        assert _sanitize_connect_error(msg) == msg

    def test_structured_oauth_tokens_are_redacted_without_hiding_error(self) -> None:
        """Token values are removed while neighboring OAuth metadata remains."""
        from ot.proxy.manager import _sanitize_connect_error

        msg = (
            'OAuth failed: access_token="opaque-access", refresh_token="opaque-refresh", '
            'status=401, error="invalid_token"'
        )

        out = _sanitize_connect_error(msg)

        assert "opaque-access" not in out
        assert "opaque-refresh" not in out
        assert "status=401" in out
        assert 'error="invalid_token"' in out

    @pytest.mark.asyncio
    async def test_incremental_connect_uses_one_sanitized_error_everywhere(self) -> None:
        from ot.config.models import McpServerConfig

        sentinel = "opaque-connect-sentinel"
        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="uvx")

        with (
            patch.object(
                manager,
                "_connect_server",
                side_effect=RuntimeError(
                    f'provider rejected Authorization: "Bearer {sentinel}"'
                ),
            ),
            patch("ot.proxy.manager.logger.warning") as warning,
        ):
            result = await manager.connect_additional("secure", config)

        stored = manager.get_error("secure")
        logged = str(warning.call_args.args[0])
        assert stored is not None
        assert sentinel not in result
        assert sentinel not in stored
        assert sentinel not in logged
        assert result == f"failed: {stored}"

    @pytest.mark.asyncio
    async def test_startup_connect_logs_only_sanitized_error(self) -> None:
        from ot.config.models import McpServerConfig

        sentinel = "startup-token-sentinel"
        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="uvx")

        with (
            patch.object(
                manager,
                "_create_client",
                side_effect=RuntimeError(f"access_token={sentinel}&status=401"),
            ),
            patch("ot.proxy.manager.logger.warning") as warning,
            patch("ot.logging.span.logger") as span_logger,
        ):
            await manager.connect({"secure": config})

        assert sentinel not in (manager.get_error("secure") or "")
        assert sentinel not in str(warning.call_args.args[0])
        assert sentinel not in str(span_logger.opt.return_value.error.call_args.args[0])


@pytest.mark.unit
@pytest.mark.core
class TestTerminalConnectionRetirement:
    """Terminal call failures retire only their exact connection generation."""

    @staticmethod
    def _manager_with_client(error: BaseException) -> tuple[ProxyManager, MagicMock]:
        manager = ProxyManager()
        client = MagicMock()
        client.call_tool = AsyncMock(side_effect=error)
        client.__aexit__ = AsyncMock(return_value=None)
        client.transport = MagicMock()
        client.transport.close = AsyncMock(return_value=None)
        manager._clients["srv"] = client
        manager._tools_by_server["srv"] = [_tool_mock()]
        manager._server_generations["srv"] = 1
        return manager, client

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            anyio.ClosedResourceError(),
            EOFError("stdio ended"),
            httpx.RemoteProtocolError("peer closed connection"),
            RuntimeError("Server session was closed unexpectedly"),
            ExceptionGroup(
                "transport closed",
                [anyio.BrokenResourceError(), anyio.EndOfStream()],
            ),
        ],
    )
    async def test_terminal_failure_retires_once_without_retry(
        self, error: BaseException
    ) -> None:
        manager, client = self._manager_with_client(error)

        with (
            patch.object(manager, "_evict_proxy_caches") as evict,
            pytest.raises(type(error)),
        ):
            await manager.call_tool("srv", "tool")

        assert manager.get_connection("srv") is None
        assert manager.list_tools(server="srv") == []
        assert manager.get_error("srv")
        client.call_tool.assert_awaited_once()
        client.__aexit__.assert_awaited_once_with(None, None, None)
        client.transport.close.assert_awaited_once_with()
        evict.assert_called_once_with("srv")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("remote application failed"),
            McpError(types.ErrorData(code=-32000, message="application failed")),
            ExceptionGroup(
                "mixed",
                [anyio.ClosedResourceError(), ValueError("application failed")],
            ),
        ],
    )
    async def test_application_failure_keeps_connection(
        self, error: BaseException
    ) -> None:
        manager, client = self._manager_with_client(error)

        with pytest.raises(type(error)):
            await manager.call_tool("srv", "tool")

        assert manager.get_connection("srv") is client
        assert manager.get_error("srv") is None
        client.call_tool.assert_awaited_once()
        client.__aexit__.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_error_result_keeps_connection(self) -> None:
        manager, client = self._manager_with_client(RuntimeError("unused"))
        result = MagicMock()
        result.content = [_text_content("application failed")]
        result.is_error = True
        client.call_tool.side_effect = None
        client.call_tool.return_value = result

        with pytest.raises(RuntimeError, match="application failed"):
            await manager.call_tool("srv", "tool")

        assert manager.get_connection("srv") is client
        client.call_tool.assert_awaited_once()
        client.__aexit__.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_terminal_failure_cannot_retire_replacement(self) -> None:
        manager = ProxyManager()
        started = asyncio.Event()
        release = asyncio.Event()
        old_client = MagicMock()

        async def fail_after_replacement(*_args: object, **_kwargs: object) -> None:
            started.set()
            await release.wait()
            raise anyio.ClosedResourceError

        old_client.call_tool = AsyncMock(side_effect=fail_after_replacement)
        old_client.__aexit__ = AsyncMock(return_value=None)
        old_client.transport = None
        new_client = MagicMock()
        manager._clients["srv"] = old_client
        manager._server_generations["srv"] = 1

        call = asyncio.create_task(manager.call_tool("srv", "tool"))
        await started.wait()
        manager._clients["srv"] = new_client
        manager._server_generations["srv"] = 2
        release.set()

        with pytest.raises(anyio.ClosedResourceError):
            await call
        assert manager.get_connection("srv") is new_client
        assert manager.get_error("srv") is None
        old_client.__aexit__.assert_not_awaited()
