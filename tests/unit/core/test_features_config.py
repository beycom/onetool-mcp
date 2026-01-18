"""Unit tests for configuration features.

Tests configuration integration with the execution system:
- Config loading produces usable configuration
- Config validation catches errors early
- Variable expansion works in config values

Note: Comprehensive config loading tests are in test_config_loader.py.
These tests focus on config's impact on execution features.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
@pytest.mark.core
class TestConfigLoading:
    """Test config loading produces usable configuration."""

    def test_load_default_config(self) -> None:
        """Default config loads with expected structure."""
        from ot.config.loader import OneToolConfig

        config = OneToolConfig()

        # Essential fields exist
        assert config.version == 1
        assert config.log_level in ["INFO", "DEBUG", "WARNING", "ERROR"]
        assert isinstance(config.tools_dir, list)
        assert isinstance(config.alias, dict)  # Note: singular 'alias'
        assert isinstance(config.snippets, dict)

    def test_load_custom_config(self) -> None:
        """Custom config values override defaults."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "log_level": "DEBUG",
                        "alias": {"test_alias": "demo.foo"},  # Note: singular 'alias'
                    }
                )
            )

            config = load_config(config_path)

            assert config.log_level == "DEBUG"
            assert "test_alias" in config.alias
            assert config.alias["test_alias"] == "demo.foo"


@pytest.mark.unit
@pytest.mark.core
class TestConfigValidation:
    """Test config validation catches invalid configurations."""

    def test_invalid_version_rejected(self) -> None:
        """Future versions are rejected with helpful error."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(yaml.dump({"version": 999}))

            with pytest.raises(ValueError, match="version 999 is not supported"):
                load_config(config_path)

    def test_invalid_yaml_rejected(self) -> None:
        """Malformed YAML produces clear error."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text("invalid: yaml: content: ::::")

            with pytest.raises(ValueError, match="Invalid YAML"):
                load_config(config_path)

    def test_invalid_tool_timeout_rejected(self) -> None:
        """Invalid tool config values rejected."""
        from pydantic import ValidationError

        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "tools": {
                            "brave": {"timeout": 0.5},  # Below minimum
                        },
                    }
                )
            )

            with pytest.raises((ValueError, ValidationError)):
                load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
class TestConfigVariableExpansion:
    """Test variable expansion in config values."""

    def test_variable_with_default(self) -> None:
        """${VAR:-default} uses default when variable not set."""
        from ot.config.loader import load_config

        # Clear any cached secrets
        import ot.config.mcp

        ot.config.mcp._early_secrets = None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "prompts_file": "${NONEXISTENT_VAR:-/default}/prompts.yaml",
                    }
                )
            )

            config = load_config(config_path)
            assert config.prompts_file == "/default/prompts.yaml"

        # Clean up
        ot.config.mcp._early_secrets = None

    def test_missing_variable_error(self) -> None:
        """${VAR} without default raises error when not defined."""
        from ot.config.loader import load_config

        # Clear any cached secrets
        import ot.config.mcp

        ot.config.mcp._early_secrets = None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "prompts_file": "${MISSING_VAR}/prompts.yaml",
                    }
                )
            )

            with pytest.raises(ValueError, match=r"Missing variables"):
                load_config(config_path)

        # Clean up
        ot.config.mcp._early_secrets = None
