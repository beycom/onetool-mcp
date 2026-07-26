"""Proxy result-conversion, thread-safety, and cancel tests (p12 core-flow-hardening).

Covers EmbeddedResource handling and structured fallback (D12), restrained JSON
coercion (D13), list_tools snapshot-under-lock (D15), and future.cancel() on the
sync-call timeout path (D-c1).
"""

from __future__ import annotations

import concurrent.futures
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

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


@pytest.mark.unit
@pytest.mark.core
class TestConnectErrorSanitization:
    """p14: connect-error strings are scrubbed of credential material before storage."""

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
