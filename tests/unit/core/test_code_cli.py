"""CLI acceptance tests for direct-model harness commands."""

from __future__ import annotations

from unittest.mock import Mock, call, patch

import pytest
from typer.testing import CliRunner

from onetool.cli import app
from onetool.code.diagnostics import CodeStatus, ExecutableStatus
from onetool.code.proxy import DiscoveredModel

pytestmark = [pytest.mark.unit, pytest.mark.core]

runner = CliRunner()


def test_code_surface_contains_launchers_models_and_status_only() -> None:
    root = runner.invoke(app, ["--help"])
    code = runner.invoke(app, ["code", "--help"])

    assert root.exit_code == 0
    assert "code" in root.stdout
    assert " claude " not in root.stdout
    assert " codex " not in root.stdout
    assert code.exit_code == 0
    for command in ("claude", "codex", "models", "status"):
        assert command in code.stdout
    for removed in ("config", "doctor", "setup", "service", "login"):
        assert removed not in code.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("--continue",),
        ("exec", "--full-auto"),
        ("--unknown", "value", "-x"),
        ("--model", "other"),
        ("--", "literal", "--tail"),
    ],
)
def test_every_token_after_model_is_forwarded_verbatim(
    arguments: tuple[str, ...],
) -> None:
    with patch("onetool.cli_commands.code_app._launch") as launch:
        result = runner.invoke(
            app,
            ["code", "codex", "z-ai/glm-5.2", *arguments],
        )

    assert result.exit_code == 0
    assert launch.call_args.kwargs == {
        "harness": "codex",
        "model": "z-ai/glm-5.2",
        "context_window": None,
        "arguments": arguments,
    }


def test_context_before_model_is_owned_but_context_after_model_is_opaque() -> None:
    with patch("onetool.cli_commands.code_app._launch") as launch:
        result = runner.invoke(
            app,
            [
                "code",
                "codex",
                "--context",
                "372000",
                "sol",
                "--context",
                "other",
            ],
        )

    assert result.exit_code == 0
    assert launch.call_args.kwargs == {
        "harness": "codex",
        "model": "sol",
        "context_window": 372_000,
        "arguments": ("--context", "other"),
    }


def test_option_like_model_is_accepted_after_end_of_options() -> None:
    with patch("onetool.cli_commands.code_app._launch") as launch:
        result = runner.invoke(
            app,
            [
                "code",
                "codex",
                "--context",
                "auto",
                "--",
                "-vendor/model",
                "exec",
                "--full-auto",
            ],
        )

    assert result.exit_code == 0
    assert launch.call_args.kwargs == {
        "harness": "codex",
        "model": "-vendor/model",
        "context_window": None,
        "arguments": ("exec", "--full-auto"),
    }


def test_direct_codex_launch_explains_model_session_and_mcp_scope() -> None:
    discovery = Mock()
    discovery.models.return_value = (
        DiscoveredModel(id="gpt-5.6-sol", provider="openai"),
    )
    invocation = Mock()
    with (
        patch(
            "onetool.cli_commands.code_app.connection_from_environment",
            return_value=("http://proxy.test", "secret"),
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            return_value=discovery,
        ),
        patch(
            "onetool.cli_commands.code_app.build_invocation",
            return_value=invocation,
        ) as build,
        patch("onetool.cli_commands.code_app.replace_process") as replace,
    ):
        result = runner.invoke(app, ["code", "codex", "sol"])

    assert result.exit_code == 0
    output = result.stdout + result.stderr
    normalized_output = " ".join(output.split())
    assert "Resolved proxy model: gpt-5.6-sol" in output
    assert "Codex /model shows Codex's native catalog" in output
    assert "Change proxy models through 'onetool code'" in normalized_output
    assert "applies to new, resumed, and forked sessions" in normalized_output
    assert "Use plain 'codex' to preserve a saved session's native model" in (
        normalized_output
    )
    assert "if Codex reports interrupted servers" in normalized_output
    assert "use '/mcp' to verify the final state" in normalized_output
    build.assert_called_once_with(
        harness="codex",
        model="gpt-5.6-sol",
        proxy_origin="http://proxy.test",
        credential="secret",
        context_window=None,
        arguments=(),
    )
    replace.assert_called_once_with(invocation=invocation)


def test_model_is_required_and_help_documents_environment() -> None:
    missing = runner.invoke(app, ["code", "claude"])
    help_result = runner.invoke(app, ["code", "claude", "--help"])

    assert missing.exit_code == 2
    assert "MODEL" in (missing.stdout + missing.stderr)
    assert help_result.exit_code == 0
    output = help_result.stdout + help_result.stderr
    assert "CLIPROXY_BASE_URL" in output
    assert "CLIPROXY_INFERENCE_KEY" in output
    assert "verbatim" in output
    assert "--context" in output


def test_models_uses_one_live_inventory_without_loading_config() -> None:
    discovery = Mock()
    discovery.models.return_value = (
        DiscoveredModel(id="codex-oauth/gpt-5.6-luna", provider="openai"),
        DiscoveredModel(id="openrouter/z-ai/glm-5.2", provider=None),
    )
    with (
        patch(
            "onetool.cli_commands.code_app.connection_from_environment",
            return_value=("http://proxy.test", "secret"),
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            return_value=discovery,
        ) as factory,
    ):
        result = runner.invoke(app, ["code", "models"])

    assert result.exit_code == 0
    assert (result.stdout + result.stderr).splitlines() == [
        "MODEL                     PROVIDER",
        "codex-oauth/gpt-5.6-luna  openai",
        "openrouter/z-ai/glm-5.2   -",
    ]
    factory.assert_called_once_with(
        proxy_origin="http://proxy.test",
        credential="secret",
    )
    discovery.models.assert_called_once_with()


def test_bare_code_requires_tty_and_interactive_path_is_shared() -> None:
    with patch(
        "onetool.cli_commands.code_app._stdin_is_tty",
        return_value=False,
    ):
        non_tty = runner.invoke(app, ["code"])
    assert non_tty.exit_code == 2
    assert "interactive terminal" in (non_tty.stdout + non_tty.stderr)

    with (
        patch(
            "onetool.cli_commands.code_app._stdin_is_tty",
            return_value=True,
        ),
        patch("onetool.cli_commands.code_app._interactive_launch") as launch,
    ):
        interactive = runner.invoke(app, ["code"])
    assert interactive.exit_code == 0
    launch.assert_called_once_with()


def test_interactive_launch_sorts_models_and_prints_reusable_command() -> None:
    discovery = Mock()
    discovery.models.return_value = (
        DiscoveredModel(id="Z-AI/glm-5.2", provider="openrouter"),
        DiscoveredModel(id="-vendor/model with space", provider=None),
        DiscoveredModel(id="gpt-5.6-sol", provider="openai"),
    )
    harness_prompt = Mock()
    harness_prompt.ask.return_value = "codex"
    context_prompt = Mock()
    context_prompt.ask.return_value = "1m"
    model_prompt = Mock()
    model_prompt.ask.return_value = "-vendor/model with space"
    with (
        patch(
            "onetool.cli_commands.code_app.connection_from_environment",
            return_value=("http://proxy.test", "secret"),
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            return_value=discovery,
        ),
        patch(
            "onetool.cli_commands.code_app.questionary.select",
            side_effect=[harness_prompt, model_prompt, context_prompt],
        ) as select,
        patch("onetool.cli_commands.code_app.console.print") as print_output,
        patch("onetool.cli_commands.code_app._launch") as launch,
    ):
        from onetool.cli_commands.code_app import _interactive_launch

        _interactive_launch()

    assert select.call_count == 3
    assert select.call_args_list[0].args == ("Harness",)
    assert select.call_args_list[1] == call(
        "Model",
        choices=["-vendor/model with space", "gpt-5.6-sol", "Z-AI/glm-5.2"],
    )
    assert select.call_args_list[2].args == ("Context",)
    print_output.assert_called_once_with(
        "Next time: onetool code codex --context 1m -- '-vendor/model with space'",
        markup=False,
    )
    launch.assert_called_once_with(
        harness="codex",
        model="-vendor/model with space",
        context_window=1_000_000,
        arguments=(),
        connection=("http://proxy.test", "secret"),
        inventory=("Z-AI/glm-5.2", "-vendor/model with space", "gpt-5.6-sol"),
    )


def test_interactive_cancellation_does_not_launch() -> None:
    discovery = Mock()
    discovery.models.return_value = (
        DiscoveredModel(id="gpt-5.6-sol", provider="openai"),
    )
    prompt = Mock()
    prompt.ask.return_value = None
    with (
        patch(
            "onetool.cli_commands.code_app.connection_from_environment",
            return_value=("http://proxy.test", "secret"),
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            return_value=discovery,
        ),
        patch(
            "onetool.cli_commands.code_app.questionary.select",
            return_value=prompt,
        ),
        patch("onetool.cli_commands.code_app._launch") as launch,
    ):
        from onetool.cli_commands.code_app import _interactive_launch

        _interactive_launch()
    launch.assert_not_called()


def _ready_status() -> CodeStatus:
    return CodeStatus(
        proxy_origin="http://proxy.test",
        origin_source="environment",
        origin_error=None,
        credential_present=True,
        models=(
            DiscoveredModel(id="codex-oauth/gpt-5.6-sol", provider="openai"),
            DiscoveredModel(id="openrouter/gpt-5.6-terra", provider="openrouter"),
        ),
        inventory_error=None,
        management_url="http://proxy.test/management.html",
        management_reachable=True,
        management_error=None,
        executables=(
            ExecutableStatus(
                name="claude",
                path="/bin/claude",
                version="Claude 1.0",
                error=None,
            ),
        ),
    )


def test_status_lists_models_and_opens_only_when_requested() -> None:
    with (
        patch(
            "onetool.cli_commands.code_app.collect_code_status",
            return_value=_ready_status(),
        ),
        patch(
            "onetool.cli_commands.code_app.open_management_url",
            return_value=True,
        ) as open_url,
    ):
        plain = runner.invoke(app, ["code", "status"])
        opened = runner.invoke(app, ["code", "status", "--open"])

    assert plain.exit_code == 0
    assert opened.exit_code == 0
    for output in (plain.stdout + plain.stderr, opened.stdout + opened.stderr):
        assert "Inference endpoint: reachable (authenticated)" in output
        assert "2 available" in output
        assert "codex-oauth/gpt-5.6-sol" in output
        assert "openai" in output
        assert "openrouter/gpt-5.6-terra" in output
        assert "openrouter" in output
        assert "http://proxy.test/management.html" in output
    assert open_url.call_args_list == [
        call("http://proxy.test/management.html"),
    ]


def test_status_required_failure_is_nonzero_and_redacted() -> None:
    failed = CodeStatus(
        proxy_origin="http://proxy.test",
        origin_source="default",
        origin_error=None,
        credential_present=True,
        models=(),
        inventory_error="CLIProxyAPI model discovery failed with HTTP 401",
        management_url="http://proxy.test/management.html",
        management_reachable=False,
        management_error="management page is unavailable",
        executables=(),
    )
    with patch(
        "onetool.cli_commands.code_app.collect_code_status",
        return_value=failed,
    ):
        result = runner.invoke(app, ["code", "status"])

    assert result.exit_code == 2
    output = result.stdout + result.stderr
    assert "HTTP 401" in output
    assert "Models: unavailable" in output
    assert "warning: management page is" in output
    assert "unavailable" in output
    assert "secret-value" not in output
