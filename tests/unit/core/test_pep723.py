"""Tests for PEP 723 inline script metadata detection."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from ot.executor.pep723 import (
    analyze_tool_file,
    parse_pep723_metadata,
)


@pytest.mark.unit
@pytest.mark.core
class TestParsePep723Metadata:
    """Tests for parse_pep723_metadata function."""

    def test_parses_valid_pep723_header(self) -> None:
        """Should parse a valid PEP 723 header with dependencies."""
        content = dedent("""
            # /// script
            # requires-python = ">=3.11"
            # dependencies = ["httpx>=0.27.0", "pydantic>=2.0.0"]
            # ///

            import httpx
        """)
        result = parse_pep723_metadata(content)

        assert result is not None
        assert result.requires_python == ">=3.11"
        assert result.dependencies == ["httpx>=0.27.0", "pydantic>=2.0.0"]
        assert result.has_dependencies is True

    def test_returns_none_for_no_header(self) -> None:
        """Should return None when no PEP 723 header is present."""
        content = dedent("""
            import sys

            def main():
                pass
        """)
        result = parse_pep723_metadata(content)

        assert result is None

    def test_parses_header_without_dependencies(self) -> None:
        """Should parse header with only requires-python."""
        content = dedent("""
            # /// script
            # requires-python = ">=3.11"
            # ///

            print("hello")
        """)
        result = parse_pep723_metadata(content)

        assert result is not None
        assert result.requires_python == ">=3.11"
        assert result.dependencies == []
        assert result.has_dependencies is False

    def test_parses_multiline_dependencies(self) -> None:
        """Should parse dependencies split across multiple lines."""
        content = dedent("""
            # /// script
            # requires-python = ">=3.11"
            # dependencies = [
            #   "httpx>=0.27.0",
            #   "trafilatura>=2.0.0",
            # ]
            # ///
        """)
        result = parse_pep723_metadata(content)

        assert result is not None
        assert result.dependencies == ["httpx>=0.27.0", "trafilatura>=2.0.0"]


@pytest.mark.unit
@pytest.mark.core
class TestExtractPack:
    """Tests for pack extraction via analyze_tool_file."""

    def test_extracts_pack_declaration(self, tmp_path: Path) -> None:
        """Should extract pack from module-level assignment."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            pack = "brave"

            def search(query: str) -> str:
                return query
        """)
        )

        result = analyze_tool_file(tool_file)
        assert result.pack == "brave"

    def test_returns_none_when_no_pack(self, tmp_path: Path) -> None:
        """Should return None when no pack is declared."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            def search(query: str) -> str:
                return query
        """)
        )

        result = analyze_tool_file(tool_file)
        assert result.pack is None

    def test_ignores_non_string_pack(self, tmp_path: Path) -> None:
        """Should return None when pack is not a string literal."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            pack = get_pack()

            def search(query: str) -> str:
                return query
        """)
        )

        result = analyze_tool_file(tool_file)
        assert result.pack is None


@pytest.mark.unit
@pytest.mark.core
class TestExtractToolFunctions:
    """Tests for function extraction via analyze_tool_file."""

    def test_extracts_public_functions(self, tmp_path: Path) -> None:
        """Should extract all public function names."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            def search(query: str) -> str:
                return query

            def fetch(url: str) -> str:
                return url

            def _private_helper():
                pass
        """)
        )

        result = analyze_tool_file(tool_file)
        assert set(result.functions) == {"search", "fetch"}

    def test_respects_all_declaration(self, tmp_path: Path) -> None:
        """Should only include functions listed in __all__."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            __all__ = ["search"]

            def search(query: str) -> str:
                return query

            def fetch(url: str) -> str:
                return url
        """)
        )

        result = analyze_tool_file(tool_file)
        assert result.functions == ["search"]

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Should return empty list for files with syntax errors."""
        tool_file = tmp_path / "broken.py"
        tool_file.write_text("def broken( = )")

        result = analyze_tool_file(tool_file)
        assert result.functions == []

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Should return empty list for non-existent files."""
        result = analyze_tool_file(tmp_path / "nonexistent.py")
        assert result.functions == []


@pytest.mark.unit
@pytest.mark.core
class TestWorkerToolDependencies:
    """Tests to ensure worker tools declare all their dependencies.

    Worker tools with PEP 723 headers run in isolated environments where only
    declared dependencies are available. If an import is missing from the
    dependencies list, the worker will crash with "Worker closed unexpectedly".
    """

    # Modules that are always available (stdlib or provided by ot_sdk)
    ALLOWED_MODULES = {
        # Standard library modules commonly used
        "abc", "asyncio", "base64", "collections", "concurrent", "contextlib",
        "copy", "dataclasses", "datetime", "decimal", "enum", "fnmatch",
        "functools", "hashlib", "html", "http", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "mimetypes", "operator", "os",
        "pathlib", "pickle", "platform", "queue", "random", "re", "shutil",
        "socket", "string", "subprocess", "sys", "tempfile", "textwrap",
        "threading", "time", "traceback", "typing", "unittest", "urllib",
        "uuid", "warnings", "weakref", "xml", "zipfile", "zlib",
        # typing_extensions is often bundled
        "typing_extensions",
        # SDK-provided modules (available in worker environment via PYTHONPATH)
        "ot_sdk",
        "ot",  # Main onetool package, available via PYTHONPATH
        # __future__ is special
        "__future__",
    }

    # Map package names to their import names (when different)
    PACKAGE_TO_IMPORT = {
        "pyyaml": "yaml",
        "pillow": "PIL",
        "beautifulsoup4": "bs4",
        "scikit-learn": "sklearn",
    }

    def _extract_imports(self, content: str) -> set[str]:
        """Extract top-level module names from imports."""
        import ast

        imports: set[str] = set()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Get top-level module (e.g., "os.path" -> "os")
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])

        return imports

    def _normalize_package_name(self, dep: str) -> str:
        """Extract package name from dependency spec (e.g., 'pydantic>=2.0' -> 'pydantic')."""
        import re

        # Remove version specifiers
        name = re.split(r"[<>=!~\[]", dep)[0].strip().lower()
        # Map to import name if different
        return self.PACKAGE_TO_IMPORT.get(name, name)

    def test_all_worker_tools_declare_dependencies(self) -> None:
        """All PEP 723 worker tools must declare their third-party imports."""
        from pathlib import Path

        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "ot_tools"
        if not tools_dir.exists():
            pytest.skip("ot_tools directory not found")

        errors: list[str] = []

        for tool_file in sorted(tools_dir.glob("*.py")):
            content = tool_file.read_text()

            # Check if it has a PEP 723 header
            metadata = parse_pep723_metadata(content)
            if metadata is None or not metadata.has_dependencies:
                continue  # Not a worker tool

            # Extract imports and declared dependencies
            imports = self._extract_imports(content)
            declared = {self._normalize_package_name(d) for d in metadata.dependencies}

            # Find missing dependencies
            for imp in imports:
                if imp in self.ALLOWED_MODULES:
                    continue
                # Check if import is covered by any declared dependency
                if imp.lower() not in declared:
                    errors.append(f"{tool_file.name}: imports '{imp}' but not in dependencies")

        if errors:
            error_msg = "Worker tools with missing dependencies:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            pytest.fail(error_msg)
