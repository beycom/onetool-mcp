"""Unit tests for root runtime CLI mode dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


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

