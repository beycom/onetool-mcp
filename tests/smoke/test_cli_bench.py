"""Smoke tests for the ot-bench CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.bench
def test_ot_bench_help() -> None:
    """Verify ot-bench --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-bench", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "benchmark" in result.stdout.lower()


@pytest.mark.smoke
@pytest.mark.bench
def test_ot_bench_version() -> None:
    """Verify ot-bench --version runs successfully."""
    result = subprocess.run(
        ["uv", "run", "ot-bench", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ot-bench" in result.stdout
