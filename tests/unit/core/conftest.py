"""Fixtures for core unit tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


@pytest.fixture
def config_dir() -> Generator[Path, None, None]:
    """Create a temporary .onetool config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        yield config_dir


@pytest.fixture
def write_config(config_dir: Path) -> Callable[[dict], Path]:
    """Write a config dict to ot-serve.yaml and return the path."""

    def _write(data: dict) -> Path:
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(yaml.dump(data))
        return config_path

    return _write


@pytest.fixture(autouse=True)
def reset_secrets_cache() -> Generator[None, None, None]:
    """Reset secrets cache before and after each test."""
    try:
        import ot.config.mcp

        ot.config.mcp._early_secrets = None
        yield
        ot.config.mcp._early_secrets = None
    except ImportError:
        yield
