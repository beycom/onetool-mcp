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
