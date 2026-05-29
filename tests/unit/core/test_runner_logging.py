"""Unit tests for runner logging metadata."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_prepare_command_records_snippet_metadata() -> None:
    """Snippet preparation keeps original command separate from expanded code."""
    from ot.config import OneToolConfig, SnippetDef
    from ot.executor.runner import prepare_command

    config = OneToolConfig(
        snippets={
            "test_snip": SnippetDef(
                description="Test snippet",
                body='ot.help(query="{{ topic }}")',
            )
        }
    )

    with patch("ot.config.get_config", return_value=config):
        prepared = prepare_command(":test_snip topic=logging")

    assert prepared.error is None
    assert prepared.original == ":test_snip topic=logging"
    assert prepared.command_type == "snippet"
    assert prepared.snippet == "test_snip"
    assert prepared.code == "ot.help(query='logging')"
    assert prepared.prepared_lines == 1
    assert prepared.prepared_length == len(prepared.code)


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_execute_command_logs_original_snippet_command_not_expanded_code() -> None:
    """runner.execute INFO metadata uses request command, not expanded snippet code."""
    from ot.config import OneToolConfig, SnippetDef
    from ot.executor.runner import execute_command

    captured: dict[str, object] = {}

    class FakeSpan:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def __enter__(self) -> FakeSpan:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def add(self, key: str, value: object = None, **kwargs: object) -> None:
            captured[key] = value
            captured.update(kwargs)

    config = OneToolConfig(
        snippets={
            "test_snip": SnippetDef(
                description="Test snippet",
                body="__sanitize__ = False\n_g = ''\n_m = '{{ topic }}'\n42",
            )
        }
    )

    with (
        patch("ot.config.get_config", return_value=config),
        patch("ot.executor.runner.get_config", return_value=config),
        patch("ot.executor.runner.load_tool_registry", return_value={}),
        patch("ot.executor.runner.build_execution_namespace", return_value={}),
        patch("ot.proxy.get_proxy_manager", return_value=SimpleNamespace(servers={})),
        patch(
            "ot.services.get_services",
            return_value=SimpleNamespace(
                output_policy_for=lambda _tool: SimpleNamespace(
                    allow_deflect=False,
                    allow_sanitize=True,
                )
            ),
        ),
        patch(
            "ot.executor.runner.execute_python_code",
            return_value=("ok", "ok", True, "json", False),
        ),
        patch("ot.executor.runner.LogSpan", FakeSpan),
    ):
        result = await execute_command(":test_snip topic=logging")

    assert result.success is True
    assert captured["command"] == ":test_snip topic=logging"
    assert captured["commandType"] == "snippet"
    assert captured["snippet"] == "test_snip"
    assert captured["preparedLines"] == 4
    assert "_g" not in str(captured["command"])
    assert "_m" not in str(captured["command"])
