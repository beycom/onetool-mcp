"""Unit tests for config settings (migrated to OneToolConfig)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_config_has_required_logging_fields() -> None:
    """Verify OneToolConfig has all required logging fields with defaults."""
    from ot.config import load_config

    config = load_config()

    # Check fields have expected defaults (migrated from Settings)
    assert config.log_level == "INFO"
    assert config.log_dir == "../logs"
    assert config.compact_max_length == 120


@pytest.mark.unit
@pytest.mark.core
def test_get_config_cached() -> None:
    """Verify get_config returns cached instance."""
    from ot.config.loader import get_config

    # Get config
    config1 = get_config()
    config2 = get_config()

    # Should be the same cached instance
    assert config1 is config2
