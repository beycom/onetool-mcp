"""Request-scoped proxy elicitation forwarding tests."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, Context, FastMCP
from fastmcp.tools import ToolResult
from mcp import types

if TYPE_CHECKING:
    from collections.abc import Iterator

from ot.proxy.manager import (
    _CURRENT_PROXY_REQUEST,
    ProxyManager,
    ProxyRequestContext,
    _ProxyCallContext,
    bind_proxy_request_context,
)


def _root_context(
    *,
    form: bool = False,
    url: bool = False,
    advertised: bool = True,
    result: types.ElicitResult | None = None,
    request_id: str = "root-request",
) -> tuple[MagicMock, MagicMock]:
    elicitation = (
        types.ElicitationCapability(
            form=types.FormElicitationCapability() if form else None,
            url=types.UrlElicitationCapability() if url else None,
        )
        if advertised
        else None
    )
    session = MagicMock()
    session.client_params = types.InitializeRequestParams(
        protocolVersion="2025-06-18",
        capabilities=types.ClientCapabilities(elicitation=elicitation),
        clientInfo=types.Implementation(name="test-client", version="1"),
    )
    response = result or types.ElicitResult(action="cancel")
    session.elicit_form = AsyncMock(return_value=response)
    session.elicit_url = AsyncMock(return_value=response)

    request_context = MagicMock()
    request_context.session = session
    request_context.request_id = request_id
    context = MagicMock()
    context.request_context = request_context
    return context, session


def _form_params() -> types.ElicitRequestFormParams:
    return types.ElicitRequestFormParams(
        message="Choose an account",
        requestedSchema={
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    )


@contextmanager
def _active_call(
    manager: ProxyManager,
    root: MagicMock,
    *,
    server: str = "srv",
) -> Iterator[tuple[ProxyRequestContext, _ProxyCallContext]]:
    with bind_proxy_request_context(root) as binding:
        call_context = _ProxyCallContext(request=binding)
        manager._active_calls[server] = call_context
        try:
            yield binding, call_context
        finally:
            call_context.expire()
            if manager._active_calls.get(server) is call_context:
                manager._active_calls.pop(server)


@pytest.mark.unit
@pytest.mark.core
class TestProxyElicitationForwarding:
    """Standard form and URL outcomes cross the proxy unchanged."""

    @pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
    async def test_form_outcomes_forwarded(self, action: str) -> None:
        content = {"account_id": "acct-1"} if action == "accept" else None
        root, session = _root_context(
            form=True,
            result=types.ElicitResult(action=action, content=content),
        )
        manager = ProxyManager()

        with _active_call(manager, root):
            result = await manager._forward_elicitation(
                "srv",
                "Choose an account",
                None,
                _form_params(),
                None,
            )

        assert result.action == action
        assert result.content == content
        session.elicit_form.assert_awaited_once_with(
            message="Choose an account",
            requestedSchema=_form_params().requestedSchema,
            related_request_id="root-request",
        )

    async def test_empty_capability_retains_legacy_form_support(self) -> None:
        root, session = _root_context(
            result=types.ElicitResult(
                action="accept",
                content={"account_id": "acct-1"},
            )
        )
        manager = ProxyManager()

        with _active_call(manager, root):
            result = await manager._forward_elicitation(
                "srv",
                "Choose an account",
                None,
                _form_params(),
                None,
            )

        assert result.action == "accept"
        session.elicit_form.assert_awaited_once()

    async def test_url_and_identifier_forwarded_unchanged(self) -> None:
        root, session = _root_context(
            url=True,
            result=types.ElicitResult(action="accept"),
        )
        params = types.ElicitRequestURLParams(
            message="Authorize access",
            url="https://auth.test/authorize",
            elicitationId="elicit-123",
        )
        manager = ProxyManager()

        with _active_call(manager, root):
            result = await manager._forward_elicitation(
                "srv",
                "Authorize access",
                None,
                params,
                None,
            )

        assert result.action == "accept"
        session.elicit_url.assert_awaited_once_with(
            message="Authorize access",
            url="https://auth.test/authorize",
            elicitation_id="elicit-123",
            related_request_id="root-request",
        )

    async def test_unsupported_mode_cancels_without_calling_client(self) -> None:
        root, session = _root_context(advertised=False)
        manager = ProxyManager()

        with _active_call(manager, root) as (_binding, call_context):
            result = await manager._forward_elicitation(
                "srv",
                "Choose an account",
                None,
                _form_params(),
                None,
            )

        assert result.action == "cancel"
        assert "does not support form elicitation" in (
            call_context.elicitation_unavailable_reason or ""
        )
        session.elicit_form.assert_not_awaited()

    async def test_forwarding_failure_cancels_without_hanging(self) -> None:
        root, session = _root_context(form=True)
        session.elicit_form.side_effect = RuntimeError("client disconnected")
        manager = ProxyManager()

        with _active_call(manager, root) as (_binding, call_context):
            result = await asyncio.wait_for(
                manager._forward_elicitation(
                    "srv",
                    "Choose an account",
                    None,
                    _form_params(),
                    None,
                ),
                timeout=1,
            )

        assert result.action == "cancel"
        assert "client disconnected" in (
            call_context.elicitation_unavailable_reason or ""
        )

    async def test_real_client_receive_loop_forwards_to_active_root(self) -> None:
        manager = ProxyManager()
        root, session = _root_context(
            form=True,
            result=types.ElicitResult(
                action="accept",
                content={"value": "acct-1"},
            ),
        )
        upstream = FastMCP("elicitation-upstream")

        @upstream.tool
        async def choose_account(ctx: Context) -> str:
            response = await ctx.elicit("Choose an account", response_type=str)
            return response.data if response.action == "accept" else response.action

        client = Client(
            upstream,
            elicitation_handler=manager._elicitation_handler_for("srv"),
        )
        manager._clients["srv"] = client

        with bind_proxy_request_context(root) as binding:
            async with client:
                result = await manager.call_tool(
                    "srv",
                    "choose_account",
                    {},
                    request_context=binding,
                )

        assert result == "acct-1"
        session.elicit_form.assert_awaited_once()

    async def test_concurrent_protocol_calls_do_not_cross_route(self) -> None:
        manager = ProxyManager()
        root_a, session_a = _root_context(
            form=True,
            result=types.ElicitResult(action="accept", content={"value": "a"}),
            request_id="request-a",
        )
        root_b, session_b = _root_context(
            form=True,
            result=types.ElicitResult(action="accept", content={"value": "b"}),
            request_id="request-b",
        )
        upstream = FastMCP("concurrent-elicitation-upstream")

        @upstream.tool
        async def choose_account(label: str, ctx: Context) -> str:
            response = await ctx.elicit(
                f"Choose account for {label}",
                response_type=str,
            )
            return response.data if response.action == "accept" else response.action

        client = Client(
            upstream,
            elicitation_handler=manager._elicitation_handler_for("srv"),
        )
        manager._clients["srv"] = client
        request_a = root_a.request_context
        request_b = root_b.request_context
        binding_a = ProxyRequestContext(
            session=request_a.session,
            request_id=request_a.request_id,
        )
        binding_b = ProxyRequestContext(
            session=request_b.session,
            request_id=request_b.request_id,
        )

        async with client:
            results = await asyncio.gather(
                manager.call_tool(
                    "srv",
                    "choose_account",
                    {"label": "A"},
                    request_context=binding_a,
                ),
                manager.call_tool(
                    "srv",
                    "choose_account",
                    {"label": "B"},
                    request_context=binding_b,
                ),
            )

        assert results == ["a", "b"]
        assert (
            session_a.elicit_form.await_args.kwargs["related_request_id"] == "request-a"
        )
        assert (
            session_b.elicit_form.await_args.kwargs["related_request_id"] == "request-b"
        )

    async def test_real_client_error_after_cancel_recommends_explicit_args(
        self,
    ) -> None:
        manager = ProxyManager()
        root, _session = _root_context(
            form=True,
            result=types.ElicitResult(action="cancel"),
        )
        upstream = FastMCP("error-elicitation-upstream")

        @upstream.tool
        async def choose_account(ctx: Context) -> ToolResult:
            response = await ctx.elicit("Choose an account", response_type=str)
            assert response.action == "cancel"
            return ToolResult(
                content="account selection required",
                is_error=True,
            )

        client = Client(
            upstream,
            elicitation_handler=manager._elicitation_handler_for("srv"),
        )
        manager._clients["srv"] = client

        with bind_proxy_request_context(root) as binding:
            async with client:
                with pytest.raises(RuntimeError) as exc_info:
                    await manager.call_tool(
                        "srv",
                        "choose_account",
                        {},
                        request_context=binding,
                    )

        error = str(exc_info.value)
        assert "account selection required" in error
        assert "explicitly" in error


@pytest.mark.unit
@pytest.mark.core
class TestProxyElicitationLifetime:
    """Execution context expires with run and is omitted from detached calls."""

    async def test_expired_request_cancels_without_client_interaction(self) -> None:
        root, session = _root_context(form=True)
        request_context = root.request_context
        binding = ProxyRequestContext(
            session=request_context.session,
            request_id=request_context.request_id,
        )
        binding.expire()
        call_context = _ProxyCallContext(request=binding)
        manager = ProxyManager()
        manager._active_calls["srv"] = call_context
        try:
            result = await manager._forward_elicitation(
                "srv",
                "Choose an account",
                None,
                _form_params(),
                None,
            )
        finally:
            call_context.expire()
            manager._active_calls.pop("srv")

        assert result.action == "cancel"
        session.elicit_form.assert_not_awaited()

    async def test_worker_thread_receives_bound_request_context(self) -> None:
        from ot.executor.runner import execute_command

        root, _session = _root_context(form=True)
        with bind_proxy_request_context(root) as binding:

            def probe() -> bool:
                return _CURRENT_PROXY_REQUEST.get() is binding

            with (
                patch(
                    "ot.executor.runner.load_tool_registry", return_value=MagicMock()
                ),
                patch(
                    "ot.executor.runner.build_execution_namespace",
                    return_value={"probe": probe},
                ),
            ):
                result = await execute_command(
                    "probe()",
                    prepared_code="probe()",
                    skip_validation=True,
                )

        assert result.success is True
        assert result.raw is True

    def test_fire_and_forget_omits_request_context(self) -> None:
        manager = ProxyManager()
        manager._loop = MagicMock()
        manager.call_tool = AsyncMock()
        future = MagicMock()
        future.exception.return_value = None

        def schedule(coro, _loop):
            coro.close()
            return future

        root, _session = _root_context(form=True)
        with (
            bind_proxy_request_context(root),
            patch("asyncio.run_coroutine_threadsafe", side_effect=schedule),
        ):
            result = manager.call_tool_sync(
                "srv",
                "tool",
                {},
                timeout=1,
                fire_and_forget=True,
            )

        assert result == "started"
        assert manager.call_tool.call_args.kwargs["request_context"] is None

    async def test_failed_interactive_call_recommends_explicit_arguments(self) -> None:
        root, _session = _root_context(form=True)
        request_context = root.request_context
        binding = ProxyRequestContext(
            session=request_context.session,
            request_id=request_context.request_id,
        )
        client = MagicMock()
        upstream_result = MagicMock()
        upstream_result.content = [
            types.TextContent(type="text", text="account selection required")
        ]
        upstream_result.is_error = True
        client.call_tool = AsyncMock(return_value=upstream_result)
        manager = ProxyManager()
        manager._clients["srv"] = client

        async def record_cancel_reason(*_args: object, **_kwargs: object) -> object:
            call_context = manager._active_calls["srv"]
            call_context.record_elicitation_unavailable("ended with a cancel response")
            return upstream_result

        client.call_tool.side_effect = record_cancel_reason

        with pytest.raises(RuntimeError, match="explicitly"):
            await manager.call_tool(
                "srv",
                "tool",
                {},
                request_context=binding,
            )

    async def test_elicitation_reason_does_not_leak_to_later_call(self) -> None:
        root, _session = _root_context(form=True)
        request_context = root.request_context
        binding = ProxyRequestContext(
            session=request_context.session,
            request_id=request_context.request_id,
        )
        failed_result = MagicMock(
            content=[types.TextContent(type="text", text="unrelated failure")],
            is_error=True,
        )
        successful_result = MagicMock(
            content=[types.TextContent(type="text", text="continued")],
            is_error=False,
        )
        client = MagicMock()
        client.call_tool = AsyncMock()
        manager = ProxyManager()
        manager._clients["srv"] = client

        async def first_call(*_args: object, **_kwargs: object) -> object:
            manager._active_calls["srv"].record_elicitation_unavailable(
                "ended with a decline response"
            )
            return successful_result

        client.call_tool.side_effect = first_call
        assert (
            await manager.call_tool(
                "srv",
                "first",
                {},
                request_context=binding,
            )
            == "continued"
        )

        client.call_tool.side_effect = None
        client.call_tool.return_value = failed_result
        with pytest.raises(RuntimeError) as exc_info:
            await manager.call_tool(
                "srv",
                "second",
                {},
                request_context=binding,
            )

        assert str(exc_info.value) == "unrelated failure"
