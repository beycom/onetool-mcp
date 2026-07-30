"""Behavioral tests for code-harness invocation adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from onetool.code.adapters import (
    build_invocation,
    replace_process,
    resolve_client_executable,
)
from onetool.code.resolver import resolve_target
from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import (
    direct_codex_config,
    proxy_launcher_config,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.core]

_MISSING_CLAUDE_ENV = {
    "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION",
}


def _build(
    config: OneToolConfig,
    *,
    harness: str,
    model: str,
    route: str | None = None,
    profile: str | None = None,
    permission: str | None = None,
    passthrough: tuple[str, ...] = (),
    secret_resolver: Mock | None = None,
):
    resolved = resolve_target(
        config=config,
        harness=harness,  # type: ignore[arg-type]
        model=model,
        route=route,  # type: ignore[arg-type]
        profile=profile,
        permission=permission,  # type: ignore[arg-type]
    )
    resolver = secret_resolver or Mock(return_value="proxy-secret")
    with patch(
        "onetool.code.adapters.resolve_client_executable",
        return_value=f"/usr/bin/{harness}",
    ):
        return build_invocation(
            config=config,
            target=resolved,
            passthrough=passthrough,
            secret_resolver=resolver,
        )


@pytest.mark.parametrize(
    ("model", "expected_model", "expected_context"),
    [
        ("sol", "gpt-5.6-sol", {}),
        (
            "glm",
            "z-ai/glm-5.2[1m]",
            {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "900000"},
        ),
        (
            "sonnet",
            "claude-sonnet-4-6",
            {"CLAUDE_CODE_DISABLE_1M_CONTEXT": "1"},
        ),
    ],
)
def test_claude_context_policy_changes_real_argv_and_environment(
    model: str,
    expected_model: str,
    expected_context: dict[str, str],
) -> None:
    config = OneToolConfig.model_validate(proxy_launcher_config())
    invocation = _build(config, harness="claude", model=model)

    assert invocation.argv[:3] == ("/usr/bin/claude", "--model", expected_model)
    assert invocation.environment.set_values["ANTHROPIC_DEFAULT_OPUS_MODEL"] == (
        expected_model
    )
    if model == "glm":
        assert invocation.environment.set_values["ANTHROPIC_MODEL"] == expected_model
    else:
        assert "ANTHROPIC_MODEL" not in invocation.environment.set_values
    for key, value in expected_context.items():
        assert invocation.environment.set_values[key] == value
    for key in _MISSING_CLAUDE_ENV:
        assert key in invocation.environment.remove

    child = invocation.environment.apply(
        dict.fromkeys(_MISSING_CLAUDE_ENV, "inherited")
    )
    assert _MISSING_CLAUDE_ENV.isdisjoint(child)


def test_direct_codex_profile_changes_runtime_without_proxy_secret(
    tmp_path,
) -> None:
    data = direct_codex_config()
    data["code"]["permission"] = "bypass"
    data["code"]["clients"] = {
        "codex": {
            "working_directory": "work",
            "home_path": "codex-home",
            "additional_arguments": ["--search"],
        }
    }
    (tmp_path / "work").mkdir()
    (tmp_path / "codex-home").mkdir()
    config = OneToolConfig.model_validate(data)
    config._config_dir = tmp_path
    secret_resolver = Mock(side_effect=AssertionError("proxy secret was resolved"))

    invocation = _build(
        config,
        harness="codex",
        model="glm",
        profile="openrouter",
        passthrough=("exec", "--json"),
        secret_resolver=secret_resolver,
    )

    assert invocation.argv == (
        "/usr/bin/codex",
        "--profile",
        "openrouter",
        "--model",
        "z-ai/glm-5.2",
        "--dangerously-bypass-approvals-and-sandbox",
        "--search",
        "exec",
        "--json",
    )
    assert invocation.argv.count("--search") == 1
    assert invocation.working_directory == str(tmp_path / "work")
    assert invocation.environment.set_values == {
        "CODEX_HOME": str(tmp_path / "codex-home")
    }
    assert "ONETOOL_CODE_PROVIDER_KEY" in invocation.environment.remove
    secret_resolver.assert_not_called()


def test_proxy_codex_keeps_secret_out_of_argv_and_redacted_output() -> None:
    config = OneToolConfig.model_validate(proxy_launcher_config())
    invocation = _build(config, harness="codex", model="sol")

    assert "proxy-secret" not in " ".join(invocation.argv)
    assert invocation.environment.set_values["ONETOOL_CODE_PROVIDER_KEY"] == (
        "proxy-secret"
    )
    assert "proxy-secret" not in str(invocation.redacted())
    assert "model_provider=\"onetool_proxy\"" in invocation.argv


def test_executable_from_relative_path_entry_is_resolved_before_chdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "codex"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(executable.stat().st_mode | 0o111)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "bin")

    resolved = resolve_client_executable("codex")

    assert resolved == str(executable.resolve())


@pytest.mark.parametrize(
    "passthrough",
    [
        ("--model", "other"),
        ("--profile=work",),
        ("-p", "work"),
        ("-pwork",),
        ("-mother",),
        ("-cmodel_provider='other'",),
        ("--config", "model_provider='other'"),
    ],
)
def test_passthrough_cannot_override_launcher_owned_arguments(
    passthrough: tuple[str, ...],
) -> None:
    config = OneToolConfig.model_validate(direct_codex_config())

    with pytest.raises(ValueError, match="launcher-owned"):
        _build(
            config,
            harness="codex",
            model="glm",
            profile="openrouter",
            passthrough=passthrough,
        )


def test_replace_process_applies_environment_and_working_directory() -> None:
    config = OneToolConfig.model_validate(direct_codex_config())
    invocation = _build(
        config,
        harness="codex",
        model="glm",
        profile="openrouter",
    )
    invocation = type(invocation)(
        target=invocation.target,
        executable=invocation.executable,
        argv=invocation.argv,
        environment=invocation.environment,
        working_directory="/tmp/onetool-code-work",
    )

    with (
        patch("onetool.code.adapters.os.chdir") as chdir,
        patch("onetool.code.adapters.os.execvpe", side_effect=RuntimeError) as execvpe,
        pytest.raises(RuntimeError),
    ):
        replace_process(
            invocation=invocation,
            parent_environment={
                "PATH": "/usr/bin",
                "ONETOOL_CODE_PROVIDER_KEY": "stale",
            },
        )

    chdir.assert_called_once_with("/tmp/onetool-code-work")
    executable, argv, environment = execvpe.call_args.args
    assert executable == "/usr/bin/codex"
    assert argv == invocation.argv
    assert environment["PATH"] == "/usr/bin"
    assert "ONETOOL_CODE_PROVIDER_KEY" not in environment
