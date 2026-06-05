"""Tests for the __display__ runner dunder."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_execute_python_code_returns_display_flag() -> None:
    """The Python runner reads __display__ from the execution namespace."""
    from ot.executor.runner import execute_python_code

    text, raw, _sanitize, _fmt, _force_context, display = execute_python_code(
        '__display__ = True\n{"ok": True}',
        tool_functions={},
    )

    assert '"ok":true' in text
    assert raw == {"ok": True}
    assert display is True


@pytest.mark.unit
@pytest.mark.core
def test_execute_command_displays_pre_deflection_result() -> None:
    """__display__ writes the full result before ctx handle deflection."""
    from ot.executor.runner import execute_command

    cfg = SimpleNamespace(
        output=SimpleNamespace(max_inline_size=5, compact=False),
        security=SimpleNamespace(sanitize=SimpleNamespace(enabled=True)),
    )
    shown: list[dict[str, object]] = []

    def fake_show_message(**kwargs: object) -> dict[str, object]:
        shown.append(kwargs)
        return {"id": "display-1"}

    service = SimpleNamespace(
        output_policy_for=lambda _tool: SimpleNamespace(allow_deflect=True, allow_sanitize=True)
    )

    with (
        patch("ot.executor.runner.get_config", return_value=cfg),
        patch("ot.executor.runner.load_tool_registry"),
        patch("ot.executor.runner.build_execution_namespace", return_value={}),
        patch("ot.proxy.get_proxy_manager") as proxy_manager,
        patch("ot.services.get_services", return_value=service),
        patch("ot.executor.result_store.get_result_store") as result_store,
        patch("ot.display.service.show_message", side_effect=fake_show_message),
    ):
        proxy_manager.return_value.servers = {}
        stored = SimpleNamespace(handle="ctx_123", bytes=30)
        result_store.return_value.store.return_value = stored
        result_store.return_value.format_store_response.return_value = {"handle": "ctx_123"}
        result = asyncio.run(execute_command('__display__ = True\n{"long": "payload"}'))

    assert result.success is True
    assert result.raw == {"handle": "ctx_123"}
    assert shown[0]["kind"] == "json"
    assert shown[0]["content"] == {"long": "payload"}
