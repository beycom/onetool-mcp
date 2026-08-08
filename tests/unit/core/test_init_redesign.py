"""Unit tests for redesigned onetool init command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.core
def test_write_onetool_yaml_minimal(tmp_path: Path) -> None:
    """Minimal onetool.yaml contains only version: 2 when no includes."""
    from onetool.cli import _write_onetool_yaml

    config_path = tmp_path / "onetool.yaml"
    _write_onetool_yaml(config_path, [])

    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2
    assert "include" not in data


@pytest.mark.unit
@pytest.mark.core
def test_write_onetool_yaml_with_includes(tmp_path: Path) -> None:
    """onetool.yaml written with include list."""
    from onetool.cli import _write_onetool_yaml

    config_path = tmp_path / "onetool.yaml"
    _write_onetool_yaml(config_path, ["security.yaml", "servers.yaml"])

    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2
    assert data["include"] == ["security.yaml", "servers.yaml"]


@pytest.mark.unit
@pytest.mark.core
def test_copy_file_security(tmp_path: Path) -> None:
    """--file security.yaml copies security.yaml from package templates."""
    from onetool.cli import _copy_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    result = _copy_file(ot_dir, "security.yaml")

    assert result is True
    assert (ot_dir / "security.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_copy_file_code_routing(tmp_path: Path) -> None:
    """The removed launcher configuration template is unavailable."""
    from onetool.cli import _copy_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    assert _copy_file(ot_dir, "code-routing.yaml") is False
    assert not (ot_dir / "code-routing.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_copy_diagram_copies_yaml_and_templates(tmp_path: Path) -> None:
    """_copy_diagram copies diagram.yaml and templates/diagram/ directory."""
    from onetool.cli import _copy_diagram

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    result = _copy_diagram(ot_dir)

    assert result is True
    assert (ot_dir / "diagram.yaml").exists()
    assert (ot_dir / "templates" / "diagram").is_dir()
    # At least one template file should be present
    templates = list((ot_dir / "templates" / "diagram").iterdir())
    assert len(templates) > 0


@pytest.mark.unit
@pytest.mark.core
def test_copy_diagram_backs_up_existing_templates(tmp_path: Path) -> None:
    """_copy_diagram backs up existing templates/diagram/ before overwriting."""
    from onetool.cli import _copy_diagram

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    existing_templates = ot_dir / "templates" / "diagram"
    existing_templates.mkdir(parents=True)
    (existing_templates / "custom.mmd").write_text("# custom")

    _copy_diagram(ot_dir)

    assert (ot_dir / "templates" / "diagram").is_dir()
    bak = ot_dir / "templates" / "diagram.bak"
    assert bak.exists()
    assert (bak / "custom.mmd").read_text() == "# custom"


@pytest.mark.unit
@pytest.mark.core
def test_copy_file_unknown(tmp_path: Path) -> None:
    """Unknown file returns False (not a fatal error)."""
    from onetool.cli import _copy_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    result = _copy_file(ot_dir, "nonexistent_xyz.yaml")

    assert result is False
    assert not (ot_dir / "nonexistent_xyz.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_copy_servers_yaml_subset(tmp_path: Path) -> None:
    """--servers chrome_devtools,playwright creates servers.yaml with only those blocks."""
    from onetool.cli import _copy_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    _copy_servers_yaml(ot_dir, ["chrome_devtools", "playwright"])

    servers_yaml = ot_dir / "servers.yaml"
    assert servers_yaml.exists()

    data = yaml.safe_load(servers_yaml.read_text())
    servers = data.get("servers", {})
    assert "chrome_devtools" in servers
    assert "playwright" in servers
    assert "github" not in servers


@pytest.mark.unit
@pytest.mark.core
def test_copy_servers_yaml_all(tmp_path: Path) -> None:
    """Only shipped server templates are materialised when requested."""
    from onetool.cli import _copy_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    _copy_servers_yaml(ot_dir, ["chrome_devtools", "playwright", "github", "azure"])

    data = yaml.safe_load((ot_dir / "servers.yaml").read_text())
    servers = data.get("servers", {})
    assert set(servers) == {"chrome_devtools", "playwright"}
    assert "github" not in servers
    assert "azure" not in servers
    assert "chunkhound" not in servers


@pytest.mark.unit
@pytest.mark.core
def test_copy_servers_yaml_unknown_skipped(tmp_path: Path) -> None:
    """Unknown server names are skipped without raising."""
    from onetool.cli import _copy_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    # Should not raise
    _copy_servers_yaml(ot_dir, ["chrome_devtools", "unknown-server"])

    data = yaml.safe_load((ot_dir / "servers.yaml").read_text())
    servers = data.get("servers", {})
    assert "chrome_devtools" in servers
    assert "unknown-server" not in servers


@pytest.mark.unit
@pytest.mark.core
def test_init_validate_include_source_reporting(tmp_path: Path) -> None:
    """init validate shows [user] vs [default] source for each include."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"

    # Create user-owned security.yaml
    (ot_dir / "security.yaml").write_text("security:\n  validate_code: true\n")
    # Leave servers.yaml absent (will use package default)
    config_path.write_text(
        "version: 2\ninclude:\n  - security.yaml\n  - servers.yaml\n"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["init", "validate", "--config", str(config_path)])

    assert "[user]" in result.output
    assert "[default]" in result.output


@pytest.mark.unit
@pytest.mark.core
def test_init_validate_succeeds_with_config_flag(tmp_path: Path) -> None:
    """init validate --config <path> must not raise 'No config loaded' (regression)."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"
    config_path.write_text("version: 2\n")

    runner = CliRunner()
    result = runner.invoke(app, ["init", "validate", "--config", str(config_path)])

    assert "No config loaded" not in result.output
    assert result.exit_code == 0


# =============================================================================
# Conflict handling: _safe_copy / _safe_write
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_safe_copy_backs_up_existing_file(tmp_path: Path) -> None:
    """_safe_copy renames existing dest to .bak before copying."""
    from onetool.cli import _safe_copy

    src = tmp_path / "src.yaml"
    src.write_text("new content")
    dest = tmp_path / "dest.yaml"
    dest.write_text("old content")

    _safe_copy(src, dest)

    assert dest.read_text() == "new content"
    bak = tmp_path / "dest.yaml.bak"
    assert bak.exists()
    assert bak.read_text() == "old content"


@pytest.mark.unit
@pytest.mark.core
def test_safe_copy_no_backup_when_dest_absent(tmp_path: Path) -> None:
    """_safe_copy works normally when dest does not exist (no .bak created)."""
    from onetool.cli import _safe_copy

    src = tmp_path / "src.yaml"
    src.write_text("content")
    dest = tmp_path / "dest.yaml"

    _safe_copy(src, dest)

    assert dest.read_text() == "content"
    assert not (tmp_path / "dest.yaml.bak").exists()


@pytest.mark.unit
@pytest.mark.core
def test_safe_write_backs_up_existing_file(tmp_path: Path) -> None:
    """_safe_write renames existing dest to .bak before writing new content."""
    from onetool.cli import _safe_write

    dest = tmp_path / "config.yaml"
    dest.write_text("old")

    _safe_write(dest, "new")

    assert dest.read_text() == "new"
    bak = tmp_path / "config.yaml.bak"
    assert bak.exists()
    assert bak.read_text() == "old"


@pytest.mark.unit
@pytest.mark.core
def test_copy_file_backs_up_existing(tmp_path: Path) -> None:
    """_copy_file renames existing file to .bak before writing."""
    from onetool.cli import _copy_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    existing = ot_dir / "security.yaml"
    existing.write_text("# my custom rules\n")

    _copy_file(ot_dir, "security.yaml")

    assert existing.exists()
    bak = ot_dir / "security.yaml.bak"
    assert bak.exists()
    assert bak.read_text() == "# my custom rules\n"


# =============================================================================
# Path confirmation prompt
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_init_tty_path_confirmation_default_accepted(tmp_path: Path) -> None:
    """In TTY mode, pressing enter accepts the default config path."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    config_path = ot_dir / "onetool.yaml"

    from unittest.mock import MagicMock

    mock_tui = MagicMock()
    mock_tui.ask_text_sync.return_value = str(config_path)
    mock_tui.ask_checkbox.return_value = []

    runner = CliRunner()
    with (
        patch.dict("sys.modules", {"ot._tui": mock_tui, "questionary": MagicMock()}),
        patch("onetool.cli._stdin_is_tty", return_value=True),
    ):
        result = runner.invoke(app, ["init", "-c", str(config_path)])

    mock_ask = mock_tui.ask_text_sync

    assert result.exit_code == 0, result.output
    mock_ask.assert_called_once()
    assert config_path.exists()


@pytest.mark.unit
@pytest.mark.core
def test_init_tty_path_confirmation_cancelled() -> None:
    """In TTY mode, Ctrl+C on the path prompt cancels init."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from onetool.cli import app

    mock_tui = MagicMock()
    mock_tui.ask_text_sync.return_value = None

    runner = CliRunner()
    with (
        patch.dict("sys.modules", {"ot._tui": mock_tui, "questionary": MagicMock()}),
        patch("onetool.cli._stdin_is_tty", return_value=True),
    ):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Cancelled" in result.output


# =============================================================================
# --config smart path detection
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_init_config_directory_creates_onetool_yaml(tmp_path: Path) -> None:
    """onetool init -c <dir> (no .yaml suffix) writes onetool.yaml inside that dir."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"

    runner = CliRunner()
    result = runner.invoke(app, ["init", "-c", str(ot_dir)])

    assert result.exit_code == 0, result.output
    assert ot_dir.exists()
    config_path = ot_dir / "onetool.yaml"
    assert config_path.exists()
    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2


@pytest.mark.unit
@pytest.mark.core
def test_init_config_yaml_path_writes_named_file(tmp_path: Path) -> None:
    """onetool init -c <path>.yaml writes that exact file (not onetool.yaml inside it)."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "custom.yaml"

    runner = CliRunner()
    result = runner.invoke(app, ["init", "-c", str(config_path)])

    assert result.exit_code == 0, result.output
    assert config_path.exists()
    assert not (ot_dir / "onetool.yaml").exists()
    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2


@pytest.mark.unit
@pytest.mark.core
def test_init_config_creates_missing_directory(tmp_path: Path) -> None:
    """onetool init -c <dir> creates the directory when it doesn't exist yet."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / "new" / "nested"
    assert not ot_dir.exists()

    runner = CliRunner()
    result = runner.invoke(app, ["init", "-c", str(ot_dir)])

    assert result.exit_code == 0, result.output
    assert ot_dir.exists()
    assert (ot_dir / "onetool.yaml").exists()


# =============================================================================
# First-Run No-Config Serve Tests (W5)
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_root_invocation_missing_config_non_interactive_exits(tmp_path: Path) -> None:
    """Root compatibility invocation with missing config exits 1."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    config_path = tmp_path / ".onetool" / "onetool.yaml"

    with patch("onetool.cli._stdin_is_tty", return_value=False):
        result = runner.invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 1
    assert "onetool init" in result.output or "not initialized" in result.output.lower()


@pytest.mark.unit
@pytest.mark.core
def test_root_invocation_missing_config_interactive_declined_exits(
    tmp_path: Path,
) -> None:
    """Root compatibility invocation with missing config exits when init is declined."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    config_path = tmp_path / ".onetool" / "onetool.yaml"

    with patch("onetool.cli._stdin_is_tty", return_value=True):
        result = runner.invoke(app, ["--config", str(config_path)], input="n\n")

    assert result.exit_code == 1
    assert "onetool init" in result.output or "when ready" in result.output


@pytest.mark.unit
@pytest.mark.core
def test_root_invocation_missing_config_interactive_accepted_calls_ensure_ot_dir(
    tmp_path: Path,
) -> None:
    """Root compatibility invocation with missing config can initialize in TTY mode."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    ot_dir = tmp_path / ".onetool"
    config_path = ot_dir / "onetool.yaml"

    mock_ensure = MagicMock()

    # Mock ot.server at sys.modules level to prevent its module-level configure_logging call
    import sys
    import types

    fake_server = types.ModuleType("ot.server")
    fake_server.run_root_server = MagicMock()

    with (
        patch("onetool.cli._stdin_is_tty", return_value=True),
        patch("ot.paths.ensure_ot_dir", mock_ensure),
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.dict(sys.modules, {"ot.server": fake_server}),
    ):
        result = runner.invoke(app, ["--config", str(config_path)], input="y\n")

    assert mock_ensure.call_count == 1
    assert "Initialized" in result.output
    fake_server.run_root_server.assert_called_once_with(transport="stdio")


@pytest.mark.unit
@pytest.mark.core
def test_serve_missing_config_fails_fast(tmp_path: Path) -> None:
    """Explicit serve command with missing config fails without interactive init."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / ".onetool" / "onetool.yaml"

    with patch("onetool.cli._stdin_is_tty", return_value=True):
        result = CliRunner().invoke(app, ["serve", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "OneTool not initialized" in result.output
    assert "Initialize now?" not in result.output


@pytest.mark.unit
@pytest.mark.core
def test_signal_handler_interrupts_for_lifespan_cleanup() -> None:
    """SIGTERM/SIGINT handlers should unwind instead of forcing process exit."""
    import signal
    from unittest.mock import patch

    from onetool.cli import _setup_signal_handlers

    handlers = {}

    def capture_handler(signum: int, handler: object) -> None:
        handlers[signum] = handler

    with patch("signal.signal", side_effect=capture_handler):
        _setup_signal_handlers()

    assert signal.SIGINT in handlers
    assert signal.SIGTERM in handlers
    with pytest.raises(KeyboardInterrupt):
        handlers[signal.SIGTERM](signal.SIGTERM, None)


@pytest.mark.unit
@pytest.mark.core
def test_serve_config_error_is_written_to_serve_log(tmp_path: Path) -> None:
    """Pre-handshake config failures should leave a diagnostic in serve.log."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"
    config_path.write_text("version: 2\ndirect:\n  host:\n    port: 70000\n")

    result = CliRunner().invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 1
    assert "Error loading config" in result.output
    log_text = (ot_dir / "runtime" / "logs" / "serve.log").read_text()
    assert "mcp.startup.config_error" in log_text
    assert str(config_path) in log_text
    assert "70000" in log_text


# ---------------------------------------------------------------------------
# p14: guided encrypted-secrets init step
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
def test_ask_password_sync() -> None:
    """ask_password_sync returns the value, or None on Ctrl+C."""
    from unittest.mock import patch

    with patch("ot._tui.questionary") as q:
        q.password.return_value.ask.return_value = "secret"
        from ot._tui import ask_password_sync

        assert ask_password_sync("Value") == "secret"
        q.password.return_value.ask.side_effect = KeyboardInterrupt
        assert ask_password_sync("Value") is None


@pytest.mark.unit
@pytest.mark.core
def test_init_secrets_yaml_not_in_include_and_0600(tmp_path: Path) -> None:
    """Selecting secrets.yaml materialises it at 0600 and keeps it out of include:."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    config_path = ot_dir / "onetool.yaml"

    mock_tui = MagicMock()
    mock_tui.ask_text_sync.return_value = str(config_path)
    mock_tui.ask_checkbox.return_value = ["secrets.yaml"]
    q = MagicMock()
    q.confirm.return_value.ask.return_value = (
        False  # decline "Set up encrypted secrets?"
    )

    runner = CliRunner()
    with (
        patch.dict("sys.modules", {"ot._tui": mock_tui, "questionary": q}),
        patch("onetool.cli._stdin_is_tty", return_value=True),
    ):
        result = runner.invoke(app, ["init", "-c", str(config_path)])

    assert result.exit_code == 0, result.output
    secrets = ot_dir / "secrets.yaml"
    assert secrets.exists()
    assert (secrets.stat().st_mode & 0o777) == 0o600
    data = yaml.safe_load(config_path.read_text())
    assert "secrets.yaml" not in (data.get("include") or [])


@pytest.mark.unit
@pytest.mark.core
def test_init_secrets_yaml_encrypted_step(tmp_path: Path) -> None:
    """Confirming the encrypted step runs init()+encrypt(backup=False)+audit()."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    config_path = ot_dir / "onetool.yaml"
    secrets_path = ot_dir / "secrets.yaml"

    mock_tui = MagicMock()
    # config path, then one secret name, then blank to finish
    mock_tui.ask_text_sync.side_effect = [str(config_path), "BRAVE_API_KEY", ""]
    mock_tui.ask_password_sync.return_value = "sk-secret"
    mock_tui.ask_checkbox.return_value = ["secrets.yaml"]
    q = MagicMock()
    q.confirm.return_value.ask.return_value = True  # accept "Set up encrypted secrets?"

    ot_secrets = MagicMock()
    ot_secrets.init.return_value = {"status": "stored"}
    ot_secrets.encrypt.return_value = {"file": str(secrets_path)}
    ot_secrets.audit.return_value = {"safe": True}
    ottools_mod = MagicMock()
    ottools_mod.ot_secrets = ot_secrets

    runner = CliRunner()
    with patch.dict(
        "sys.modules",
        {"ot._tui": mock_tui, "questionary": q, "ottools": ottools_mod},
    ), patch("onetool.cli._stdin_is_tty", return_value=True):
        result = runner.invoke(app, ["init", "-c", str(config_path)])

    assert result.exit_code == 0, result.output
    ot_secrets.init.assert_called_once()
    ot_secrets.encrypt.assert_called_once_with(file=str(secrets_path), backup=False)
    ot_secrets.audit.assert_called_once()


# ---------------------------------------------------------------------------
# p15: init idempotency + --force + validate hint
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
def test_init_noninteractive_rerun_is_noop(tmp_path: Path) -> None:
    """A non-interactive re-run against an existing config is a no-op (no .bak)."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / ".onetool" / "onetool.yaml"
    runner = CliRunner()
    with patch("onetool.cli._stdin_is_tty", return_value=False):
        r1 = runner.invoke(app, ["init", "-c", str(config_path)])
        assert r1.exit_code == 0, r1.output
        before = config_path.read_text()
        r2 = runner.invoke(app, ["init", "-c", str(config_path)])

    assert r2.exit_code == 0, r2.output
    assert config_path.read_text() == before  # unchanged
    assert not list((tmp_path / ".onetool").glob("*.bak"))


@pytest.mark.unit
@pytest.mark.core
def test_init_noninteractive_force_overwrites_with_bak(tmp_path: Path) -> None:
    """--force overwrites an existing config and backs the old one up as .bak."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / ".onetool" / "onetool.yaml"
    runner = CliRunner()
    with patch("onetool.cli._stdin_is_tty", return_value=False):
        runner.invoke(app, ["init", "-c", str(config_path)])
        r = runner.invoke(app, ["init", "-c", str(config_path), "--force"])

    assert r.exit_code == 0, r.output
    assert list((tmp_path / ".onetool").glob("*.bak"))


@pytest.mark.unit
@pytest.mark.core
def test_init_prints_validate_hint(tmp_path: Path) -> None:
    """After writing, init prints the `onetool init validate` next-step hint."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / ".onetool" / "onetool.yaml"
    runner = CliRunner()
    with patch("onetool.cli._stdin_is_tty", return_value=False):
        r = runner.invoke(app, ["init", "-c", str(config_path)])

    assert "onetool init validate" in r.output


# ---------------------------------------------------------------------------
# p15: --secrets missing-file startup failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
def test_serve_missing_secrets_fails_clearly(tmp_path: Path) -> None:
    """serve with a nonexistent --secrets exits non-zero with an actionable message."""
    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text("version: 2\n")
    missing = tmp_path / "nope-secrets.yaml"

    runner = CliRunner()
    r = runner.invoke(
        app, ["serve", "--config", str(config_path), "--secrets", str(missing)]
    )
    assert r.exit_code != 0
    # Rich soft-wraps long paths, so de-wrap before matching the path.
    dewrapped = r.output.replace("\n", "")
    assert "Secrets file not found" in dewrapped
    assert str(missing) in dewrapped


@pytest.mark.unit
@pytest.mark.core
def test_load_runtime_config_without_secrets_ok(tmp_path: Path) -> None:
    """Omitting --secrets loads config without error (secrets stay optional)."""
    from onetool.cli import _load_runtime_config

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text("version: 2\n")
    _load_runtime_config(config_path, None)  # must not raise


@pytest.mark.unit
@pytest.mark.core
def test_init_validate_missing_secrets_reports_error(tmp_path: Path) -> None:
    """init validate with a nonexistent --secrets names the missing path."""
    from typer.testing import CliRunner

    from onetool.cli import app

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text("version: 2\n")
    missing = tmp_path / "nope-secrets.yaml"

    runner = CliRunner()
    r = runner.invoke(
        app,
        ["init", "validate", "--config", str(config_path), "--secrets", str(missing)],
    )
    assert "Secrets file not found" in r.output or str(missing) in r.output
