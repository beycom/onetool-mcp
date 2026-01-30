"""Smoke tests for the bench CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.bench
def test_bench_help() -> None:
    """Verify bench --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "bench", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "benchmark" in result.stdout.lower()


@pytest.mark.smoke
@pytest.mark.bench
def test_bench_version() -> None:
    """Verify bench --version runs successfully."""
    result = subprocess.run(
        ["uv", "run", "bench", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "bench" in result.stdout
