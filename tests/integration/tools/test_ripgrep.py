"""Live integration tests for ripgrep tool.

Requires rg binary to be installed.
"""

from __future__ import annotations

import shutil

import pytest


@pytest.mark.integration
@pytest.mark.tools
class TestRipgrepLive:
    """Live integration tests for ripgrep tool."""

    @pytest.fixture(autouse=True)
    def skip_if_rg_not_installed(self):
        """Skip tests if ripgrep is not installed."""
        if shutil.which("rg") is None:
            pytest.skip("ripgrep (rg) not installed")

    def test_search_live(self, tmp_path):
        """Verify ripgrep search works with real binary."""
        from ot_tools.ripgrep import search

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello_world():\n    print('Hello')\n")

        result = search(pattern="hello", path=str(tmp_path))

        assert "hello" in result.lower()

    def test_files_live(self, tmp_path):
        """Verify ripgrep files listing works."""
        from ot_tools.ripgrep import files

        # Create test files
        (tmp_path / "test.py").write_text("# python")
        (tmp_path / "test.js").write_text("// javascript")

        result = files(path=str(tmp_path), file_type="py")

        assert "test.py" in result

    def test_types_live(self):
        """Verify ripgrep types listing works."""
        from ot_tools.ripgrep import types

        result = types()

        assert "py" in result  # Python should be in type list
