"""CLI acceptance tests for exact code-launch targets and diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from onetool.cli import app
from ot.config import reset
from tests.unit.core.routing_fixtures import (
    direct_codex_config,
    proxy_launcher_config,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.core]

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_config_cache() -> Iterator[None]:
    reset()
    yield
    reset()


def _write_config(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "onetool.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_help_exposes_profile_and_removes_setup() -> None:
    root = runner.invoke(app, ["--help"])
    codex = runner.invoke(app, ["codex", "--help"])
    code = runner.invoke(app, ["code", "--help"])

    assert root.exit_code == 0
    assert "Code Harnesses" in root.stdout
    assert codex.exit_code == 0
    assert "--profile" in codex.stdout
    assert "-p" in codex.stdout
    assert code.exit_code == 0
    assert "models" in code.stdout
    assert "status" in code.stdout
    assert "doctor" in code.stdout
    assert "setup" not in code.stdout


def test_real_boundary_preserves_opaque_tail_and_profile() -> None:
    with patch("onetool.cli_commands.code_app._launch") as launch:
        result = runner.invoke(
            app,
            [
                "codex",
                "glm",
                "--profile",
                "openrouter",
                "--",
                "exec",
                "--json",
            ],
        )

    assert result.exit_code == 0
    assert launch.call_args.kwargs["model"] == "glm"
    assert launch.call_args.kwargs["profile_name"] == "openrouter"
    assert launch.call_args.kwargs["passthrough"] == ("exec", "--json")


def test_direct_dry_run_is_redacted_and_does_not_replace_process(
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path, direct_codex_config())
    with (
        patch(
            "onetool.code.adapters.resolve_client_executable",
            return_value="/usr/bin/codex",
        ),
        patch("onetool.cli_commands.code_app.replace_process") as replace,
    ):
        result = runner.invoke(
            app,
            [
                "codex",
                "glm",
                "--profile",
                "openrouter",
                "--dry-run",
                "--config",
                str(config),
            ],
        )

    assert result.exit_code == 0
    output = result.stdout + result.stderr
    assert '"kind": "profile"' in output
    assert '"name": "openrouter"' in output
    assert '"set": []' in output
    replace.assert_not_called()


def test_route_and_profile_conflict_fails_before_launch(tmp_path: Path) -> None:
    data = proxy_launcher_config()
    data["code"]["direct"] = direct_codex_config()["code"]["direct"]
    config = _write_config(tmp_path, data)

    result = runner.invoke(
        app,
        [
            "codex",
            "glm",
            "--route",
            "openrouter",
            "--profile",
            "openrouter",
            "--dry-run",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 2
    assert "route 'openrouter'" in result.stderr
    assert "profile 'openrouter'" in result.stderr


def test_direct_only_status_and_doctor_ignore_proxy(tmp_path: Path) -> None:
    config = _write_config(tmp_path, direct_codex_config())
    capabilities = Mock(return_value=("--model", "--profile"))
    with (
        patch(
            "onetool.cli_commands.code_app.resolve_client_executable",
            return_value="/usr/bin/codex",
        ),
        patch(
            "onetool.cli_commands.code_app.check_client_capabilities",
            capabilities,
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            side_effect=AssertionError("proxy discovery ran"),
        ),
        patch(
            "onetool.cli_commands.code_app.get_secret",
            side_effect=AssertionError("proxy secret resolved"),
        ),
    ):
        status = runner.invoke(app, ["code", "status", "--config", str(config)])
        doctor = runner.invoke(app, ["code", "doctor", "--config", str(config)])

    assert status.exit_code == 0
    assert "codex: available" in status.stderr
    assert "claude:" not in status.stderr
    assert "CLIProxyAPI" not in status.stderr
    assert doctor.exit_code == 0
    capabilities.assert_called_once()
    assert capabilities.call_args.kwargs["require_proxy"] is False
    assert capabilities.call_args.kwargs["require_profile"] is True


@pytest.mark.parametrize(
    ("advertised", "expected_exit", "expected_diagnostic"),
    [
        (
            ("gpt-5.6-sol", "z-ai/glm-5.2", "claude-sonnet-4-6"),
            0,
            "codex_subscription: gpt-5.6-sol",
        ),
        (
            ("z-ai/glm-5.2", "claude-sonnet-4-6"),
            1,
            "codex_subscription: gpt-5.6-sol (not advertised)",
        ),
        (
            (
                "gpt-5.6-sol",
                "gpt-5.6-sol",
                "z-ai/glm-5.2",
                "claude-sonnet-4-6",
            ),
            1,
            "codex_subscription: gpt-5.6-sol (duplicate)",
        ),
    ],
)
def test_proxy_doctor_fetches_one_inventory_and_compares_exact_ids(
    tmp_path: Path,
    advertised: tuple[str, ...],
    expected_exit: int,
    expected_diagnostic: str,
) -> None:
    config = _write_config(tmp_path, proxy_launcher_config())
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("CLIPROXY_INFERENCE_KEY: test-key\n")
    discovery = Mock()
    discovery.models.return_value = advertised
    with (
        patch(
            "onetool.cli_commands.code_app.resolve_client_executable",
            return_value="/usr/bin/harness",
        ),
        patch(
            "onetool.cli_commands.code_app.check_client_capabilities",
            return_value=("--model",),
        ),
        patch(
            "onetool.cli_commands.code_app.ModelDiscovery",
            return_value=discovery,
        ) as discovery_factory,
    ):
        result = runner.invoke(
            app,
            [
                "code",
                "doctor",
                "--config",
                str(config),
                "--secrets",
                str(secrets),
            ],
        )

    assert result.exit_code == expected_exit
    assert expected_diagnostic in result.stderr
    discovery_factory.assert_called_once()
    discovery.models.assert_called_once_with()


def test_claude_subscription_warning_survives_quiet_mode(tmp_path: Path) -> None:
    config = _write_config(tmp_path, proxy_launcher_config())
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("CLIPROXY_INFERENCE_KEY: test-key\n")
    with patch(
        "onetool.code.adapters.resolve_client_executable",
        return_value="/usr/bin/claude",
    ):
        result = runner.invoke(
            app,
            [
                "claude",
                "sonnet",
                "--route",
                "claude_subscription",
                "--quiet",
                "--dry-run",
                "--config",
                str(config),
                "--secrets",
                str(secrets),
            ],
        )

    assert result.exit_code == 0
    output = " ".join(result.stderr.split())
    assert "not an approved Anthropic subscription path" in output
    assert "Starting claude" not in output
