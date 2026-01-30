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
    """Config loads with defaults when file missing."""
    from ot.config.loader import OneToolConfig

    config = OneToolConfig()

    # Check defaults
    assert config.version == 1
    assert config.log_level == "INFO"
    assert config.security.validate_code is True
    assert config.tools_dir == ["tools/*.py"]
    assert config.secrets_file == "config/secrets.yaml"


@pytest.mark.unit
@pytest.mark.core
def test_load_config_from_yaml(write_config) -> None:
    """Config loads from YAML file."""
    from ot.config.loader import load_config

    config_path = write_config(
        {"version": 1, "log_level": "DEBUG", "security": {"validate_code": False}}
    )

    config = load_config(config_path)
    assert config.log_level == "DEBUG"
    assert config.security.validate_code is False


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion() -> None:
    """${VAR} expands from secrets.yaml, not os.environ."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create secrets.yaml with test variable in config/ subdirectory
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)
        secrets_path = config_dir / "secrets.yaml"
        secrets_path.write_text(yaml.dump({"TEST_CONFIG_VAR": "/test/path"}))

        # Create config file
        config_path = config_dir / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "secrets_file": "${TEST_CONFIG_VAR}/secrets.yaml",
                }
            )
        )

        # Set OT_CWD so secrets are found
        old_cwd = os.environ.get("OT_CWD")
        os.environ["OT_CWD"] = tmpdir

        try:
            config = load_config(config_path)
            assert config.secrets_file == "/test/path/secrets.yaml"
        finally:
            if old_cwd is not None:
                os.environ["OT_CWD"] = old_cwd
            else:
                os.environ.pop("OT_CWD", None)


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion_default_value() -> None:
    """${VAR:-default} uses default when variable not in secrets."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "secrets_file": "${NONEXISTENT_VAR:-/default/path}/secrets.yaml",
                }
            )
        )

        config = load_config(config_path)
        assert config.secrets_file == "/default/path/secrets.yaml"


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion_error_on_missing() -> None:
    """${VAR} without default raises error when not in secrets."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "secrets_file": "${MISSING_VAR}/secrets.yaml",
                }
            )
        )

        with pytest.raises(ValueError, match=r"Missing variables in secrets\.yaml"):
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

    # Core infrastructure config (msg, stats) is still typed
    assert config.tools.msg is not None
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
                    "version": 1,
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
                    "version": 1,
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
def test_get_config_singleton() -> None:
    """get_config returns singleton instance."""
    # Reset global config
    import ot.config.loader
    from ot.config.loader import get_config

    ot.config.loader._config = None

    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


@pytest.mark.unit
@pytest.mark.core
def test_get_config_reload() -> None:
    """get_config with reload=True reloads config."""
    # Reset global config
    import ot.config.loader
    from ot.config.loader import get_config

    ot.config.loader._config = None

    config1 = get_config()
    config2 = get_config(reload=True)

    # Should be different instances after reload
    assert config1 is not config2


@pytest.mark.unit
@pytest.mark.core
def test_config_dir_tracking() -> None:
    """Config directory is tracked when loading from file."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(yaml.dump({"version": 1}))

        config = load_config(config_path)

        # _config_dir should be set to the config file's parent
        assert config._config_dir == config_dir.resolve()


@pytest.mark.unit
@pytest.mark.core
def test_secrets_file_relative_resolution() -> None:
    """secrets_file resolves relative to OT_DIR (.onetool/)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Standard directory structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "secrets_file": "config/secrets.yaml"})
        )

        config = load_config(config_path)

        # secrets_file should resolve relative to OT_DIR (.onetool/)
        expected = (onetool_dir / "config" / "secrets.yaml").resolve()
        assert config.get_secrets_file_path() == expected


# ==================== include: Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_include_single_file() -> None:
    """include: loads and merges single file (paths relative to OT_DIR)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create include file in config/ subdirectory
        servers_file = config_dir / "servers.yaml"
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

        # Create main config with include (paths relative to OT_DIR)
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "include": ["config/servers.yaml"],
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
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create first include file in OT_DIR
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

        # Create main config (includes relative to OT_DIR)
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
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
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create include file in OT_DIR
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
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
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
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create include file in OT_DIR
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
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
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
                    "version": 1,
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
def test_include_circular_detection() -> None:
    """Circular includes are detected and skipped."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create file A in OT_DIR that includes file B
        file_a = onetool_dir / "a.yaml"
        file_a.write_text(
            yaml.dump(
                {
                    "include": ["b.yaml"],
                    "alias": {"from_a": "a.value"},
                }
            )
        )

        # Create file B in OT_DIR that includes file A (circular)
        file_b = onetool_dir / "b.yaml"
        file_b.write_text(
            yaml.dump(
                {
                    "include": ["a.yaml"],
                    "alias": {"from_b": "b.value"},
                }
            )
        )

        # Create main config
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "include": ["a.yaml"],
                }
            )
        )

        # Should not raise or loop forever
        config = load_config(config_path)

        # Both files should be processed (once each)
        assert "from_a" in config.alias
        assert "from_b" in config.alias


@pytest.mark.unit
@pytest.mark.core
def test_include_with_prompts_section() -> None:
    """include: with prompts: section works (migration from prompts_file)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create prompts file in OT_DIR with prompts: key
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
        # Use inherit: none to isolate test from bundled defaults
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "none",
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
        # Standard structure: .onetool/config/onetool.yaml
        onetool_dir = Path(tmpdir) / ".onetool"
        config_dir = onetool_dir / "config"
        config_dir.mkdir(parents=True)

        # Create snippets file in OT_DIR with snippets: key
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
        # Use inherit: none to isolate test from bundled defaults
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "none",
                    "include": ["my-snippets.yaml"],
                }
            )
        )

        config = load_config(config_path)

        assert "test_snip" in config.snippets
        assert config.snippets["test_snip"].body == "test.call()"


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
def test_resolve_include_path_global_fallback(tmp_path: Path) -> None:
    """_resolve_include_path falls back to global OT_DIR when not in ot_dir."""
    from ot.config.loader import _resolve_include_path
    from ot.paths import get_global_dir

    # Create file in global OT_DIR (~/.onetool/) but not in local ot_dir
    global_ot_dir = get_global_dir()
    global_ot_dir.mkdir(parents=True, exist_ok=True)
    global_file = global_ot_dir / "global-only.yaml"

    try:
        global_file.write_text("global: test")

        # local ot_dir doesn't have the file
        result = _resolve_include_path("global-only.yaml", tmp_path)

        assert result == global_file
    finally:
        if global_file.exists():
            global_file.unlink()


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_path_bundled_fallback(tmp_path: Path) -> None:
    """_resolve_include_path falls back to bundled when not in config_dir or global."""
    from ot.config.loader import _resolve_include_path
    from ot.paths import get_bundled_config_dir

    # prompts.yaml exists in bundled defaults
    bundled_dir = get_bundled_config_dir()
    bundled_dir / "prompts.yaml"

    # tmp_path doesn't have the file, and we assume global doesn't either
    result = _resolve_include_path("prompts.yaml", tmp_path)

    # Should find it in bundled
    assert result is not None
    assert result.name == "prompts.yaml"


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
@pytest.mark.core
def test_inherit_none_no_merging() -> None:
    """inherit: none prevents any inheritance."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create project config with inherit: none
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "none",
                    "log_level": "ERROR",
                }
            )
        )

        config = load_config(config_path)

        # Should use values from config only (defaults from model, not from global/bundled)
        assert config.inherit == "none"
        assert config.log_level == "ERROR"


@pytest.mark.unit
@pytest.mark.core
def test_inherit_bundled_merges_bundled_only() -> None:
    """inherit: bundled merges from bundled defaults only."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create project config with inherit: bundled and override
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "bundled",
                    "log_level": "ERROR",
                }
            )
        )

        config = load_config(config_path)

        # Should have bundled inheritance
        assert config.inherit == "bundled"
        # Our override should apply
        assert config.log_level == "ERROR"


@pytest.mark.unit
@pytest.mark.core
def test_inherit_global_is_default() -> None:
    """inherit defaults to 'global' when not specified."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create project config without inherit field
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "log_level": "DEBUG",
                }
            )
        )

        config = load_config(config_path)

        # Default should be 'global'
        assert config.inherit == "global"
        # Our override should apply
        assert config.log_level == "DEBUG"


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
                    "version": 1,
                    "inherit": "bundled",
                    "tools": {
                        "brave": {"timeout": 120.0},
                    },
                }
            )
        )

        config = load_config(config_path)

        # Override should apply (tool configs stored as extra dicts)
        assert config.tools.model_extra.get("brave", {}).get("timeout") == 120.0
        # Other tool configs may come from bundled defaults if present


@pytest.mark.unit
@pytest.mark.core
def test_include_three_tier_fallback() -> None:
    """include: uses three-tier fallback resolution."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create project config that includes bundled prompts.yaml
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "none",
                    "include": ["prompts.yaml"],  # Should fall back to bundled
                }
            )
        )

        config = load_config(config_path)

        # Should have loaded prompts from bundled defaults
        assert config.prompts is not None
