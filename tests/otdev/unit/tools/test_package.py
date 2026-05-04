"""Unit tests for package tool pack."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestPackagePack:
    """Test package pack structure."""

    def test_pack_name(self):
        from otdev.tools import package

        assert package.pack == "package"

    def test_has_all_exports(self):
        from otdev.tools import package

        # Package should export npm, pypi, models, and other functions
        assert hasattr(package, "__all__")
        expected = {"npm", "pypi", "models"}
        assert expected.issubset(set(package.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import package

        for name in package.__all__:
            func = getattr(package, name)
            assert callable(func), f"{name} should be callable"


@pytest.mark.unit
@pytest.mark.tools
class TestPackageRegressionFixes:
    def test_version_empty_input_returns_empty_list(self):
        from otdev.tools.package import version

        assert version(registry="npm", packages=[]) == []

    def test_parse_dependency_string_accepts_dotted_names(self):
        from otdev.tools.package import _parse_dependency_string

        name, ver = _parse_dependency_string("zope.interface>=6.0")
        assert name == "zope.interface"
        assert ver == ">=6.0"

    def test_audit_resolves_relative_path_from_project_cwd(self, tmp_path: Path):
        from otdev.tools.package import audit

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "requirements.txt").write_text("requests>=2.0\n")

        with (
            patch("otdev.tools.package.resolve_cwd_path", return_value=project_dir),
            patch(
                "otdev.tools.package._fetch_package",
                return_value={"name": "requests", "latest": "2.32.0", "registry": "pypi"},
            ),
        ):
            result = audit(path="relative/path")

        assert "error" not in result
        assert result["manifest"].endswith("requirements.txt")
