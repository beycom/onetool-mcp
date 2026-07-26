"""CLI tests for code harness launch and diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from onetool.cli import app
from ot.config.loader import load_config
from tests.unit.core.routing_fixtures import valid_routing_config

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ot.config.routing import CLIProxyConnectionConfig

pytestmark = [pytest.mark.unit, pytest.mark.serve]

runner = CliRunner()


class FakeDiscovery:
    """Live-model fixture used by CLI dry runs."""

    def __init__(
        self,
        *,
        config: CLIProxyConnectionConfig,
        secret: str,
    ) -> None:
        assert config.base_url == "http://127.0.0.1:8317"
        assert secret == "proxy-secret"

    def validate(self, *identities: str) -> str:
        """Return the first configured identity."""
        return identities[0]


class CapturingConsole:
    """Console facade that writes through Click's current captured stream."""

    is_terminal = False

    def print(self, *objects: object, **_kwargs: object) -> None:
        """Write plain object text to the active CLI runner stream."""
        typer.echo(" ".join(str(item) for item in objects))


@pytest.fixture
def launcher_files(tmp_path: Path) -> tuple[Path, Path]:
    """Write a complete launcher config and named secrets."""
    data = valid_routing_config()
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    data["code"]["routes"]["claude-sol"]["settings_path"] = str(settings)
    data["code"]["clients"]["codex"].pop("home_path")
    data["code"]["routes"]["codex-openrouter"].pop("profile")
    data["code"]["routes"]["codex-openrouter"].pop("model_catalog_path")
    config = tmp_path / "onetool.yaml"
    config.write_text(yaml.safe_dump(data))
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text(
        yaml.safe_dump(
            {
                "CLIPROXY_INFERENCE_KEY": "proxy-secret",
                "OPENROUTER_API_KEY": "openrouter-secret",
            }
        )
    )
    return config, secrets


@pytest.fixture(autouse=True)
def adapter_capabilities() -> Iterator[None]:
    """Avoid depending on installed harnesses in CLI unit tests."""
    with (
        patch(
            "onetool.code.adapters.resolve_client_executable",
            side_effect=lambda value: f"/resolved/{Path(value).name}",
        ),
        patch("onetool.code.adapters._check_configured_version"),
        patch("onetool.code.adapters._check_help_capabilities"),
        patch(
            "onetool.code.adapters.ModelDiscovery",
            FakeDiscovery,
        ),
        patch(
            "onetool.cli_commands.code_app.resolve_client_executable",
            side_effect=lambda value: f"/resolved/{Path(value).name}",
        ),
        patch(
            "onetool.cli_commands.code_app.run_capability_command",
            return_value="auth login -config -codex-login",
        ),
        patch("onetool.cli_commands.code_app.console", CapturingConsole()),
    ):
        yield


def test_root_and_harness_help_are_labelled() -> None:
    """Launcher commands and complete options appear in CLI help."""
    root = runner.invoke(app, ["--help"])
    claude = runner.invoke(app, ["claude", "--help"])
    code = runner.invoke(app, ["code", "--help"])

    assert root.exit_code == 0
    assert "Code Harnesses" in root.stdout
    assert "claude" in root.stdout and "codex" in root.stdout
    assert claude.exit_code == 0
    for option in (
        "--route",
        "--safe",
        "--bypass",
        "--config",
        "--quiet",
        "--verbose",
        "--dry-run",
    ):
        assert option in claude.stdout
    assert code.exit_code == 0
    for command in ("setup", "models", "status", "doctor", "config", "login"):
        assert command in code.stdout
    for excluded in ("restart", "logs", "account", "activity", "management"):
        assert excluded not in code.stdout


def test_missing_config_lists_checked_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Automatic resolution fails with checked paths and setup guidance."""
    project = tmp_path / "project.yaml"
    user = tmp_path / "user.yaml"
    monkeypatch.setattr(
        "onetool.cli_commands.code_app._candidate_config_paths",
        lambda: (project, user),
    )

    result = runner.invoke(app, ["claude", "--dry-run"])

    assert result.exit_code == 2
    assert str(project) in result.stdout
    assert str(user) in result.stdout
    assert "code setup" in result.stdout


def test_explicit_config_is_the_only_checked_path(tmp_path: Path) -> None:
    """An invalid explicit config never falls back to another location."""
    missing = tmp_path / "missing.yaml"

    result = runner.invoke(
        app,
        ["codex", "--config", str(missing), "--dry-run"],
    )

    assert result.exit_code == 2
    assert f"Explicit launcher config is not a file: {missing}" in result.stdout


def test_native_dry_run_shows_redacted_resolved_invocation(
    launcher_files: tuple[Path, Path],
) -> None:
    """Dry-run validates the route without starting the harness."""
    config, _ = launcher_files

    result = runner.invoke(
        app,
        [
            "claude",
            "--config",
            str(config),
            "--dry-run",
            "--verbose",
            "--",
            "--continue",
        ],
    )

    assert result.exit_code == 0
    assert '"route": "claude-native"' in result.stdout
    assert '"--continue"' in result.stdout
    assert "ANTHROPIC_AUTH_TOKEN" in result.stdout
    assert "proxy-secret" not in result.stdout


def test_proxy_dry_run_never_displays_secret(
    launcher_files: tuple[Path, Path],
) -> None:
    """Proxy credentials stay out of argv, summaries, and dry-run output."""
    config, secrets = launcher_files

    result = runner.invoke(
        app,
        [
            "claude",
            "sol",
            "--route",
            "claude-sol",
            "--config",
            str(config),
            "--secrets",
            str(secrets),
            "--dry-run",
            "--verbose",
        ],
    )

    assert result.exit_code == 0
    assert "claude-sol" in result.stdout
    assert "ANTHROPIC_AUTH_TOKEN" in result.stdout
    assert "proxy-secret" not in result.stdout


def test_contradictory_permissions_fail_before_launch(
    launcher_files: tuple[Path, Path],
) -> None:
    """Safe and bypass modes are mutually exclusive."""
    config, _ = launcher_files

    result = runner.invoke(
        app,
        [
            "codex",
            "--config",
            str(config),
            "--safe",
            "--bypass",
            "--dry-run",
        ],
    )

    assert result.exit_code == 2
    assert "--safe and --bypass" in result.stdout


def test_route_owned_passthrough_is_rejected(
    launcher_files: tuple[Path, Path],
) -> None:
    """Arguments after -- cannot override the typed route."""
    config, _ = launcher_files

    result = runner.invoke(
        app,
        [
            "codex",
            "--config",
            str(config),
            "--dry-run",
            "--",
            "--model",
            "other",
        ],
    )

    assert result.exit_code == 2
    assert "launcher-owned model" in result.stdout


def test_child_exit_code_is_preserved(
    launcher_files: tuple[Path, Path],
) -> None:
    """The top-level command returns the foreground child's outcome."""
    config, _ = launcher_files
    with patch(
        "onetool.cli_commands.code_app.run_foreground",
        return_value=(17, 0.25),
    ):
        result = runner.invoke(app, ["codex", "--config", str(config)])

    assert result.exit_code == 17
    assert "outcome=exit 17" in result.stdout


def test_noninteractive_picker_reports_explicit_syntax(
    launcher_files: tuple[Path, Path],
) -> None:
    """The picker never guesses in a non-interactive session."""
    config, _ = launcher_files
    with patch("onetool.cli_commands.code_app.os.isatty", return_value=False):
        result = runner.invoke(app, ["code", "--config", str(config)])

    assert result.exit_code == 2
    assert "onetool claude [MODEL]" in result.stdout
    assert "onetool codex [MODEL]" in result.stdout


def test_interactive_picker_cancellation_is_clean(
    launcher_files: tuple[Path, Path],
) -> None:
    """Cancelling the first picker leaves external state untouched."""
    config, _ = launcher_files
    cancelled = MagicMock()
    cancelled.ask.return_value = None
    with (
        patch("onetool.cli_commands.code_app.os.isatty", return_value=True),
        patch(
            "onetool.cli_commands.code_app.questionary.select",
            return_value=cancelled,
        ),
    ):
        result = runner.invoke(app, ["code", "--config", str(config)])

    assert result.exit_code == 0


def test_quiet_does_not_suppress_claude_proxy_warning(
    launcher_files: tuple[Path, Path],
) -> None:
    """The terms/account/billing warning remains visible in quiet mode."""
    config, secrets = launcher_files
    data = yaml.safe_load(config.read_text())
    data["code"]["claude_subscription_proxy_enabled"] = True
    data["code"]["routes"]["claude-subscription-proxy"] = {
        "harness": "claude",
        "source": "claude_subscription",
        "transport": "cliproxy",
        "model": "sonnet",
    }
    config.write_text(yaml.safe_dump(data))

    result = runner.invoke(
        app,
        [
            "claude",
            "--route",
            "claude-subscription-proxy",
            "--config",
            str(config),
            "--secrets",
            str(secrets),
            "--quiet",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "not an approved Anthropic subscription path" in result.stdout
    assert "Starting claude" not in result.stdout


def test_setup_materializes_valid_packaged_template(
    tmp_path: Path,
) -> None:
    """Setup writes a standalone include fragment and refuses overwrite."""
    config = tmp_path / "onetool.yaml"
    config.write_text("version: 2\n")

    first = runner.invoke(app, ["code", "setup", "--config", str(config)])
    target = tmp_path / "code-routing.yaml"
    second = runner.invoke(app, ["code", "setup", "--config", str(config)])

    assert first.exit_code == 0
    assert target.is_file()
    loaded = load_config(target)
    assert loaded.code is not None
    assert loaded.code.defaults.claude_route == "claude-native"
    assert second.exit_code == 2
    assert "Refusing to overwrite" in second.stdout


def test_status_is_presence_only(
    launcher_files: tuple[Path, Path],
) -> None:
    """Status names required secrets without showing values."""
    config, secrets = launcher_files
    result = runner.invoke(
        app,
        [
            "code",
            "status",
            "--config",
            str(config),
            "--secrets",
            str(secrets),
        ],
    )

    assert result.exit_code == 0
    assert "CLIPROXY_INFERENCE_KEY: configured" in result.stdout
    assert "CLIProxyAPI inference endpoint: configured" in result.stdout
    assert "settings: available" in result.stdout
    assert "proxy-secret" not in result.stdout


def test_status_reports_non_executable_absolute_client_as_missing(
    launcher_files: tuple[Path, Path],
) -> None:
    """Presence checks do not accept a nonexistent absolute executable path."""
    config, secrets = launcher_files
    with patch(
        "onetool.cli_commands.code_app.resolve_client_executable",
        side_effect=ValueError("missing"),
    ):
        result = runner.invoke(
            app,
            [
                "code",
                "status",
                "--config",
                str(config),
                "--secrets",
                str(secrets),
            ],
        )

    assert result.exit_code == 0
    assert "claude: missing" in result.stdout
    assert "codex: missing" in result.stdout
    assert "cliproxy: missing" in result.stdout


def test_doctor_checks_every_enabled_route(
    launcher_files: tuple[Path, Path],
) -> None:
    """Doctor constructs each enabled route without launching a child."""
    config, secrets = launcher_files
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

    assert result.exit_code == 0
    assert "claude-native" in result.stdout
    assert "codex-native" in result.stdout
    assert "configured constraint: >=2.1.0" in result.stdout
    assert "required capabilities: --model" in result.stdout


def test_login_is_delegated_with_inherited_process_outcome(
    launcher_files: tuple[Path, Path],
) -> None:
    """Login calls only the verified external command and preserves failure."""
    config, _ = launcher_files
    with patch("onetool.cli_commands.code_app.subprocess.run") as run:
        run.return_value.returncode = 23
        result = runner.invoke(
            app,
            ["code", "login", "codex", "--config", str(config)],
        )

    assert result.exit_code == 23
    run.assert_called_once_with(
        ("/resolved/codex", "login"),
        check=False,
        shell=False,
    )


def test_cliproxy_login_resolves_config_relative_to_launcher_config(
    tmp_path: Path,
) -> None:
    """Delegated CLIProxy login uses the canonical config-relative path."""
    data = valid_routing_config()
    data["code"]["clients"]["cliproxy"]["config_path"] = "cliproxy.conf"
    config = tmp_path / "onetool.yaml"
    config.write_text(yaml.safe_dump(data))
    cliproxy_config = tmp_path / "cliproxy.conf"
    cliproxy_config.write_text("port: 8317\n")

    with patch("onetool.cli_commands.code_app.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(
            app,
            ["code", "login", "cliproxy", "--config", str(config)],
        )

    assert result.exit_code == 0
    run.assert_called_once_with(
        (
            "/resolved/cliproxyapi",
            "-config",
            str(cliproxy_config),
            "-codex-login",
        ),
        check=False,
        shell=False,
    )
