from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_pack_topics_render_dynamic_resource_and_adapter_content() -> None:
    from ot.meta import help

    workflow = help(query="file", topic="workflow")
    setup = help(query="mem", topic="setup")
    config = help(query="mem", topic="config")
    dsl = help(query="whiteboard", topic="dsl")
    policy = help(query="diagram", topic="policy")

    assert "# File workflow" in workflow
    assert "ot.help(query='file', topic='setup')" in workflow
    assert "## Safety and side effects" in workflow
    assert "## Verification and recovery" in workflow
    assert "# mem setup" in setup
    assert "This report is read-only" in setup
    assert "# mem config" in config
    assert "Redacted active values" in config
    assert "node" in dsl.lower()
    assert "diagram" in policy.lower()


def test_packaged_whiteboard_topic_is_utf8_and_available_from_package() -> None:
    from importlib.resources import files

    from ot.meta import help

    resource = files("otdev.tools._excalidraw").joinpath("dsl-reference.md")
    packaged = resource.read_text(encoding="utf-8")
    rendered = help(query="whiteboard", topic="dsl")

    assert rendered == packaged
    assert "## Draw DSL" in rendered


def test_every_stable_pack_has_standard_topic_inventory() -> None:
    from ot.catalog import PACK_CATALOG, PackStability

    for pack in PACK_CATALOG:
        if pack.stability is not PackStability.STABLE:
            continue
        names = [topic.name for topic in pack.topics]
        assert names[:4] == ["overview", "workflow", "setup", "config"]
        assert len(names) == len(set(names))


def test_unknown_pack_topic_lists_valid_topics() -> None:
    from ot.meta import help

    with pytest.raises(
        ValueError,
        match=r"Unknown topic 'missing'.*Valid topics: overview, workflow, setup, config",
    ):
        help(query="file", topic="missing")


def test_generic_proxy_setup_is_schema_driven_and_has_no_presets() -> None:
    from ot.meta import help

    result = help(query="proxy", topic="setup")

    assert "McpServerConfig schema" in result
    assert '"type"' in result
    assert "no server-specific preset catalog" in result
    assert "authoritative MCP documentation" in result
    assert "enabled: false" in result


def test_answer_only_requires_ask_and_returns_narrowed_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ot.meta import help

    with pytest.raises(ValueError, match="requires a non-empty ask"):
        help(query="file", answer_only=True)

    monkeypatch.setattr("ot.config.get_secret", lambda _name: "")
    result = help(
        query="file",
        topic="workflow",
        ask="What should I do first?",
        answer_only=True,
    )

    assert result.startswith("## Ask Unavailable")
    assert "## Narrowed Deterministic Help" in result
    assert "# File workflow" in result


def test_answer_only_success_omits_deterministic_context() -> None:
    from ot.meta import help

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Use ot.status()."))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    llm = MagicMock(base_url="https://api.openai.com/v1", model="gpt-test", max_tokens=100)

    with (
        patch("ot.config.get_secret", return_value="configured"),
        patch("ot.config.get_llm_config", return_value=llm),
        patch("openai.OpenAI", return_value=client),
    ):
        result = help(
            query="ot",
            ask="Which operation checks status?",
            answer_only=True,
        )

    assert result == "Use ot.status()."
    assert "# ot pack" not in result


def test_ask_failure_redacts_exception_details() -> None:
    from ot.meta import help

    llm = MagicMock(
        base_url="https://api.openai.com/v1",
        model="gpt-test",
        max_tokens=100,
    )
    with (
        patch("ot.config.get_secret", return_value="configured"),
        patch("ot.config.get_llm_config", return_value=llm),
        patch(
            "openai.OpenAI",
            side_effect=RuntimeError("token=abcdefghijklmnop-private"),
        ),
    ):
        result = help(query="ot", ask="Which operation checks status?")

    assert "## Ask Unavailable" in result
    assert "private" not in result


def test_configured_server_topic_prefers_live_server_subject() -> None:
    from ot.config.models import McpServerConfig
    from ot.meta import help

    config = MagicMock()
    config.servers = {
        "file": McpServerConfig(
            type="http",
            enabled=False,
            headers={"Authorization": "${MCP_TOKEN}"},
        )
    }
    proxy = MagicMock()
    proxy.get_connection.return_value = None
    proxy.is_connecting = False
    proxy.get_server_instructions.return_value = ""

    with (
        patch("ot.meta._help.get_config", return_value=config),
        patch("ot.proxy.get_proxy_manager", return_value=proxy),
    ):
        result = help(query="file", topic="config")

    assert "# file server config" in result
    assert "**Status:** disabled" in result
    assert '"variable": "MCP_TOKEN"' in result
