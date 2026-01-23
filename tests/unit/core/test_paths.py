"""Unit tests for ot.paths module.

Tests path resolution logic including:
- get_effective_cwd() with and without OT_CWD
- Config resolution order
- .env loading precedence
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_get_effective_cwd_returns_cwd_by_default() -> None:
    """Verify get_effective_cwd() returns Path.cwd() when OT_CWD not set."""
    from ot.paths import get_effective_cwd

    with patch.dict(os.environ, {}, clear=False):
        # Ensure OT_CWD is not set
        os.environ.pop("OT_CWD", None)
        result = get_effective_cwd()

    assert result == Path.cwd()


@pytest.mark.unit
@pytest.mark.core
def test_get_effective_cwd_uses_ot_cwd_env_var() -> None:
    """Verify get_effective_cwd() uses OT_CWD when set."""
    from ot.paths import get_effective_cwd

    with patch.dict(os.environ, {"OT_CWD": "/tmp/test-project"}):
        result = get_effective_cwd()

    # Path is resolved, so compare resolved paths (handles symlinks like /tmp -> /private/tmp)
    assert result == Path("/tmp/test-project").resolve()


@pytest.mark.unit
@pytest.mark.core
def test_get_effective_cwd_resolves_relative_ot_cwd() -> None:
    """Verify get_effective_cwd() resolves relative OT_CWD paths."""
    from ot.paths import get_effective_cwd

    with patch.dict(os.environ, {"OT_CWD": "demo"}):
        result = get_effective_cwd()

    # Should be resolved to absolute path
    assert result.is_absolute()
    assert result.name == "demo"


@pytest.mark.unit
@pytest.mark.core
def test_get_global_dir_returns_home_onetool() -> None:
    """Verify get_global_dir() returns ~/.onetool/."""
    from ot.paths import get_global_dir

    result = get_global_dir()

    assert result == Path.home() / ".onetool"


@pytest.mark.unit
@pytest.mark.core
def test_get_project_dir_returns_none_when_not_exists(tmp_path: Path) -> None:
    """Verify get_project_dir() returns None when .onetool/ doesn't exist."""
    from ot.paths import get_project_dir

    result = get_project_dir(start=tmp_path)

    assert result is None


@pytest.mark.unit
@pytest.mark.core
def test_get_project_dir_returns_path_when_exists(tmp_path: Path) -> None:
    """Verify get_project_dir() returns path when .onetool/ exists."""
    from ot.paths import get_project_dir

    # Create .onetool directory
    onetool_dir = tmp_path / ".onetool"
    onetool_dir.mkdir()

    result = get_project_dir(start=tmp_path)

    assert result == onetool_dir


@pytest.mark.unit
@pytest.mark.core
def test_get_project_dir_uses_effective_cwd(tmp_path: Path) -> None:
    """Verify get_project_dir() uses get_effective_cwd() when no start given."""
    from ot.paths import get_project_dir

    # Create .onetool in tmp_path
    onetool_dir = tmp_path / ".onetool"
    onetool_dir.mkdir()

    with patch.dict(os.environ, {"OT_CWD": str(tmp_path)}):
        result = get_project_dir()

    assert result == onetool_dir


@pytest.mark.unit
@pytest.mark.core
def test_get_config_path_project_first(tmp_path: Path) -> None:
    """Verify get_config_path() checks project config first."""
    from ot.paths import get_config_path

    # Create project config
    project_onetool = tmp_path / ".onetool"
    project_onetool.mkdir()
    project_config = project_onetool / "ot-serve.yaml"
    project_config.write_text("# project config")

    with patch.dict(os.environ, {"OT_CWD": str(tmp_path)}):
        result = get_config_path("ot-serve")

    assert result == project_config


@pytest.mark.unit
@pytest.mark.core
def test_get_config_path_falls_back_to_global(tmp_path: Path) -> None:
    """Verify get_config_path() falls back to global when no project config."""
    from ot.paths import get_config_path, get_global_dir

    # Ensure no project config exists
    with patch.dict(os.environ, {"OT_CWD": str(tmp_path)}):
        # Create global config
        global_dir = get_global_dir()
        global_dir.mkdir(parents=True, exist_ok=True)
        global_config = global_dir / "ot-serve.yaml"

        # Only test if we can write to global dir
        try:
            global_config.write_text("# global config")
            result = get_config_path("ot-serve")
            assert result == global_config
        finally:
            # Cleanup
            if global_config.exists():
                global_config.unlink()


@pytest.mark.unit
@pytest.mark.core
def test_get_config_path_returns_none_when_not_found(tmp_path: Path) -> None:
    """Verify get_config_path() returns None when config not found."""
    from ot.paths import get_config_path

    with patch.dict(os.environ, {"OT_CWD": str(tmp_path)}):
        result = get_config_path("nonexistent-cli")

    assert result is None


@pytest.mark.unit
@pytest.mark.core
def test_expand_path_expands_home() -> None:
    """Verify expand_path() expands ~ to home directory."""
    from ot.paths import expand_path

    result = expand_path("~/projects")

    assert result == Path.home() / "projects"


@pytest.mark.unit
@pytest.mark.core
def test_expand_path_does_not_expand_env_vars() -> None:
    """Verify expand_path() does NOT expand ${VAR} (use ~ instead)."""
    from ot.paths import expand_path

    with patch.dict(os.environ, {"MY_DIR": "/custom/path"}):
        result = expand_path("${MY_DIR}/subdir")

    # ${VAR} is not expanded - only ~ is expanded
    # The result contains the literal ${MY_DIR} resolved to absolute path
    assert "${MY_DIR}" in str(result)


# ==================== Bundled Config Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_get_bundled_config_dir_returns_path() -> None:
    """Verify get_bundled_config_dir() returns a valid Path."""
    from ot.paths import get_bundled_config_dir

    result = get_bundled_config_dir()

    assert isinstance(result, Path)
    # Should point to the defaults directory
    assert result.name == "defaults"


@pytest.mark.unit
@pytest.mark.core
def test_get_bundled_config_dir_contains_yaml_files() -> None:
    """Verify bundled config directory contains expected YAML files."""
    from ot.paths import get_bundled_config_dir

    bundled_dir = get_bundled_config_dir()

    # Should contain key config files
    assert (bundled_dir / "ot-serve.yaml").exists()
    assert (bundled_dir / "prompts.yaml").exists()
    assert (bundled_dir / "snippets.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_ensure_global_dir_creates_directory(tmp_path: Path) -> None:
    """Verify ensure_global_dir() creates ~/.onetool/ with configs."""
    from ot.paths import ensure_global_dir

    # Use a fake home directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    with patch.dict(os.environ, {"HOME": str(fake_home)}):
        # Import fresh to pick up new HOME
        import importlib

        import ot.paths

        importlib.reload(ot.paths)

        result = ot.paths.ensure_global_dir(quiet=True)

        # Should create the directory
        assert result.exists()
        assert result.name == ".onetool"


@pytest.mark.unit
@pytest.mark.core
def test_ensure_global_dir_idempotent(tmp_path: Path) -> None:
    """Verify ensure_global_dir() is idempotent (no error on second call)."""
    from ot.paths import ensure_global_dir, get_global_dir

    # Create the directory manually first
    global_dir = get_global_dir()
    global_dir.mkdir(parents=True, exist_ok=True)

    # Should not raise, should return existing directory
    result = ensure_global_dir(quiet=True)

    assert result == global_dir
    assert result.exists()


# ==================== Global Templates Tests ====================


@pytest.mark.unit
@pytest.mark.core
def test_get_global_templates_dir_returns_path() -> None:
    """Verify get_global_templates_dir() returns a valid Path."""
    from ot.paths import get_global_templates_dir

    result = get_global_templates_dir()

    assert isinstance(result, Path)
    # Should point to the global_templates directory
    assert result.name == "global_templates"


@pytest.mark.unit
@pytest.mark.core
def test_get_global_templates_dir_contains_yaml_files() -> None:
    """Verify global templates directory contains expected template files."""
    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()

    # Should contain key template files
    assert (templates_dir / "ot-serve.yaml").exists()
    assert (templates_dir / "snippets.yaml").exists()
    assert (templates_dir / "servers.yaml").exists()
    # secrets-template.yaml (named to avoid gitignore)
    assert (templates_dir / "secrets-template.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_ensure_global_dir_copies_from_templates(tmp_path: Path) -> None:
    """Verify ensure_global_dir() copies from global_templates, not defaults."""
    import importlib

    import ot.paths

    # Use a fake home directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    with patch.dict(os.environ, {"HOME": str(fake_home)}):
        importlib.reload(ot.paths)

        result = ot.paths.ensure_global_dir(quiet=True)

        # Should copy template files
        assert (result / "ot-serve.yaml").exists()
        # secrets-template.yaml should be copied as secrets.yaml
        assert (result / "secrets.yaml").exists()
        # Subdirectories (like diagram-templates) should NOT be copied
        assert not (result / "diagram-templates").exists()


@pytest.mark.unit
@pytest.mark.core
def test_ensure_global_dir_force_overwrites(tmp_path: Path) -> None:
    """Verify ensure_global_dir(force=True) overwrites existing files."""
    import importlib

    import ot.paths

    # Use a fake home directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    with patch.dict(os.environ, {"HOME": str(fake_home)}):
        importlib.reload(ot.paths)

        # Create directory with a custom file
        global_dir = ot.paths.get_global_dir()
        global_dir.mkdir(parents=True)
        custom_config = global_dir / "ot-serve.yaml"
        custom_config.write_text("# custom config")

        # Force should overwrite
        ot.paths.ensure_global_dir(quiet=True, force=True)

        # File should now contain template content, not custom content
        content = custom_config.read_text()
        assert "# custom config" not in content
        assert "OneTool Global Configuration" in content or "version:" in content


@pytest.mark.unit
@pytest.mark.core
def test_ensure_global_dir_no_force_preserves(tmp_path: Path) -> None:
    """Verify ensure_global_dir(force=False) preserves existing files."""
    import importlib

    import ot.paths

    # Use a fake home directory
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    with patch.dict(os.environ, {"HOME": str(fake_home)}):
        importlib.reload(ot.paths)

        # Create directory with a custom file
        global_dir = ot.paths.get_global_dir()
        global_dir.mkdir(parents=True)
        custom_config = global_dir / "ot-serve.yaml"
        custom_config.write_text("# custom config")

        # Without force, should not overwrite
        ot.paths.ensure_global_dir(quiet=True, force=False)

        # File should still contain custom content
        content = custom_config.read_text()
        assert "# custom config" in content
