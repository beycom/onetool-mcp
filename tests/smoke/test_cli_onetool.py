"""Smoke tests for the onetool CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_help() -> None:
    """Verify onetool --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "OneTool MCP server" in result.stdout


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_version() -> None:
    """Verify onetool --version runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "onetool" in result.stdout


# ==================== Init Subcommand Tests ====================


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_init_help() -> None:
    """Verify onetool init --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "init", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "reset" in result.stdout
    assert "validate" in result.stdout
