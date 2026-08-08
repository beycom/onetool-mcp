"""Behavioral tests for the minimal harness adapters."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from onetool.code.adapters import (
    build_invocation,
    connection_from_environment,
    replace_process,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_environment_bootstrap_uses_default_origin_and_requires_key() -> None:
    assert connection_from_environment({"CLIPROXY_INFERENCE_KEY": "secret"}) == (
        "http://127.0.0.1:8317",
        "secret",
    )

    with pytest.raises(ValueError, match="CLIPROXY_INFERENCE_KEY"):
        connection_from_environment({})
    with pytest.raises(ValueError, match="CLIPROXY_INFERENCE_KEY"):
        connection_from_environment({"CLIPROXY_INFERENCE_KEY": ""})


def test_claude_uses_exact_model_and_cleans_inherited_environment() -> None:
    invocation = build_invocation(
        harness="claude",
        model="z-ai/glm-5.2",
        proxy_origin="http://proxy.test:8317/",
        credential="proxy-secret",
        arguments=("--continue", "--model", "other", "--"),
    )

    assert invocation.argv == (
        "claude",
        "--model",
        "z-ai/glm-5.2",
        "--continue",
        "--model",
        "other",
        "--",
    )
    assert invocation.environment.set_values["ANTHROPIC_BASE_URL"] == (
        "http://proxy.test:8317"
    )
    assert invocation.environment.set_values["ANTHROPIC_MODEL"] == "z-ai/glm-5.2"
    assert invocation.environment.set_values["CLAUDE_CODE_SUBAGENT_MODEL"] == (
        "z-ai/glm-5.2"
    )
    child = invocation.environment.apply(
        {
            "CLIPROXY_INFERENCE_KEY": "bootstrap",
            "ANTHROPIC_API_KEY": "stale",
            "PATH": "/bin",
        }
    )
    assert child["ANTHROPIC_AUTH_TOKEN"] == "proxy-secret"
    assert "CLIPROXY_INFERENCE_KEY" not in child
    assert "ANTHROPIC_API_KEY" not in child
    assert child["PATH"] == "/bin"


def test_claude_context_policies_are_explicit_and_child_scoped() -> None:
    extended = build_invocation(
        harness="claude",
        model="gpt-5.6-sol",
        proxy_origin="http://proxy.test",
        credential="secret",
        context_window=1_000_000,
    )
    standard = build_invocation(
        harness="claude",
        model="gpt-5.6-sol",
        proxy_origin="http://proxy.test",
        credential="secret",
        context_window=200_000,
    )

    assert extended.model == "gpt-5.6-sol"
    assert extended.argv == ("claude", "--model", "gpt-5.6-sol[1m]")
    assert extended.environment.set_values["ANTHROPIC_MODEL"] == ("gpt-5.6-sol[1m]")
    assert "CLAUDE_CODE_DISABLE_1M_CONTEXT" not in (extended.environment.set_values)
    assert standard.argv == ("claude", "--model", "gpt-5.6-sol")
    assert standard.environment.set_values["CLAUDE_CODE_DISABLE_1M_CONTEXT"] == "1"

    with pytest.raises(ValueError, match="Claude context"):
        build_invocation(
            harness="claude",
            model="gpt-5.6-sol",
            proxy_origin="http://proxy.test",
            credential="secret",
            context_window=372_000,
        )


def test_codex_derives_v1_provider_and_keeps_secret_out_of_argv() -> None:
    arguments = ("exec", "--full-auto", "-m", "other", "--", "literal")
    invocation = build_invocation(
        harness="codex",
        model="gpt-5.6-luna",
        proxy_origin="https://proxy.test",
        credential="proxy-secret",
        arguments=arguments,
    )

    assert invocation.argv[-(len(arguments) + 2) :] == (
        "--model",
        "gpt-5.6-luna",
        *arguments,
    )
    assert 'model_providers.onetool_proxy.base_url="https://proxy.test/v1"' in (
        invocation.argv
    )
    assert 'model_providers.onetool_proxy.wire_api="responses"' in invocation.argv
    assert "proxy-secret" not in "\0".join(invocation.argv)
    assert invocation.environment.set_values == {
        "ONETOOL_CODE_PROVIDER_KEY": "proxy-secret"
    }


def test_codex_numeric_context_is_invocation_scoped() -> None:
    invocation = build_invocation(
        harness="codex",
        model="gpt-5.6-sol",
        proxy_origin="http://proxy.test",
        credential="secret",
        context_window=372_000,
    )

    assert "model_context_window=372000" in invocation.argv
    assert "model_auto_compact_token_limit=334800" in invocation.argv

    with pytest.raises(ValueError, match="positive"):
        build_invocation(
            harness="codex",
            model="gpt-5.6-sol",
            proxy_origin="http://proxy.test",
            credential="secret",
            context_window=0,
        )


def test_replace_process_uses_path_and_does_not_mutate_parent() -> None:
    invocation = build_invocation(
        harness="codex",
        model="gpt-5.6-luna",
        proxy_origin="http://127.0.0.1:8317",
        credential="proxy-secret",
    )
    parent = {
        "PATH": "/usr/bin",
        "CLIPROXY_INFERENCE_KEY": "bootstrap",
        "ONETOOL_CODE_PROVIDER_KEY": "stale",
    }

    with (
        patch("onetool.code.adapters.os.execvpe", side_effect=RuntimeError) as execvpe,
        pytest.raises(RuntimeError),
    ):
        replace_process(invocation=invocation, parent_environment=parent)

    executable, argv, environment = execvpe.call_args.args
    assert executable == "codex"
    assert argv == invocation.argv
    assert environment["PATH"] == "/usr/bin"
    assert environment["ONETOOL_CODE_PROVIDER_KEY"] == "proxy-secret"
    assert "CLIPROXY_INFERENCE_KEY" not in environment
    assert parent["ONETOOL_CODE_PROVIDER_KEY"] == "stale"
