"""Unit tests for root runtime CLI mode dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.serve
def test_default_invocation_starts_stdio_root(tmp_path: Path) -> None:
    """Root invocation remains supported with an explicit-command warning."""
    from onetool.cli import app
    from ot import server

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with (
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.object(server, "run_root_server") as run_root_server,
    ):
        result = CliRunner().invoke(app, ["--config", str(config)])

    assert result.exit_code == 0
    assert "prefer explicit runtime invocation" in result.output
    assert "onetool serve --config" in result.output
    assert "onetool.yaml" in result.output
    run_root_server.assert_called_once_with(transport="stdio")


@pytest.mark.unit
@pytest.mark.serve
def test_serve_defaults_to_stdio_root(tmp_path: Path) -> None:
    """serve dispatches stdio root mode by default."""
    from onetool.cli import app
    from ot import server

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with (
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.object(server, "run_root_server") as run_root_server,
    ):
        result = CliRunner().invoke(app, ["serve", "--config", str(config)])

    assert result.exit_code == 0
    assert "prefer explicit runtime invocation" not in result.output
    run_root_server.assert_called_once_with(transport="stdio")


@pytest.mark.unit
@pytest.mark.serve
def test_serve_http_transport_passes_options(tmp_path: Path) -> None:
    """serve --transport http dispatches Streamable HTTP root settings."""
    from onetool.cli import app
    from ot import server

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with (
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.object(server, "run_root_server") as run_root_server,
    ):
        result = CliRunner().invoke(
            app,
            [
                "serve",
                "--config",
                str(config),
                "--transport",
                "http",
                "--host",
                "127.0.0.1",
                "--port",
                "8768",
                "--path",
                "/root-mcp",
            ],
        )

    assert result.exit_code == 0
    run_root_server.assert_called_once_with(
        transport="streamable-http",
        host="127.0.0.1",
        port=8768,
        path="/root-mcp",
    )


@pytest.mark.unit
@pytest.mark.serve
def test_serve_http_short_transport_option_passes_options(tmp_path: Path) -> None:
    """serve -t http maps to Streamable HTTP root transport."""
    from onetool.cli import app
    from ot import server

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with (
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.object(server, "run_root_server") as run_root_server,
    ):
        result = CliRunner().invoke(
            app,
            ["serve", "-c", str(config), "-t", "http"],
        )

    assert result.exit_code == 0
    run_root_server.assert_called_once_with(
        transport="streamable-http",
        host="127.0.0.1",
        port=8767,
        path="/mcp",
    )


@pytest.mark.unit
@pytest.mark.serve
def test_serve_http_rejects_invalid_path(tmp_path: Path) -> None:
    """HTTP root path validation fails before server startup."""
    from onetool.cli import app

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with patch("ot.server.run_root_server") as run_root_server:
        result = CliRunner().invoke(
            app,
            ["serve", "--config", str(config), "--transport", "http", "--path", "mcp"],
        )

    assert result.exit_code == 2
    assert "--path must start with '/'" in result.output
    run_root_server.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_serve_http_command_is_removed(tmp_path: Path) -> None:
    """serve-http is not retained as a compatibility command."""
    from onetool.cli import app

    config = tmp_path / "onetool.yaml"
    config.write_text("tools: {}\n", encoding="utf-8")

    with patch("ot.server.run_root_server") as run_root_server:
        result = CliRunner().invoke(app, ["serve-http", "--config", str(config)])

    assert result.exit_code != 0
    assert "No such command" in result.output
    run_root_server.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_admin_help_lists_serve_command() -> None:
    """admin group exposes the serve command."""
    from onetool.cli import app

    result = CliRunner().invoke(app, ["admin", "--help"])

    assert result.exit_code == 0
    assert "serve" in result.output


@pytest.mark.unit
@pytest.mark.serve
def test_admin_serve_passes_default_args(tmp_path: Path) -> None:
    """admin serve uses default Admin App and scan ports."""
    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    with patch("onetool.admin.server.serve_admin_app") as serve_admin_app:
        result = CliRunner().invoke(app, ["admin", "serve", "--ot-dir", str(ot_dir)])

    assert result.exit_code == 0
    assert "http://127.0.0.1:8760" in result.output
    serve_admin_app.assert_called_once_with(
        ot_dir=ot_dir,
        port=8760,
        direct_start_port=8765,
        scan_max=10,
    )


@pytest.mark.unit
@pytest.mark.serve
def test_admin_serve_passes_port_and_scan_overrides(tmp_path: Path) -> None:
    """admin serve passes Admin App and Direct API scan overrides."""
    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    with patch("onetool.admin.server.serve_admin_app") as serve_admin_app:
        result = CliRunner().invoke(
            app,
            [
                "admin",
                "serve",
                "--ot-dir",
                str(ot_dir),
                "--port",
                "8761",
                "--direct-start-port",
                "9000",
                "--scan-max",
                "20",
            ],
        )

    assert result.exit_code == 0
    assert "http://127.0.0.1:8761" in result.output
    serve_admin_app.assert_called_once_with(
        ot_dir=ot_dir,
        port=8761,
        direct_start_port=9000,
        scan_max=20,
    )


@pytest.mark.unit
@pytest.mark.serve
def test_admin_serve_rejects_relative_ot_dir() -> None:
    """admin serve requires an absolute ot-dir after expansion."""
    from onetool.cli import app

    with patch("onetool.admin.server.serve_admin_app") as serve_admin_app:
        result = CliRunner().invoke(app, ["admin", "serve", "--ot-dir", ".onetool"])

    assert result.exit_code == 2
    assert "--ot-dir must be an absolute path" in result.output
    serve_admin_app.assert_not_called()
