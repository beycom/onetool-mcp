"""Unit tests for Scaffold tool.

Tests scaffold.create(), scaffold.validate(), scaffold.extensions(), scaffold.templates().
Uses tmp_path fixture for isolated test files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def mock_project_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Mock project directory to tmp_path."""
    project_dir = tmp_path / ".onetool"
    project_dir.mkdir()

    with patch("ot_tools.scaffold.get_project_dir", return_value=project_dir):
        yield project_dir


@pytest.fixture
def mock_global_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Mock global directory to tmp_path."""
    global_dir = tmp_path / "global_onetool"
    global_dir.mkdir()

    with patch("ot_tools.scaffold.get_global_dir", return_value=global_dir):
        yield global_dir


# =============================================================================
# Module Structure Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_pack_is_scaffold() -> None:
    """Verify pack is correctly set."""
    from ot_tools.scaffold import pack

    assert pack == "scaffold"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from ot_tools.scaffold import __all__

    expected = {"create", "extensions", "templates", "validate"}
    assert set(__all__) == expected


# =============================================================================
# templates() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_templates_lists_available() -> None:
    """Verify templates() returns available templates."""
    from ot_tools.scaffold import templates

    result = templates()

    assert "Available extension templates:" in result
    assert "extension" in result
    assert "scaffold.create()" in result


@pytest.mark.unit
@pytest.mark.tools
def test_templates_missing_dir(tmp_path: Path) -> None:
    """Verify templates() handles missing directory."""
    from ot_tools.scaffold import templates

    with patch("ot_tools.scaffold._get_templates_dir", return_value=tmp_path / "nonexistent"):
        result = templates()

    assert "Error" in result
    assert "not found" in result


# =============================================================================
# create() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_create_extension_project_scope(mock_project_dir: Path) -> None:
    """Verify create() creates extension in project scope."""
    from ot_tools.scaffold import create

    result = create(name="my_tool", function="search")

    assert "Created extension:" in result
    assert "my_tool" in result
    assert "Next steps:" in result

    # Verify file was created
    ext_file = mock_project_dir / "tools" / "my_tool" / "my_tool.py"
    assert ext_file.exists()

    content = ext_file.read_text()
    assert 'pack = "my_tool"' in content
    assert 'def search(' in content
    assert "worker_main()" in content


@pytest.mark.unit
@pytest.mark.tools
def test_create_extension_global_scope(mock_global_dir: Path) -> None:
    """Verify create() creates extension in global scope."""
    from ot_tools.scaffold import create

    result = create(name="global_tool", scope="global")

    assert "Created extension:" in result

    # Verify file was created in global dir
    ext_file = mock_global_dir / "tools" / "global_tool" / "global_tool.py"
    assert ext_file.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_create_custom_pack_name(mock_project_dir: Path) -> None:
    """Verify create() uses custom pack_name."""
    from ot_tools.scaffold import create

    result = create(name="my_tool", pack_name="custom_pack")

    assert "Created extension:" in result

    ext_file = mock_project_dir / "tools" / "my_tool" / "my_tool.py"
    content = ext_file.read_text()
    assert 'pack = "custom_pack"' in content


@pytest.mark.unit
@pytest.mark.tools
def test_create_invalid_name() -> None:
    """Verify create() rejects invalid names."""
    from ot_tools.scaffold import create

    # Uppercase not allowed
    result = create(name="MyTool")
    assert "Error" in result
    assert "lowercase" in result

    # Starting with number not allowed
    result = create(name="1tool")
    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_create_already_exists(mock_project_dir: Path) -> None:
    """Verify create() returns error if extension exists."""
    from ot_tools.scaffold import create

    # Create first time
    create(name="existing_tool")

    # Try to create again
    result = create(name="existing_tool")

    assert "Error" in result
    assert "already exists" in result


@pytest.mark.unit
@pytest.mark.tools
def test_create_invalid_template(mock_project_dir: Path) -> None:
    """Verify create() returns error for invalid template."""
    from ot_tools.scaffold import create

    result = create(name="my_tool", template="nonexistent_template")

    assert "Error" in result
    assert "not found" in result


# =============================================================================
# validate() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_validate_valid_extension(tmp_path: Path) -> None:
    """Verify validate() passes for valid extension."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "valid_tool.py"
    ext_file.write_text('''"""My tool description."""

from __future__ import annotations

pack = "mytool"

__all__ = ["run"]

from ot_sdk import log, worker_main


def run(*, input: str) -> str:
    """Run the tool.

    Args:
        input: Input string

    Returns:
        Result string

    Example:
        mytool.run(input="test")
    """
    with log("mytool.run") as s:
        return f"Result: {input}"


if __name__ == "__main__":
    worker_main()
''')

    result = validate(path=str(ext_file))

    assert "Validation PASSED" in result
    assert "[x] pack" in result
    assert "[x] __all__" in result
    assert "[x] Python syntax valid" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_missing_pack(tmp_path: Path) -> None:
    """Verify validate() fails for missing pack."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "no_pack.py"
    ext_file.write_text('''"""My tool."""

__all__ = ["run"]

def run(*, input: str) -> str:
    return input
''')

    result = validate(path=str(ext_file))

    assert "Validation FAILED" in result
    assert "pack" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_validate_missing_all(tmp_path: Path) -> None:
    """Verify validate() fails for missing __all__."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "no_all.py"
    ext_file.write_text('''"""My tool."""

pack = "mytool"

def run(*, input: str) -> str:
    return input
''')

    result = validate(path=str(ext_file))

    assert "Validation FAILED" in result
    assert "__all__" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_syntax_error(tmp_path: Path) -> None:
    """Verify validate() catches syntax errors."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "syntax_error.py"
    ext_file.write_text('''"""My tool."""

pack = "mytool"
__all__ = ["run"]

def run(*, input: str) -> str
    return input  # Missing colon above
''')

    result = validate(path=str(ext_file))

    assert "Syntax error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_missing_worker_main_with_pep723(tmp_path: Path) -> None:
    """Verify validate() fails when PEP 723 deps present but no worker_main."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "no_worker.py"
    ext_file.write_text('''# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""My tool."""

pack = "mytool"
__all__ = ["run"]

def run(*, input: str) -> str:
    return input
''')

    result = validate(path=str(ext_file))

    assert "Validation FAILED" in result
    assert "worker_main" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_file_not_found() -> None:
    """Verify validate() handles missing file."""
    from ot_tools.scaffold import validate

    result = validate(path="/nonexistent/path/tool.py")

    assert "Error" in result
    assert "not found" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_not_python_file(tmp_path: Path) -> None:
    """Verify validate() rejects non-Python files."""
    from ot_tools.scaffold import validate

    txt_file = tmp_path / "file.txt"
    txt_file.write_text("not python")

    result = validate(path=str(txt_file))

    assert "Error" in result
    assert "Not a Python file" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_best_practices_warnings(tmp_path: Path) -> None:
    """Verify validate() shows warnings for best practice violations."""
    from ot_tools.scaffold import validate

    ext_file = tmp_path / "missing_practices.py"
    # Missing docstring, future annotations, logging
    ext_file.write_text('''pack = "mytool"
__all__ = ["run"]

def run(input: str) -> str:  # Missing keyword-only args
    return input
''')

    result = validate(path=str(ext_file))

    # Should pass but with warnings
    assert "Validation PASSED" in result
    assert "Warnings:" in result


# =============================================================================
# extensions() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_extensions_no_config() -> None:
    """Verify extensions() handles no config."""
    from ot_tools.scaffold import extensions

    with patch("ot.config.loader.get_config", return_value=None):
        result = extensions()

    assert "No configuration" in result


@pytest.mark.unit
@pytest.mark.tools
def test_extensions_no_extensions_loaded() -> None:
    """Verify extensions() handles empty tools_dir."""
    from unittest.mock import MagicMock

    from ot_tools.scaffold import extensions

    mock_config = MagicMock()
    mock_config.get_tool_files.return_value = []

    with patch("ot.config.loader.get_config", return_value=mock_config):
        result = extensions()

    assert "No extensions loaded" in result
    assert "scaffold.create()" in result


@pytest.mark.unit
@pytest.mark.tools
def test_extensions_lists_loaded(tmp_path: Path) -> None:
    """Verify extensions() lists loaded extension files."""
    from unittest.mock import MagicMock

    from ot_tools.scaffold import extensions

    mock_config = MagicMock()
    mock_config.get_tool_files.return_value = [
        tmp_path / "tool1.py",
        tmp_path / "tool2.py",
    ]

    with patch("ot.config.loader.get_config", return_value=mock_config):
        result = extensions()

    assert "Loaded extensions:" in result
    assert "tool1.py" in result
    assert "tool2.py" in result
    assert "Total: 2 files" in result


# =============================================================================
# Helper Function Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_has_pep723_deps_true() -> None:
    """Verify _has_pep723_deps detects PEP 723 dependencies."""
    from ot_tools.scaffold import _has_pep723_deps

    content = '''# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""Tool."""
'''
    assert _has_pep723_deps(content) is True


@pytest.mark.unit
@pytest.mark.tools
def test_has_pep723_deps_false_no_deps() -> None:
    """Verify _has_pep723_deps returns False without dependencies."""
    from ot_tools.scaffold import _has_pep723_deps

    content = '''# /// script
# requires-python = ">=3.11"
# ///
"""Tool."""
'''
    assert _has_pep723_deps(content) is False


@pytest.mark.unit
@pytest.mark.tools
def test_has_pep723_deps_false_no_script() -> None:
    """Verify _has_pep723_deps returns False without script block."""
    from ot_tools.scaffold import _has_pep723_deps

    content = '''"""Tool without PEP 723."""

pack = "mytool"
'''
    assert _has_pep723_deps(content) is False
