"""Smoke tests for config loading."""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.core
def test_config_imports() -> None:
    """Verify config module imports successfully."""
    from ot.config import OneToolConfig, get_config, load_config

    # These should all be importable
    assert OneToolConfig is not None
    assert get_config is not None
    assert load_config is not None


@pytest.mark.smoke
@pytest.mark.core
def test_config_has_logging_settings() -> None:
    """Verify OneToolConfig has logging settings with defaults."""
    from ot.config import load_config

    # Load default config
    config = load_config()
    assert config is not None
    # Check logging settings exist (migrated from Settings)
    assert hasattr(config, "log_level")
    assert hasattr(config, "log_dir")
    assert hasattr(config, "compact_max_length")


@pytest.mark.smoke
@pytest.mark.core
def test_load_config_default() -> None:
    """Verify config loading works (uses defaults if no file found)."""
    from ot.config import load_config

    # Should not raise even if no config file exists
    config = load_config()
    assert config is not None
