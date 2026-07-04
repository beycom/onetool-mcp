"""Unit tests for scripts/release_publish.py's run() helper.

Verifies the argv-list fix (p33-release-cut task group 1): run() must invoke
subprocess.run with a list, never a shell string, and must never use
shell=True. Dry-run (the default, no --force) must never call subprocess.run
at all.
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"


@pytest.fixture
def release_publish():
    """Import scripts.release_publish, ensuring the project root is on sys.path."""
    project_root = str(SCRIPTS_DIR.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    module = import_module("scripts.release_publish")
    # Reset the module-level dry-run flag before each test.
    module.DRY_RUN = True
    return module


@pytest.mark.unit
@pytest.mark.core
class TestRunHelperArgvOnly:
    """run() must pass argv lists to subprocess.run, never shell strings."""

    def test_run_passes_list_not_str(self, release_publish) -> None:
        release_publish.DRY_RUN = False
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            release_publish.run(["uv", "build"])

        assert mock_run.call_count == 1
        cmd_arg = mock_run.call_args.args[0]
        assert isinstance(cmd_arg, list)
        assert not isinstance(cmd_arg, str)
        assert cmd_arg == ["uv", "build"]

    def test_run_never_uses_shell_true(self, release_publish) -> None:
        release_publish.DRY_RUN = False
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            release_publish.run(["git", "add", "-A"])
            release_publish.run(["git", "commit", "-m", "Release 1.0.0"], check=False)

        for call in mock_run.call_args_list:
            assert call.kwargs.get("shell") is not True
            assert "shell" not in call.kwargs or call.kwargs["shell"] is False

    def test_dry_run_default_never_calls_subprocess(self, release_publish) -> None:
        # DRY_RUN defaults to True (module-level default / no --force).
        assert release_publish.DRY_RUN is True
        with patch("subprocess.run") as mock_run:
            result = release_publish.run(["uv", "publish"])

        mock_run.assert_not_called()
        assert result is None

    def test_dry_run_prints_space_joined_display(self, release_publish, capsys) -> None:
        assert release_publish.DRY_RUN is True
        with patch("subprocess.run") as mock_run:
            release_publish.run(["git", "tag", "-a", "v1.0.0", "-m", "Release 1.0.0"])

        mock_run.assert_not_called()
        captured = capsys.readouterr()
        assert "git tag -a v1.0.0 -m Release 1.0.0" in captured.out
