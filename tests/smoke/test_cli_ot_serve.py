"""Smoke tests for the ot-serve CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.serve
def test_ot_serve_help() -> None:
    """Verify ot-serve --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-serve", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "OneTool MCP server" in result.stdout


@pytest.mark.smoke
@pytest.mark.serve
def test_ot_serve_version() -> None:
    """Verify ot-serve --version runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-serve", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ot-serve" in result.stdout


# ==================== Init Subcommand Tests ====================


@pytest.mark.smoke
@pytest.mark.serve
def test_ot_serve_init_help() -> None:
    """Verify ot-serve init --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-serve", "init", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "reset" in result.stdout
    assert "validate" in result.stdout
