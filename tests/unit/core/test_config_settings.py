"""Unit tests for config settings (migrated to OneToolConfig)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_config_has_required_logging_fields() -> None:
    """Verify OneToolConfig has all required logging fields with defaults."""
    from ot.config import OneToolConfig

    config = OneToolConfig()

    # Check fields have expected defaults (migrated from Settings)
    assert config.log_level == "INFO"
    assert config.log_dir == "runtime/logs"  # relative to .onetool/
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


@pytest.mark.unit
@pytest.mark.core
def test_auth_config_oauth() -> None:
    """Verify AuthConfig with OAuth settings."""
    from ot.config.models import AuthConfig

    config = AuthConfig(type="oauth", scopes=["tools:read", "tools:write"])
    assert config.type == "oauth"
    assert config.scopes == ["tools:read", "tools:write"]
    assert config.token is None


@pytest.mark.unit
@pytest.mark.core
def test_auth_config_bearer() -> None:
    """Verify AuthConfig with bearer token."""
    from ot.config.models import AuthConfig

    config = AuthConfig(type="bearer", token="test-token-123")
    assert config.type == "bearer"
    assert config.token == "test-token-123"
    assert config.scopes == []


@pytest.mark.unit
@pytest.mark.core
def test_mcp_server_config_with_auth() -> None:
    """Verify McpServerConfig includes auth field."""
    from ot.config.models import AuthConfig, McpServerConfig

    # Server config with OAuth auth
    config = McpServerConfig(
        type="http",
        url="https://test.invalid/mcp",
        auth=AuthConfig(type="oauth", scopes=["tools:read"]),
    )
    assert config.auth is not None
    assert config.auth.type == "oauth"
    assert config.auth.scopes == ["tools:read"]

    # Server config with no auth (default)
    config_no_auth = McpServerConfig(type="http", url="https://test.invalid/mcp")
    assert config_no_auth.auth is None
