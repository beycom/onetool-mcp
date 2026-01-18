"""Tests for secrets loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from ot.config.secrets import get_secret, get_secrets, load_secrets


@pytest.mark.unit
@pytest.mark.core
class TestLoadSecrets:
    """Tests for load_secrets function."""

    def test_loads_secrets_from_yaml_file(self, tmp_path: Path) -> None:
        """Should load secrets from a YAML file."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
BRAVE_API_KEY: "test-brave-key"
OPENAI_API_KEY: "sk-test-key"
""")

        result = load_secrets(secrets_file)

        assert result["BRAVE_API_KEY"] == "test-brave-key"
        assert result["OPENAI_API_KEY"] == "sk-test-key"

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        """Should return empty dict when file doesn't exist."""
        result = load_secrets(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        """Should return empty dict for empty YAML file."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("")

        result = load_secrets(secrets_file)
        assert result == {}

    def test_values_are_literal_no_env_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should NOT expand ${VAR_NAME} - values are literal."""
        monkeypatch.setenv("MY_SECRET_VALUE", "secret-from-env")

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "${MY_SECRET_VALUE}"
""")

        result = load_secrets(secrets_file)
        # Value is stored literally, no expansion
        assert result["API_KEY"] == "${MY_SECRET_VALUE}"

    def test_env_var_syntax_is_literal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should store ${VAR} syntax as literal string."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "${NONEXISTENT_VAR}"
""")

        result = load_secrets(secrets_file)
        # Value is stored literally
        assert result["API_KEY"] == "${NONEXISTENT_VAR}"

    def test_raises_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise ValueError for invalid YAML."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
invalid: yaml: content:
  - [broken
""")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_secrets(secrets_file)

    def test_raises_for_non_mapping_yaml(self, tmp_path: Path) -> None:
        """Should raise ValueError when YAML is not a mapping."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
- item1
- item2
""")

        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_secrets(secrets_file)

    def test_skips_none_values(self, tmp_path: Path) -> None:
        """Should skip keys with None values."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "valid-key"
EMPTY_KEY:
""")

        result = load_secrets(secrets_file)
        assert "API_KEY" in result
        assert "EMPTY_KEY" not in result

    def test_converts_non_string_values(self, tmp_path: Path) -> None:
        """Should convert non-string values to strings."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
PORT: 8080
DEBUG: true
""")

        result = load_secrets(secrets_file)
        assert result["PORT"] == "8080"
        assert result["DEBUG"] == "True"


@pytest.mark.unit
@pytest.mark.core
class TestGetSecrets:
    """Tests for get_secrets caching function."""

    def test_caches_secrets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should cache secrets after first load."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "cached-key"')

        # Reset the module's cache
        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        monkeypatch.setenv("OT_SECRETS_FILE", str(secrets_file))

        # First call loads
        result1 = get_secrets()
        # Second call uses cache
        result2 = get_secrets()

        assert result1 is result2
        assert result1["API_KEY"] == "cached-key"

        # Cleanup
        secrets_module._secrets = None

    def test_reload_forces_fresh_load(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should reload when reload=True."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "original-key"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        monkeypatch.setenv("OT_SECRETS_FILE", str(secrets_file))

        result1 = get_secrets()
        assert result1["API_KEY"] == "original-key"

        # Modify the file
        secrets_file.write_text('API_KEY: "updated-key"')

        # Without reload, should still have old value
        result2 = get_secrets()
        assert result2["API_KEY"] == "original-key"

        # With reload, should get new value
        result3 = get_secrets(reload=True)
        assert result3["API_KEY"] == "updated-key"

        # Cleanup
        secrets_module._secrets = None


@pytest.mark.unit
@pytest.mark.core
class TestGetSecret:
    """Tests for get_secret convenience function."""

    def test_returns_secret_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return secret value by name."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('MY_SECRET: "secret-value"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        monkeypatch.setenv("OT_SECRETS_FILE", str(secrets_file))

        result = get_secret("MY_SECRET")
        assert result == "secret-value"

        # Cleanup
        secrets_module._secrets = None

    def test_returns_none_for_missing_secret(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return None for non-existent secret."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('OTHER_KEY: "value"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        monkeypatch.setenv("OT_SECRETS_FILE", str(secrets_file))

        result = get_secret("NONEXISTENT")
        assert result is None

        # Cleanup
        secrets_module._secrets = None
