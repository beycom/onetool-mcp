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
    assert config.validate_code is True
    assert config.tools_dir == ["src/ot_tools/*.py"]
    assert config.prompts_file == "prompts.yaml"
    assert config.secrets_file == "secrets.yaml"


@pytest.mark.unit
@pytest.mark.core
def test_load_config_from_yaml() -> None:
    """Config loads from YAML file."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "log_level": "DEBUG",
                    "validate_code": False,
                }
            )
        )

        config = load_config(config_path)
        assert config.log_level == "DEBUG"
        assert config.validate_code is False


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion() -> None:
    """${VAR} expands from secrets.yaml, not os.environ."""
    # Clear early secrets cache to ensure fresh load
    import ot.config.mcp
    from ot.config.loader import load_config

    ot.config.mcp._early_secrets = None

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create secrets.yaml with test variable
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir()
        secrets_path = onetool_dir / "secrets.yaml"
        secrets_path.write_text(yaml.dump({"TEST_CONFIG_VAR": "/test/path"}))

        # Create config file
        config_path = onetool_dir / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "prompts_file": "${TEST_CONFIG_VAR}/prompts.yaml",
                }
            )
        )

        # Set OT_CWD so secrets are found
        old_cwd = os.environ.get("OT_CWD")
        os.environ["OT_CWD"] = tmpdir

        try:
            config = load_config(config_path)
            assert config.prompts_file == "/test/path/prompts.yaml"
        finally:
            # Clean up
            if old_cwd is not None:
                os.environ["OT_CWD"] = old_cwd
            else:
                os.environ.pop("OT_CWD", None)
            ot.config.mcp._early_secrets = None


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion_default_value() -> None:
    """${VAR:-default} uses default when variable not in secrets."""
    # Clear early secrets cache
    import ot.config.mcp
    from ot.config.loader import load_config

    ot.config.mcp._early_secrets = None

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "prompts_file": "${NONEXISTENT_VAR:-/default/path}/prompts.yaml",
                }
            )
        )

        config = load_config(config_path)
        assert config.prompts_file == "/default/path/prompts.yaml"

    # Clean up
    ot.config.mcp._early_secrets = None


@pytest.mark.unit
@pytest.mark.core
def test_secrets_expansion_error_on_missing() -> None:
    """${VAR} without default raises error when not in secrets."""
    # Clear early secrets cache
    import ot.config.mcp
    from ot.config.loader import load_config

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

        with pytest.raises(ValueError, match=r"Missing variables in secrets\.yaml"):
            load_config(config_path)

    # Clean up
    ot.config.mcp._early_secrets = None


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
    """Tools config has correct defaults."""
    from ot.config.loader import OneToolConfig

    config = OneToolConfig()

    # Check tool defaults
    assert config.tools.brave.timeout == 60.0
    assert config.tools.ground.model == "gemini-2.5-flash"
    assert config.tools.context7.timeout == 30.0
    assert config.tools.context7.docs_limit == 10
    assert config.tools.web_fetch.timeout == 30.0
    assert config.tools.web_fetch.max_length == 50000
    assert config.tools.ripgrep.timeout == 60.0
    assert config.tools.code_search.limit == 10
    assert config.tools.db.max_chars == 4000
    assert config.tools.page_view.sessions_dir == ".browse"
    assert config.tools.package.timeout == 30.0


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_partial() -> None:
    """Partial tools config merges with defaults."""
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

        # Custom values
        assert config.tools.brave.timeout == 120.0
        assert config.tools.ground.model == "gemini-2.0-flash"

        # Defaults for unconfigured tools
        assert config.tools.context7.timeout == 30.0
        assert config.tools.ripgrep.timeout == 60.0


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_validation_timeout_too_low() -> None:
    """Invalid tool config values rejected - timeout too low."""
    from pydantic import ValidationError

    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "brave": {"timeout": 0.5},  # Below minimum of 1.0
                    },
                }
            )
        )

        with pytest.raises((ValueError, ValidationError)):
            load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_validation_timeout_too_high() -> None:
    """Invalid tool config values rejected - timeout too high."""
    from pydantic import ValidationError

    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "brave": {"timeout": 500.0},  # Above maximum of 300.0
                    },
                }
            )
        )

        with pytest.raises((ValueError, ValidationError)):
            load_config(config_path)


@pytest.mark.unit
@pytest.mark.core
def test_tools_config_validation_limit_too_low() -> None:
    """Invalid tool config values rejected - limit too low."""
    from pydantic import ValidationError

    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "code_search": {"limit": 0},  # Below minimum of 1
                    },
                }
            )
        )

        with pytest.raises((ValueError, ValidationError)):
            load_config(config_path)


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
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(yaml.dump({"version": 1}))

        config = load_config(config_path)

        # _config_dir should be set to the config file's parent
        assert config._config_dir == config_dir.resolve()


@pytest.mark.unit
@pytest.mark.core
def test_prompts_file_relative_resolution() -> None:
    """prompts_file resolves relative to config directory."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "prompts_file": "prompts.yaml"})
        )

        config = load_config(config_path)

        # prompts_file should resolve relative to config dir
        expected = (config_dir / "prompts.yaml").resolve()
        assert config.get_prompts_file_path() == expected


@pytest.mark.unit
@pytest.mark.core
def test_secrets_file_relative_resolution() -> None:
    """secrets_file resolves relative to config directory."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "secrets_file": "secrets.yaml"})
        )

        config = load_config(config_path)

        # secrets_file should resolve relative to config dir
        expected = (config_dir / "secrets.yaml").resolve()
        assert config.get_secrets_file_path() == expected


@pytest.mark.unit
@pytest.mark.core
def test_prompts_file_absolute_passthrough() -> None:
    """Absolute prompts_file paths pass through unchanged."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "prompts_file": "/absolute/path/prompts.yaml"})
        )

        config = load_config(config_path)

        # Absolute path should pass through
        assert config.get_prompts_file_path() == Path("/absolute/path/prompts.yaml")


@pytest.mark.unit
@pytest.mark.core
def test_prompts_file_tilde_expansion() -> None:
    """prompts_file with ~ expands to home directory."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "prompts_file": "~/prompts.yaml"})
        )

        config = load_config(config_path)

        # ~ should expand to home directory
        expected = Path.home() / "prompts.yaml"
        assert config.get_prompts_file_path() == expected


@pytest.mark.unit
@pytest.mark.core
def test_prompts_file_parent_relative() -> None:
    """prompts_file with ../ resolves relative to config directory."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump({"version": 1, "prompts_file": "../shared/prompts.yaml"})
        )

        config = load_config(config_path)

        # ../ should resolve relative to config dir
        expected = (config_dir / ".." / "shared" / "prompts.yaml").resolve()
        assert config.get_prompts_file_path() == expected


# ==================== snippets_dir Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_single_file() -> None:
    """snippets_dir loads snippets from single file."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create external snippets file
        snippets_path = config_dir / "my-snippets.yaml"
        snippets_path.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "test_snip": {
                            "description": "Test snippet",
                            "body": "demo.foo()",
                        }
                    }
                }
            )
        )

        # Create config referencing the snippets file
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["my-snippets.yaml"],
                }
            )
        )

        config = load_config(config_path)

        assert "test_snip" in config.snippets
        assert config.snippets["test_snip"].description == "Test snippet"
        assert config.snippets["test_snip"].body == "demo.foo()"


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_glob_pattern() -> None:
    """snippets_dir loads snippets from glob pattern."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create snippets subdirectory
        snippets_subdir = config_dir / "snippets"
        snippets_subdir.mkdir()

        # Create multiple snippet files
        (snippets_subdir / "a-snippets.yaml").write_text(
            yaml.dump(
                {
                    "snippets": {
                        "snip_a": {"body": "a.call()"},
                    }
                }
            )
        )
        (snippets_subdir / "b-snippets.yaml").write_text(
            yaml.dump(
                {
                    "snippets": {
                        "snip_b": {"body": "b.call()"},
                    }
                }
            )
        )

        # Create config with glob pattern
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["snippets/*.yaml"],
                }
            )
        )

        config = load_config(config_path)

        # Both snippets should be loaded
        assert "snip_a" in config.snippets
        assert "snip_b" in config.snippets
        assert config.snippets["snip_a"].body == "a.call()"
        assert config.snippets["snip_b"].body == "b.call()"


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_merge_with_inline() -> None:
    """snippets_dir merges external snippets with inline snippets."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create external snippets file
        snippets_path = config_dir / "external.yaml"
        snippets_path.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "external_snip": {"body": "external.call()"},
                    }
                }
            )
        )

        # Create config with both inline and external snippets
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["external.yaml"],
                    "snippets": {
                        "inline_snip": {"body": "inline.call()"},
                    },
                }
            )
        )

        config = load_config(config_path)

        # Both external and inline snippets should be present
        assert "external_snip" in config.snippets
        assert "inline_snip" in config.snippets
        assert config.snippets["external_snip"].body == "external.call()"
        assert config.snippets["inline_snip"].body == "inline.call()"


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_inline_wins_on_conflict() -> None:
    """Inline snippets override external snippets on name conflict."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create external snippets file with same name as inline
        snippets_path = config_dir / "external.yaml"
        snippets_path.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "conflicting": {
                            "description": "External version",
                            "body": "external.call()",
                        },
                    }
                }
            )
        )

        # Create config where inline has same snippet name
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["external.yaml"],
                    "snippets": {
                        "conflicting": {
                            "description": "Inline version",
                            "body": "inline.call()",
                        },
                    },
                }
            )
        )

        config = load_config(config_path)

        # Inline should win
        assert config.snippets["conflicting"].description == "Inline version"
        assert config.snippets["conflicting"].body == "inline.call()"


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_invalid_file_skipped() -> None:
    """Invalid snippet files are skipped with error logged."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        snippets_subdir = config_dir / "snippets"
        snippets_subdir.mkdir()

        # Create one valid and one invalid file
        (snippets_subdir / "valid.yaml").write_text(
            yaml.dump(
                {
                    "snippets": {
                        "valid_snip": {"body": "valid.call()"},
                    }
                }
            )
        )
        (snippets_subdir / "invalid.yaml").write_text("invalid: yaml: content: ::::")

        # Create config with glob pattern
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["snippets/*.yaml"],
                }
            )
        )

        # Should not raise - invalid file is skipped
        config = load_config(config_path)

        # Valid snippet should still be loaded
        assert "valid_snip" in config.snippets
        assert config.snippets["valid_snip"].body == "valid.call()"


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_missing_pattern_warns() -> None:
    """snippets_dir with no matching files logs warning but continues."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create config with non-existent pattern
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["nonexistent/*.yaml"],
                }
            )
        )

        # Should not raise
        config = load_config(config_path)

        # Snippets should be empty (or just defaults)
        assert len(config.snippets) == 0


@pytest.mark.unit
@pytest.mark.core
def test_snippets_dir_file_without_snippets_key() -> None:
    """YAML files without 'snippets' key are skipped gracefully."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create YAML file without snippets key
        snippets_path = config_dir / "not-snippets.yaml"
        snippets_path.write_text(yaml.dump({"other_key": "value"}))

        # Create config referencing the file
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": ["not-snippets.yaml"],
                }
            )
        )

        # Should not raise
        config = load_config(config_path)

        # Snippets should be empty
        assert len(config.snippets) == 0
