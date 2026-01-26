"""Tests for ripgrep text search tools.

Tests pure functions directly and main functions with subprocess mocks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# -----------------------------------------------------------------------------
# Pure Function Tests (No Mocking Required)
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestResolvePath:
    """Test _resolve_path function."""

    def test_absolute_path_unchanged(self):
        import ot_sdk.config as config_module

        from ot_tools.ripgrep import _resolve_path

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        result = _resolve_path("/absolute/path")

        assert result == Path("/absolute/path")
        config_module._current_config.clear()

    def test_relative_path_resolved(self):
        import ot_sdk.config as config_module

        from ot_tools.ripgrep import _resolve_path

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        result = _resolve_path("src/main.py")

        assert result == Path("/project/src/main.py")
        config_module._current_config.clear()

    def test_dot_path_resolved(self):
        import ot_sdk.config as config_module

        from ot_tools.ripgrep import _resolve_path

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        result = _resolve_path(".")

        assert result == Path("/project")
        config_module._current_config.clear()


@pytest.mark.unit
@pytest.mark.tools
class TestCheckRgInstalled:
    """Test _check_rg_installed function."""

    @patch("shutil.which")
    def test_returns_none_when_installed(self, mock_which):
        from ot_tools.ripgrep import _check_rg_installed

        mock_which.return_value = "/usr/bin/rg"

        result = _check_rg_installed()

        assert result is None

    @patch("shutil.which")
    def test_returns_error_when_not_installed(self, mock_which):
        from ot_tools.ripgrep import _check_rg_installed

        mock_which.return_value = None

        result = _check_rg_installed()

        assert result is not None
        assert "ripgrep" in result
        assert "not installed" in result


# -----------------------------------------------------------------------------
# Subprocess Mock Tests
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_ripgrep_config():
    """Mock get_tool_config to return a Config with default timeout."""
    from ot_tools.ripgrep import Config

    with patch("ot_tools.ripgrep.get_tool_config") as mock:
        mock.return_value = Config(timeout=30)
        yield mock


@pytest.mark.unit
@pytest.mark.tools
class TestRunRg:
    """Test _run_rg subprocess wrapper."""

    def test_successful_run(self, mock_ripgrep_config):
        from ot_tools.ripgrep import _run_rg

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="file.py:10:match", stderr=""
            )

            success, output = _run_rg(["pattern", "."])

        assert success is True
        assert "file.py:10:match" in output

    def test_no_matches_is_success(self, mock_ripgrep_config):
        from ot_tools.ripgrep import _run_rg

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

            success, _output = _run_rg(["pattern", "."])

        # returncode 1 = no matches, which is not an error
        assert success is True

    def test_actual_error(self, mock_ripgrep_config):
        from ot_tools.ripgrep import _run_rg

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2, stdout="", stderr="Invalid regex"
            )

            success, output = _run_rg(["[invalid", "."])

        assert success is False
        assert "Invalid regex" in output

    def test_timeout(self, mock_ripgrep_config):
        from ot_tools.ripgrep import _run_rg

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="rg", timeout=30)

            success, output = _run_rg(["pattern", "."])

        assert success is False
        assert "timed out" in output

    def test_rg_not_found(self, mock_ripgrep_config):
        from ot_tools.ripgrep import _run_rg

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            success, output = _run_rg(["pattern", "."])

        assert success is False
        assert "not installed" in output


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked subprocess."""

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_basic_search(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "file.py:10:TODO: fix this")

        result = search(pattern="TODO", path=".")

        assert "file.py" in result
        assert "TODO" in result

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_no_matches(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        result = search(pattern="nonexistent", path=".")

        assert "No matches found" in result

    @patch("ot_tools.ripgrep._check_rg_installed")
    def test_rg_not_installed(self, mock_check):
        from ot_tools.ripgrep import search

        mock_check.return_value = "Error: ripgrep (rg) is not installed"

        result = search(pattern="test", path=".")

        assert "not installed" in result

    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_invalid_path(self, mock_resolve, mock_check):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_resolve.return_value = mock_path

        result = search(pattern="test", path="/nonexistent")

        assert "does not exist" in result


@pytest.mark.unit
@pytest.mark.tools
class TestCount:
    """Test count function with mocked subprocess."""

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_count_matches(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import count

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "file1.py:3\nfile2.py:5")

        result = count(pattern="TODO", path=".")

        assert "file1.py" in result
        assert "file2.py" in result

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_no_matches(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import count

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        result = count(pattern="nonexistent", path=".")

        assert "No matches found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFiles:
    """Test files function with mocked subprocess."""

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_list_files(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import files

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "src/main.py\nsrc/utils.py")

        result = files(path=".", file_type="py")

        assert "main.py" in result
        assert "utils.py" in result

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_no_files(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import files

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        result = files(path=".", file_type="xyz")

        assert "No files found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestTypes:
    """Test types function with mocked subprocess."""

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    def test_list_types(self, mock_check, mock_run):
        from ot_tools.ripgrep import types

        mock_check.return_value = None
        mock_run.return_value = (
            True,
            "py: *.py\njs: *.js, *.jsx\nts: *.ts, *.tsx",
        )

        result = types()

        assert "py" in result
        assert "js" in result

    @patch("ot_tools.ripgrep._check_rg_installed")
    def test_rg_not_installed(self, mock_check):
        from ot_tools.ripgrep import types

        mock_check.return_value = "Error: ripgrep (rg) is not installed"

        result = types()

        assert "not installed" in result


# -----------------------------------------------------------------------------
# Argument Building Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearchArguments:
    """Test that search builds correct arguments."""

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_case_insensitive_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", case_sensitive=False)

        args = mock_run.call_args[0][0]
        assert "--ignore-case" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_fixed_strings_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="[test]", path=".", fixed_strings=True)

        args = mock_run.call_args[0][0]
        assert "--fixed-strings" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_file_type_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", file_type="py")

        args = mock_run.call_args[0][0]
        assert "--type" in args
        assert "py" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_glob_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", glob="*.ts")

        args = mock_run.call_args[0][0]
        assert "--glob" in args
        assert "*.ts" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_context_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", context=3)

        args = mock_run.call_args[0][0]
        assert "--context" in args
        assert "3" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_word_match_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", word_match=True)

        args = mock_run.call_args[0][0]
        assert "--word-regexp" in args

    @patch("ot_tools.ripgrep._run_rg")
    @patch("ot_tools.ripgrep._check_rg_installed")
    @patch("ot_tools.ripgrep._resolve_path")
    def test_hidden_flag(self, mock_resolve, mock_check, mock_run):
        from ot_tools.ripgrep import search

        mock_check.return_value = None
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path
        mock_run.return_value = (True, "")

        search(pattern="test", path=".", include_hidden=True)

        args = mock_run.call_args[0][0]
        assert "--hidden" in args
