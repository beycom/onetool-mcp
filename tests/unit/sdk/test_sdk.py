"""Tests for ot_sdk package utilities."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestSdkConfig:
    """Tests for ot_sdk.config module."""

    @pytest.fixture(autouse=True)
    def save_and_restore_config(self):
        """Save config state before test and restore after."""
        import ot_sdk.config as config_module

        # Save original state
        original_secrets = dict(config_module._current_secrets)
        original_config = dict(config_module._current_config)

        yield

        # Restore original state
        config_module._current_secrets.clear()
        config_module._current_secrets.update(original_secrets)
        config_module._current_config.clear()
        config_module._current_config.update(original_config)

    def test_get_secret_returns_value(self) -> None:
        """Should return secret value from current secrets."""
        import ot_sdk.config as config_module

        # Use .clear() and .update() to modify in-place (preserves references)
        config_module._current_secrets.clear()
        config_module._current_secrets.update({"MY_KEY": "my-value"})

        from ot_sdk import get_secret

        result = get_secret("MY_KEY")
        assert result == "my-value"

    def test_get_secret_returns_none_for_missing(self) -> None:
        """Should return None for missing secret."""
        import ot_sdk.config as config_module

        config_module._current_secrets.clear()

        from ot_sdk import get_secret

        result = get_secret("NONEXISTENT")
        assert result is None

    def test_get_config_returns_nested_value(self) -> None:
        """Should return value from dotted path."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update(
            {"tools": {"brave": {"timeout": 30.0, "count": 10}}}
        )

        from ot_sdk import get_config

        result = get_config("tools.brave.timeout")
        assert result == 30.0

    def test_get_config_returns_none_for_missing_path(self) -> None:
        """Should return None for non-existent path."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"tools": {}})

        from ot_sdk import get_config

        result = get_config("tools.nonexistent.path")
        assert result is None

    def test_get_config_returns_none_for_non_dict_intermediate(self) -> None:
        """Should return None when path traverses non-dict value."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"tools": "not-a-dict"})

        from ot_sdk import get_config

        result = get_config("tools.brave.timeout")
        assert result is None


@pytest.mark.unit
@pytest.mark.core
class TestSdkUtils:
    """Tests for ot_sdk.utils module."""

    def test_truncate_short_text(self) -> None:
        """Should not truncate text shorter than max length."""
        from ot_sdk import truncate

        result = truncate("short text", 100)
        assert result == "short text"

    def test_truncate_long_text(self) -> None:
        """Should truncate text longer than max length."""
        from ot_sdk import truncate

        long_text = "a" * 100
        result = truncate(long_text, 50)

        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_with_custom_indicator(self) -> None:
        """Should use custom truncation indicator."""
        from ot_sdk import truncate

        result = truncate("a" * 100, 50, indicator="[more]")
        assert result.endswith("[more]")

    def test_format_error_simple(self) -> None:
        """Should format simple error message."""
        from ot_sdk import format_error

        result = format_error("Something went wrong")
        assert result == "Error: Something went wrong"

    def test_format_error_with_details(self) -> None:
        """Should format error with details dict."""
        from ot_sdk import format_error

        result = format_error("Failed", details={"code": 500, "reason": "timeout"})
        assert "Error: Failed" in result
        assert "code=500" in result
        assert "reason=timeout" in result

    def test_run_command_success(self) -> None:
        """Should run command and capture output."""
        from ot_sdk import run_command

        returncode, stdout, _stderr = run_command(["echo", "hello"])

        assert returncode == 0
        assert stdout.strip() == "hello"

    def test_run_command_failure(self) -> None:
        """Should capture non-zero return code."""
        from ot_sdk import run_command

        returncode, _stdout, _stderr = run_command(["false"])

        assert returncode != 0


@pytest.mark.unit
@pytest.mark.core
class TestSdkCache:
    """Tests for ot_sdk.cache decorator."""

    def test_cache_memoizes_result(self) -> None:
        """Should cache function results."""
        from ot_sdk import cache

        call_count = 0

        @cache(ttl=60)
        def expensive_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_func(5)
        assert result1 == 10
        assert call_count == 1

        # Second call with same arg - should use cache
        result2 = expensive_func(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented

        # Different arg - should call function
        result3 = expensive_func(10)
        assert result3 == 20
        assert call_count == 2

    def test_cache_with_kwargs(self) -> None:
        """Should cache results based on kwargs."""
        from ot_sdk import cache

        call_count = 0

        @cache(ttl=60)
        def func_with_kwargs(*, a: int, b: int) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        result1 = func_with_kwargs(a=1, b=2)
        result2 = func_with_kwargs(a=1, b=2)
        result3 = func_with_kwargs(a=2, b=1)

        assert result1 == result2 == 3
        assert result3 == 3
        assert call_count == 2  # Called twice for different kwargs

    def test_cache_manual_get_set_clear(self) -> None:
        """Should support manual cache operations."""
        from ot_sdk.cache import cache

        # Set a value
        cache.set("my_key", "my_value", ttl=60)

        # Get the value
        result = cache.get("my_key")
        assert result == "my_value"

        # Clear specific key
        cache.clear("my_key")
        assert cache.get("my_key") is None

        # Set again and clear all
        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


@pytest.mark.unit
@pytest.mark.core
class TestSdkPaths:
    """Tests for ot_sdk.paths module."""

    @pytest.fixture(autouse=True)
    def save_and_restore_config(self):
        """Save config state before test and restore after."""
        import ot_sdk.config as config_module

        # Save original state
        original_config = dict(config_module._current_config)

        yield

        # Restore original state
        config_module._current_config.clear()
        config_module._current_config.update(original_config)

    def test_get_project_path_relative(self, tmp_path: Path) -> None:
        """Should resolve relative path against project path."""
        import ot_sdk.config as config_module

        # Use .clear() and .update() to modify in-place (paths.py has a reference)
        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import get_project_path

        result = get_project_path("diagrams/flow.svg")
        assert result == tmp_path / "diagrams" / "flow.svg"

    def test_get_project_path_absolute(self, tmp_path: Path) -> None:
        """Should return absolute path unchanged."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import get_project_path

        result = get_project_path("/tmp/output.svg")
        assert result == Path("/tmp/output.svg")

    def test_get_project_path_tilde(self) -> None:
        """Should expand tilde to home directory."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        from ot_sdk import get_project_path

        result = get_project_path("~/output.svg")
        assert result == Path.home() / "output.svg"

    def test_get_project_path_fallback_to_cwd(self) -> None:
        """Should fall back to cwd when _project_path not set."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()

        from ot_sdk import get_project_path

        result = get_project_path("output.svg")
        assert result == (Path.cwd() / "output.svg").resolve()

    def test_get_config_path_relative(self, tmp_path: Path) -> None:
        """Should resolve relative path against config directory."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({"_config_dir": str(config_dir)})

        from ot_sdk import get_config_path

        result = get_config_path("templates/flow.mmd")
        assert result == config_dir / "templates" / "flow.mmd"

    def test_get_config_path_absolute(self, tmp_path: Path) -> None:
        """Should return absolute path unchanged."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_config_dir": str(tmp_path)})

        from ot_sdk import get_config_path

        result = get_config_path("/etc/templates/flow.mmd")
        assert result == Path("/etc/templates/flow.mmd")

    def test_expand_path_tilde(self) -> None:
        """Should expand tilde to home directory."""
        from ot_sdk import expand_path

        result = expand_path("~/config.yaml")
        assert result == Path.home() / "config.yaml"

    def test_expand_path_no_var_expansion(self) -> None:
        """Should NOT expand ${VAR} patterns."""
        from ot_sdk import expand_path

        result = expand_path("${HOME}/config.yaml")
        # Should contain literal ${HOME}
        assert "${HOME}" in str(result)

    def test_expand_path_relative(self) -> None:
        """Should return relative path as-is (not resolved)."""
        from ot_sdk import expand_path

        result = expand_path("relative/path.txt")
        assert result == Path("relative/path.txt")

    # =========================================================================
    # New SDK Path API Tests
    # =========================================================================

    def test_get_ot_dir_uses_config_dir(self, tmp_path: Path) -> None:
        """Should use _config_dir from context when available."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({"_config_dir": str(config_dir)})

        from ot_sdk import get_ot_dir

        result = get_ot_dir()
        assert result == config_dir

    def test_get_ot_dir_project_local(self, tmp_path: Path) -> None:
        """Should use project-local .onetool if exists."""
        import ot_sdk.config as config_module

        # Create project-local .onetool
        project_ot = tmp_path / ".onetool"
        project_ot.mkdir()

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import get_ot_dir

        result = get_ot_dir()
        assert result == project_ot

    def test_get_ot_dir_fallback_to_global(self, tmp_path: Path) -> None:
        """Should fall back to global ~/.onetool/ when no project .onetool."""
        import ot_sdk.config as config_module

        # No .onetool directory in project
        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import get_ot_dir

        result = get_ot_dir()
        assert result == Path.home() / ".onetool"

    def test_resolve_path_default_cwd(self, tmp_path: Path) -> None:
        """Should resolve relative path against CWD by default."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_path

        result = resolve_path("data/file.txt")
        assert result == (tmp_path / "data" / "file.txt").resolve()

    def test_resolve_path_ot_dir_base(self, tmp_path: Path) -> None:
        """Should resolve relative path against OT_DIR with base param."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({"_config_dir": str(config_dir)})

        from ot_sdk import resolve_path

        result = resolve_path("templates/flow.mmd", base="OT_DIR")
        assert result == (config_dir / "templates" / "flow.mmd").resolve()

    def test_resolve_path_global_base(self) -> None:
        """Should resolve relative path against GLOBAL base."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()

        from ot_sdk import resolve_path

        result = resolve_path("logs/app.log", base="GLOBAL")
        assert result == (Path.home() / ".onetool" / "logs" / "app.log").resolve()

    def test_resolve_path_cwd_prefix(self, tmp_path: Path) -> None:
        """Should handle CWD prefix override."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({
            "_project_path": str(tmp_path),
            "_config_dir": str(config_dir),
        })

        from ot_sdk import resolve_path

        # CWD prefix should override OT_DIR base
        result = resolve_path("CWD/output.txt", base="OT_DIR")
        assert result == (tmp_path / "output.txt").resolve()

    def test_resolve_path_global_prefix(self, tmp_path: Path) -> None:
        """Should handle GLOBAL prefix override."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_path

        # GLOBAL prefix should override CWD base
        result = resolve_path("GLOBAL/logs/app.log", base="CWD")
        assert result == (Path.home() / ".onetool" / "logs" / "app.log").resolve()

    def test_resolve_path_ot_dir_prefix(self, tmp_path: Path) -> None:
        """Should handle OT_DIR prefix override."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({
            "_project_path": str(tmp_path),
            "_config_dir": str(config_dir),
        })

        from ot_sdk import resolve_path

        # OT_DIR prefix should override CWD base
        result = resolve_path("OT_DIR/templates/flow.mmd", base="CWD")
        assert result == (config_dir / "templates" / "flow.mmd").resolve()

    def test_resolve_path_tilde(self, tmp_path: Path) -> None:
        """Should handle tilde prefix for home directory."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_path

        result = resolve_path("~/documents/file.txt")
        assert result == (Path.home() / "documents" / "file.txt").resolve()

    def test_resolve_path_absolute(self, tmp_path: Path) -> None:
        """Should return absolute path unchanged."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_path

        result = resolve_path("/tmp/output.svg")
        assert result == Path("/tmp/output.svg").resolve()

    def test_resolve_cwd_path(self, tmp_path: Path) -> None:
        """Should resolve against CWD (convenience wrapper)."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_cwd_path

        result = resolve_cwd_path("data/file.txt")
        assert result == (tmp_path / "data" / "file.txt").resolve()

    def test_resolve_ot_path(self, tmp_path: Path) -> None:
        """Should resolve against OT_DIR (convenience wrapper)."""
        import ot_sdk.config as config_module

        config_dir = tmp_path / ".onetool"
        config_module._current_config.clear()
        config_module._current_config.update({"_config_dir": str(config_dir)})

        from ot_sdk import resolve_ot_path

        result = resolve_ot_path("templates/flow.mmd")
        assert result == (config_dir / "templates" / "flow.mmd").resolve()

    def test_resolve_path_prefix_only(self, tmp_path: Path) -> None:
        """Should handle prefix-only paths (e.g., 'CWD', 'GLOBAL')."""
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": str(tmp_path)})

        from ot_sdk import resolve_path

        # Just the prefix should return the base directory
        assert resolve_path("CWD") == tmp_path
        assert resolve_path("GLOBAL") == Path.home() / ".onetool"


@pytest.mark.unit
@pytest.mark.core
class TestSdkExports:
    """Tests for ot_sdk package exports."""

    def test_all_exports_are_importable(self) -> None:
        """Should export all documented functions."""
        from ot_sdk import (
            expand_path,
            format_error,
            get_config,
            get_config_path,
            get_ot_dir,
            get_project_path,
            get_secret,
            http,
            resolve_cwd_path,
            resolve_ot_path,
            resolve_path,
            run_command,
            truncate,
            worker_main,
        )

        # Just verify they're callable/usable
        assert callable(worker_main)
        assert callable(get_secret)
        assert callable(get_config)
        assert callable(get_project_path)
        assert callable(get_config_path)
        assert callable(expand_path)
        assert callable(truncate)
        assert callable(format_error)
        assert callable(run_command)
        assert callable(get_ot_dir)
        assert callable(resolve_path)
        assert callable(resolve_cwd_path)
        assert callable(resolve_ot_path)
        assert hasattr(http, "get")
        assert hasattr(http, "post")

    def test_all_list_matches_exports(self) -> None:
        """Should have all exports listed in __all__."""
        import ot_sdk

        expected = {
            "cache",
            "expand_path",
            "format_error",
            "get_config",
            "get_config_path",
            "get_ot_dir",
            "get_project_path",
            "get_secret",
            "http",
            "log",
            "resolve_cwd_path",
            "resolve_ot_path",
            "resolve_path",
            "run_command",
            "truncate",
            "worker_main",
        }
        assert set(ot_sdk.__all__) == expected
