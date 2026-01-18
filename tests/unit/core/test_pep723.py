"""Tests for PEP 723 inline script metadata detection."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from ot.executor.pep723 import (
    extract_namespace,
    extract_tool_functions,
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
class TestExtractNamespace:
    """Tests for extract_namespace function."""

    def test_extracts_namespace_declaration(self, tmp_path: Path) -> None:
        """Should extract namespace from module-level assignment."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            namespace = "brave"

            def search(query: str) -> str:
                return query
        """)
        )

        result = extract_namespace(tool_file)
        assert result == "brave"

    def test_returns_none_when_no_namespace(self, tmp_path: Path) -> None:
        """Should return None when no namespace is declared."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            def search(query: str) -> str:
                return query
        """)
        )

        result = extract_namespace(tool_file)
        assert result is None

    def test_ignores_non_string_namespace(self, tmp_path: Path) -> None:
        """Should return None when namespace is not a string literal."""
        tool_file = tmp_path / "my_tool.py"
        tool_file.write_text(
            dedent("""
            namespace = get_namespace()

            def search(query: str) -> str:
                return query
        """)
        )

        result = extract_namespace(tool_file)
        assert result is None


@pytest.mark.unit
@pytest.mark.core
class TestExtractToolFunctions:
    """Tests for extract_tool_functions function."""

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

        result = extract_tool_functions(tool_file)
        assert set(result) == {"search", "fetch"}

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

        result = extract_tool_functions(tool_file)
        assert result == ["search"]

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Should return empty list for files with syntax errors."""
        tool_file = tmp_path / "broken.py"
        tool_file.write_text("def broken( = )")

        result = extract_tool_functions(tool_file)
        assert result == []

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Should return empty list for non-existent files."""
        result = extract_tool_functions(tmp_path / "nonexistent.py")
        assert result == []
