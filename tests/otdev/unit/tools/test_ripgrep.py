"""Unit tests for ripgrep tool pack."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestRipgrepPack:
    """Test ripgrep pack structure."""

    def test_pack_name(self):
        from otdev.tools import ripgrep

        assert ripgrep.pack == "ripgrep"

    def test_has_all_exports(self):
        from otdev.tools import ripgrep

        # Ripgrep should export search, count, files, types
        assert hasattr(ripgrep, "__all__")
        expected = {"search", "count", "files", "types"}
        assert set(ripgrep.__all__) == expected

    def test_functions_are_callable(self):
        from otdev.tools import ripgrep

        for name in ripgrep.__all__:
            func = getattr(ripgrep, name)
            assert callable(func), f"{name} should be callable"


@pytest.mark.unit
@pytest.mark.tools
class TestRipgrepSearchFlags:
    def test_search_supports_new_cli_flags(self) -> None:
        from otdev.tools.ripgrep import search

        with (
            patch("otdev.tools.ripgrep._check_rg_installed", return_value=None),
            patch("otdev.tools.ripgrep._resolve_path", return_value=Path(".")),
            patch("otdev.tools.ripgrep._run_rg", return_value=(True, "a.py\nb.py")) as mock_run,
            patch("otdev.tools.ripgrep._to_relative_output", side_effect=lambda output, _: output),
        ):
            result = search(
                pattern="TODO",
                follow_symlinks=True,
                smart_case=True,
                filenames_only=True,
            )

        assert "a.py" in result
        args = mock_run.call_args.args[0]
        assert "--follow" in args
        assert "--smart-case" in args
        assert "--files-with-matches" in args
