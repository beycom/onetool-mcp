"""Unit tests for config loader."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
@pytest.mark.core
def test_load_config_defaults() -> None:
    """Config model has correct defaults."""
    from ot.config import OneToolConfig

    config = OneToolConfig()

    # Check defaults
    assert config.version == 2
    assert config.log_level == "INFO"
    assert config.security.validate_code is True
    assert config.tools_dir == ["tools/*.py"]
    assert config.llm.base_url == "https://api.openai.com/v1"
    assert config.llm.model == "gpt-5.4-nano"
    assert config.llm.embedding_model == "text-embedding-3-small"


@pytest.mark.unit
@pytest.mark.core
def test_load_config_from_yaml(write_config) -> None:
    """Config loads from YAML file."""
    from ot.config.loader import load_config

    config_path = write_config(
        {"version": 2, "log_level": "DEBUG", "security": {"validate_code": False}}
    )

    config = load_config(config_path)
    assert config.log_level == "DEBUG"
    assert config.security.validate_code is False


@pytest.mark.unit
@pytest.mark.core
def test_compact_array_format() -> None:
    """Nested arrays are flattened (compact array format)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool" / "config"
        config_dir.mkdir(parents=True)

        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "security": {
                        "builtins": {
                            "allow": [
                                ["bool", "bytes", "dict"],  # Nested array
                                ["abs", "all", "any"],
                                "str",  # Mixed with scalar
                            ]
                        }
                    },
                }
            )
        )

        config = load_config(config_path)

        # Nested arrays should be flattened
        assert "bool" in config.security.builtins.allow
        assert "bytes" in config.security.builtins.allow
        assert "dict" in config.security.builtins.allow
        assert "abs" in config.security.builtins.allow
        assert "all" in config.security.builtins.allow
        assert "any" in config.security.builtins.allow
        assert "str" in config.security.builtins.allow


# NOTE: Variable expansion tests removed - expansion now happens at runtime
# in get_tool_config(), not during load_config(). This fixes the chicken-and-egg
# problem where secrets_file couldn't be expanded because secrets weren't loaded yet.


@pytest.mark.unit
@pytest.mark.core
def test_version_1_rejected() -> None:
    """Version 1 configs are rejected with migration message."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(yaml.dump({"version": 1}))

        with pytest.raises(ValueError, match="version 1 is not supported"):
            load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
def test_version_validation() -> None:
    """Future versions rejected with helpful error."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(yaml.dump({"version": 999}))

        with pytest.raises(ValueError, match="version 999 is not supported"):
            load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
def test_invalid_yaml_error() -> None:
    """Invalid YAML shows error."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text("invalid: yaml: content: ::::")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_defaults() -> None:
    """Tools config has core infrastructure defaults."""
    from ot.config.loader import OneToolConfig

    config = OneToolConfig()

    # Core infrastructure config (stats) is still typed
    assert config.tools.stats is not None
    # Tool configs are now stored as extra dicts (validated at runtime by tools)
    # The ToolsConfig uses ConfigDict(extra="allow")


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_partial() -> None:
    """Partial tools config is preserved in extra fields."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "tools": {
                        "brave": {"timeout": 120.0},
                        "ground": {"model": "gemini-2.0-flash"},
                    },
                }
            )
        )

        config = load_config(config_path)

        # Tool configs are stored as dicts in model_extra (validated at runtime)
        # Access via model_extra since tools now use ConfigDict(extra="allow")
        assert config.tools.model_extra.get("brave", {}).get("timeout") == 120.0
        assert config.tools.model_extra.get("ground", {}).get("model") == "gemini-2.0-flash"


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_accepts_any_tool() -> None:
    """Tool configs accept any fields (validated at runtime by tools)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "tools": {
                        "brave": {"timeout": 0.5},  # Would fail old validation
                        "custom_tool": {"my_setting": "value"},  # Unknown tool
                    },
                }
            )
        )

        # Now loads without error - validation happens at get_tool_config() time
        config = load_config(config_path)

        # Tool configs are accessible as dicts
        assert config.tools.model_extra.get("brave", {}).get("timeout") == 0.5
        assert config.tools.model_extra.get("custom_tool", {}).get("my_setting") == "value"


@pytest.mark.unit
@pytest.mark.core
def test_get_tool_config_rejects_invalid_override(tmp_path: Path) -> None:
    """Pack config schema errors are visible instead of falling back to defaults."""
    import ot.config.loader
    from pydantic import BaseModel

    from ot.config.loader import get_config, get_tool_config

    class SampleConfig(BaseModel):
        timeout: int = 30

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(
        yaml.dump({"version": 2, "tools": {"sample": {"timeout": "not-an-int"}}})
    )

    ot.config.loader._config = None
    try:
        get_config(config_path)
        with pytest.raises(ValueError, match="Invalid tools.sample configuration"):
            get_tool_config("sample", SampleConfig)
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_tool_config_rejects_unknown_override(tmp_path: Path) -> None:
    """Unknown typed pack config keys fail loudly instead of being ignored."""
    import ot.config.loader
    from pydantic import BaseModel

    from ot.config.loader import get_config, get_tool_config

    class SampleConfig(BaseModel):
        timeout: int = 30

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(
        yaml.dump({"version": 2, "tools": {"sample": {"timeout": 45, "extra": True}}})
    )

    ot.config.loader._config = None
    try:
        get_config(config_path)
        with pytest.raises(ValueError, match="Invalid tools.sample configuration"):
            get_tool_config("sample", SampleConfig)
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_tool_config_rejects_unknown_for_forbid_schema(tmp_path: Path) -> None:
    """Unknown fields remain hard errors for schemas that explicitly forbid extras."""
    import ot.config.loader
    from pydantic import BaseModel, ConfigDict

    from ot.config.loader import get_config, get_tool_config

    class SampleConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")

        timeout: int = 30

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(
        yaml.dump({"version": 2, "tools": {"sample": {"timeout": 45, "extra": True}}})
    )

    ot.config.loader._config = None
    try:
        get_config(config_path)
        with pytest.raises(ValueError, match="Invalid tools.sample configuration"):
            get_tool_config("sample", SampleConfig)
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_tool_config_rejects_removed_knowledge_keys(tmp_path: Path) -> None:
    """Removed knowledge config keys must not be silently dropped."""
    import ot.config.loader

    from ot.config.loader import get_config, get_tool_config
    from otutil.tools._knowledge.config import Config

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "version": 2,
                "tools": {
                    "knowledge": {
                        "databases": {"docs": {"path": "mem/docs.db"}},
                    },
                },
            }
        )
    )

    ot.config.loader._config = None
    try:
        get_config(config_path)
        with pytest.raises(ValueError, match="Invalid tools.knowledge configuration"):
            get_tool_config("knowledge", Config)
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_config_singleton(tmp_path: Path) -> None:
    """get_config returns singleton instance."""
    import ot.config.loader
    from ot.config.loader import get_config

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(yaml.dump({"version": 2}))

    ot.config.loader._config = None
    try:
        config1 = get_config(config_path)
        config2 = get_config()  # No path - returns cached

        assert config1 is config2
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_config_reload(tmp_path: Path) -> None:
    """get_config with reload=True reloads config."""
    import ot.config.loader
    from ot.config.loader import get_config

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(yaml.dump({"version": 2}))

    ot.config.loader._config = None
    try:
        config1 = get_config(config_path)
        config2 = get_config(config_path, reload=True)

        # Should be different instances after reload
        assert config1 is not config2
    finally:
        ot.config.loader._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_config_reload_preserves_secrets_path(tmp_path: Path) -> None:
    """Secrets are still available after reload (secrets_path preserved)."""
    import ot.config.loader
    import ot.config.secrets as secrets_module
    from ot.config.loader import get_config
    from ot.config.secrets import get_secret

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(yaml.dump({"version": 2}))

    secrets_path = tmp_path / "secrets.yaml"
    secrets_path.write_text('GEMINI_API_KEY: "test-key-123"')

    ot.config.loader._config = None
    ot.config.loader._secrets_path = None
    secrets_module._secrets = None
    try:
        # Initial load with secrets
        get_config(config_path, secrets_path=secrets_path)
        assert get_secret("GEMINI_API_KEY") == "test-key-123"

        # Simulate ot.reload(): clear both caches (no paths passed)
        ot.config.loader._config = None
        secrets_module._secrets = None

        # Reload without passing secrets_path — should reuse stored _secrets_path
        get_config()
        assert get_secret("GEMINI_API_KEY") == "test-key-123"
    finally:
        ot.config.loader._config = None
        ot.config.loader._secrets_path = None
        secrets_module._secrets = None


@pytest.mark.unit
@pytest.mark.core
def test_config_dir_tracking() -> None:
    """Config directory is tracked when loading from file."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(yaml.dump({"version": 2}))

        config = load_config(config_path)

        # _config_dir should be set to the config file's parent (not resolved)
        assert config._config_dir == config_dir


# ==================== include: Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_include_single_file() -> None:
    """include: loads and merges single file (paths relative to config dir)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create include file alongside onetool.yaml
        servers_file = onetool_dir / "servers.yaml"
        servers_file.write_text(
            yaml.dump(
                {
                    "servers": {
                        "test_server": {
                            "type": "stdio",
                            "command": "test",
                        }
                    }
                }
            )
        )

        # Create main config with include (paths relative to onetool_dir)
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["servers.yaml"],
                }
            )
        )

        config = load_config(config_path)

        assert "test_server" in config.servers
        assert config.servers["test_server"].type == "stdio"
        assert config.servers["test_server"].command == "test"


@pytest.mark.unit
@pytest.mark.core
def test_include_multiple_files_merge_order() -> None:
    """include: merges multiple files left-to-right (later wins)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create first include file alongside onetool.yaml
        first_file = onetool_dir / "first.yaml"
        first_file.write_text(
            yaml.dump(
                {
                    "alias": {
                        "a": "first.a",
                        "b": "first.b",
                    }
                }
            )
        )

        # Create second include file (should override 'a')
        second_file = onetool_dir / "second.yaml"
        second_file.write_text(
            yaml.dump(
                {
                    "alias": {
                        "a": "second.a",
                        "c": "second.c",
                    }
                }
            )
        )

        # Create main config (includes relative to onetool_dir)
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["first.yaml", "second.yaml"],
                }
            )
        )

        config = load_config(config_path)

        # 'a' should be from second (later wins)
        assert config.alias["a"] == "second.a"
        # 'b' should be from first
        assert config.alias["b"] == "first.b"
        # 'c' should be from second
        assert config.alias["c"] == "second.c"


@pytest.mark.unit
@pytest.mark.core
def test_include_inline_overrides_included() -> None:
    """Inline content in main file overrides included content."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create include file alongside onetool.yaml
        include_file = onetool_dir / "base.yaml"
        include_file.write_text(
            yaml.dump(
                {
                    "alias": {
                        "a": "included.a",
                    },
                    "log_level": "DEBUG",
                }
            )
        )

        # Create main config with inline override
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["base.yaml"],
                    "alias": {
                        "a": "inline.a",
                    },
                }
            )
        )

        config = load_config(config_path)

        # Inline should override included
        assert config.alias["a"] == "inline.a"
        # Non-overridden values from include should be preserved
        assert config.log_level == "DEBUG"


@pytest.mark.unit
@pytest.mark.core
def test_include_nested_dicts_deep_merged() -> None:
    """Nested dicts are deep-merged, not replaced."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create include file alongside onetool.yaml
        include_file = onetool_dir / "tools.yaml"
        include_file.write_text(
            yaml.dump(
                {
                    "tools": {
                        "brave": {
                            "timeout": 120.0,
                        }
                    }
                }
            )
        )

        # Create main config with different tool setting
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["tools.yaml"],
                    "tools": {
                        "context7": {
                            "timeout": 60.0,
                        }
                    },
                }
            )
        )

        config = load_config(config_path)

        # Both tool configs should be present (deep merged, stored as extra dicts)
        assert config.tools.model_extra.get("brave", {}).get("timeout") == 120.0
        assert config.tools.model_extra.get("context7", {}).get("timeout") == 60.0


@pytest.mark.unit
@pytest.mark.core
def test_include_missing_file_logs_warning() -> None:
    """Missing include file logs warning and continues."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create config with non-existent include
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["nonexistent.yaml"],
                    "log_level": "DEBUG",
                }
            )
        )

        # Should not raise
        config = load_config(config_path)

        # Main config should still work
        assert config.log_level == "DEBUG"


@pytest.mark.unit
@pytest.mark.core
def test_include_with_prompts_section() -> None:
    """include: with prompts: section works (migration from prompts_file)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create prompts file alongside onetool.yaml
        prompts_file = onetool_dir / "prompts.yaml"
        prompts_file.write_text(
            yaml.dump(
                {
                    "prompts": {
                        "instructions": "Test instructions",
                    }
                }
            )
        )

        # Create main config using include instead of prompts_file
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["prompts.yaml"],
                }
            )
        )

        config = load_config(config_path)

        assert config.prompts is not None
        assert config.prompts["instructions"] == "Test instructions"


@pytest.mark.unit
@pytest.mark.core
def test_include_with_snippets_section() -> None:
    """include: with snippets: section works (migration from snippets_dir)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Flat structure: .onetool/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create snippets file alongside onetool.yaml
        snippets_file = onetool_dir / "my-snippets.yaml"
        snippets_file.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "test_snip": {
                            "description": "Test snippet",
                            "body": "test.call()",
                        }
                    }
                }
            )
        )

        # Create main config using include instead of snippets_dir
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["my-snippets.yaml"],
                }
            )
        )

        config = load_config(config_path)

        assert "test_snip" in config.snippets
        assert config.snippets["test_snip"].body == "test.call()"


# ==================== Env Var Override Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_get_log_level_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """OT_LOG_LEVEL env var overrides config value."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_log_level

    monkeypatch.setenv("OT_LOG_LEVEL", "DEBUG")
    loader_module._config = None
    try:
        assert get_log_level() == "DEBUG"
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_log_level_invalid_env_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Invalid OT_LOG_LEVEL value falls through to config default."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_config, get_log_level

    monkeypatch.setenv("OT_LOG_LEVEL", "VERBOSE")  # Not a valid level
    config_path = tmp_path / "onetool.yaml"
    import yaml as yaml_mod
    config_path.write_text(yaml_mod.dump({"version": 2, "log_level": "WARNING"}))

    loader_module._config = None
    try:
        get_config(config_path)
        assert get_log_level() == "WARNING"
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_log_level_default_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_log_level returns 'INFO' when no env var and no config loaded."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_log_level

    monkeypatch.delenv("OT_LOG_LEVEL", raising=False)
    loader_module._config = None
    try:
        assert get_log_level() == "INFO"
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_log_dir_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """OT_LOG_DIR env var overrides config value."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_log_dir

    monkeypatch.setenv("OT_LOG_DIR", "/tmp/custom-logs")
    loader_module._config = None
    try:
        assert get_log_dir() == "/tmp/custom-logs"
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_log_dir_default_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_log_dir returns the runtime log path when no env var and no config loaded."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_log_dir

    monkeypatch.delenv("OT_LOG_DIR", raising=False)
    loader_module._config = None
    try:
        assert get_log_dir() == "runtime/logs"
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_compact_max_length_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """OT_COMPACT_MAX_LENGTH env var overrides config value."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_compact_max_length

    monkeypatch.setenv("OT_COMPACT_MAX_LENGTH", "200")
    loader_module._config = None
    try:
        assert get_compact_max_length() == 200
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_compact_max_length_invalid_env_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Non-integer OT_COMPACT_MAX_LENGTH falls through to config default."""
    import yaml as yaml_mod

    import ot.config.loader as loader_module
    from ot.config.loader import get_compact_max_length, get_config

    monkeypatch.setenv("OT_COMPACT_MAX_LENGTH", "notanumber")
    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(yaml_mod.dump({"version": 2, "compact_max_length": 80}))

    loader_module._config = None
    try:
        get_config(config_path)
        assert get_compact_max_length() == 80
    finally:
        loader_module._config = None


@pytest.mark.unit
@pytest.mark.core
def test_get_compact_max_length_default_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_compact_max_length returns 120 when no env var and no config loaded."""
    import ot.config.loader as loader_module
    from ot.config.loader import get_compact_max_length

    monkeypatch.delenv("OT_COMPACT_MAX_LENGTH", raising=False)
    loader_module._config = None
    try:
        assert get_compact_max_length() == 120
    finally:
        loader_module._config = None


# ==================== Deep Merge Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_deep_merge_basic() -> None:
    """_deep_merge merges dicts correctly."""
    from ot.config.loader import _deep_merge

    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"y": 30, "z": 40}, "c": 3}

    result = _deep_merge(base, override)

    assert result["a"] == 1
    assert result["b"]["x"] == 10  # From base
    assert result["b"]["y"] == 30  # From override
    assert result["b"]["z"] == 40  # From override
    assert result["c"] == 3  # From override


@pytest.mark.unit
@pytest.mark.core
def test_deep_merge_list_replacement() -> None:
    """_deep_merge replaces lists entirely (no merge)."""
    from ot.config.loader import _deep_merge

    base = {"items": [1, 2, 3]}
    override = {"items": [4, 5]}

    result = _deep_merge(base, override)

    # Lists are replaced, not merged
    assert result["items"] == [4, 5]


@pytest.mark.unit
@pytest.mark.core
def test_deep_merge_type_mismatch() -> None:
    """_deep_merge replaces when types don't match."""
    from ot.config.loader import _deep_merge

    base = {"value": {"nested": "dict"}}
    override = {"value": "scalar"}

    result = _deep_merge(base, override)

    # Override wins even with type mismatch
    assert result["value"] == "scalar"


# ==================== Three-Tier Include Resolution Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_path_config_dir_first() -> None:
    """_resolve_include_path finds file in config_dir first."""
    from ot.config.loader import _resolve_include_path

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir).resolve()
        include_file = config_dir / "test.yaml"
        include_file.write_text("test: value")

        result = _resolve_include_path("test.yaml", config_dir)

        # Both paths should resolve to the same location
        assert result is not None
        assert result.resolve() == include_file.resolve()


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_path_absolute_used_as_is(tmp_path: Path) -> None:
    """_resolve_include_path uses absolute paths directly."""
    from ot.config.loader import _resolve_include_path

    # Create a file with absolute path
    abs_file = tmp_path / "absolute.yaml"
    abs_file.write_text("absolute: test")

    result = _resolve_include_path(str(abs_file), Path("/some/other/dir"))

    assert result == abs_file


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_path_not_found() -> None:
    """_resolve_include_path returns None when file not found anywhere."""
    from ot.config.loader import _resolve_include_path

    with tempfile.TemporaryDirectory() as tmpdir:
        result = _resolve_include_path("nonexistent-file.yaml", Path(tmpdir))

        assert result is None


# ==================== Inheritance Tests ====================


@pytest.mark.unit
@pytest.mark.unit
@pytest.mark.core
def test_inherit_deep_merges_tools() -> None:
    """Inheritance deep-merges nested tool configurations."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create project config with partial tool override
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "tools": {
                        "brave": {"timeout": 120.0},
                    },
                }
            )
        )

        config = load_config(config_path)

        # Override should apply (tool configs stored as extra dicts)
        assert config.tools.model_extra.get("brave", {}).get("timeout") == 120.0


# ==================== Runtime Variable Expansion Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_get_tool_config_expands_vars_at_runtime() -> None:
    """get_tool_config() expands ${VAR} at runtime, not during load_config()."""
    import ot.config.loader as loader_module
    import ot.config.secrets as secrets_module
    from ot.config.loader import get_config, get_tool_config

    # Clean slate
    secrets_module._secrets = None
    loader_module._config = None

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create config with ${VAR} in tool config
        config_dir = Path(tmpdir) / ".onetool" / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "tools": {
                        "mypack": {
                            "api_url": "https://test.invalid/api/${API_VERSION}",
                            "cache_dir": "${CACHE_DIR}/mypack",
                        }
                    },
                    "env": {
                        "CACHE_DIR": "/tmp/cache",
                    },
                }
            )
        )

        # Create secrets file
        secrets_path = config_dir / "secrets.yaml"
        secrets_path.write_text('API_VERSION: "v2"')

        # Load and cache config with explicit secrets path
        config = get_config(config_path, secrets_path=secrets_path)

        # Raw config should still have ${VAR} patterns
        raw_url = config.tools.model_extra.get("mypack", {}).get("api_url")
        assert "${API_VERSION}" in raw_url

        # Now get_tool_config() should expand at runtime
        tool_cfg = get_tool_config("mypack")

        # Variables should be expanded
        assert tool_cfg["api_url"] == "https://test.invalid/api/v2"
        assert tool_cfg["cache_dir"] == "/tmp/cache/mypack"

        # Cleanup
        secrets_module._secrets = None
        loader_module._config = None
