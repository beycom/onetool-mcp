"""Smoke tests for the ot-browse CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.browse
def test_ot_browse_help() -> None:
    """Verify ot-browse --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-browse", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Browser Inspector" in result.stdout
