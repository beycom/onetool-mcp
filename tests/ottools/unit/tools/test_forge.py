"""Unit tests for ot_forge tool.

Tests ot_forge.create_ext(), ot_forge.validate_ext().
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
def mock_ot_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Mock ot dir (config_path.parent) to tmp_path."""
    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    with patch("ottools.ot_forge.get_config_dir", return_value=ot_dir):
        yield ot_dir


# =============================================================================
# Module Structure Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_pack_is_forge() -> None:
    """Verify pack is correctly set."""
    from ottools.ot_forge import pack

    assert pack == "ot_forge"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    """Verify __all__ contains the expected public functions."""
    from ottools.ot_forge import __all__

    expected = {"create_ext", "install_skills", "validate_ext"}
    assert set(__all__) == expected


# =============================================================================
# create_ext() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_project_scope(mock_ot_dir: Path) -> None:
    """Verify create_ext() creates extension in project scope."""
    from ottools.ot_forge import create_ext

    result = create_ext(name="my_tool", function="search")

    assert "Created extension:" in result
    assert "my_tool" in result
    assert "Next steps:" in result

    ext_file = mock_ot_dir / "tools" / "my_tool" / "my_tool.py"
    assert ext_file.exists()

    content = ext_file.read_text()
    assert 'pack = "my_tool"' in content
    assert 'def search(' in content
    assert "LogSpan" in content


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_custom_pack_name(mock_ot_dir: Path) -> None:
    """Verify create_ext() uses custom pack_name."""
    from ottools.ot_forge import create_ext

    result = create_ext(name="my_tool", pack_name="custom_pack")

    assert "Created extension:" in result

    ext_file = mock_ot_dir / "tools" / "my_tool" / "my_tool.py"
    content = ext_file.read_text()
    assert 'pack = "custom_pack"' in content


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_invalid_name() -> None:
    """Verify create_ext() rejects invalid names."""
    from ottools.ot_forge import create_ext

    result = create_ext(name="MyTool")
    assert "Error" in result
    assert "lowercase" in result

    result = create_ext(name="1tool")
    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_already_exists(mock_ot_dir: Path) -> None:
    """Verify create_ext() returns error if extension exists."""
    from ottools.ot_forge import create_ext

    create_ext(name="existing_tool")
    result = create_ext(name="existing_tool")

    assert "Error" in result
    assert "already exists" in result


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_next_steps_reference_forge(mock_ot_dir: Path) -> None:
    """Verify create_ext() next steps reference ot_forge methods."""
    from ottools.ot_forge import create_ext

    result = create_ext(name="my_tool")

    assert "ot_forge.validate_ext" in result


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_uses_flat_layout_for_tools_star_py(mock_ot_dir: Path) -> None:
    """tools/*.py patterns should scaffold flat files for immediate discovery."""
    from ottools.ot_forge import create_ext

    cfg = type("Cfg", (), {"tools_dir": ["tools/*.py"]})()
    with patch("ot.config.loader.get_config", return_value=cfg):
        result = create_ext(name="flat_tool")

    assert "Created extension:" in result
    assert (mock_ot_dir / "tools" / "flat_tool.py").exists()


@pytest.mark.unit
@pytest.mark.tools
def test_create_ext_uses_nested_layout_for_tools_star_star_py(mock_ot_dir: Path) -> None:
    """tools/*/*.py patterns should scaffold nested files."""
    from ottools.ot_forge import create_ext

    cfg = type("Cfg", (), {"tools_dir": ["tools/*/*.py"]})()
    with patch("ot.config.loader.get_config", return_value=cfg):
        result = create_ext(name="nested_tool")

    assert "Created extension:" in result
    assert (mock_ot_dir / "tools" / "nested_tool" / "nested_tool.py").exists()


# =============================================================================
# validate_ext() Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_extension_tool(tmp_path: Path) -> None:
    """Verify validate_ext() passes for a well-formed extension tool."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "valid_tool.py"
    ext_file.write_text('''"""My tool description."""

from __future__ import annotations

pack = "mytool"

__all__ = ["run"]

from ot.logging import LogSpan


def run(*, input: str) -> str:
    """Run the tool.

    Args:
        input: Input string

    Returns:
        Result string

    Example:
        mytool.run(input="test")
    """
    with LogSpan(span="mytool.run") as s:
        return f"Result: {input}"
''')

    result = validate_ext(path=str(ext_file))

    assert "Validation PASSED" in result
    assert "[x] pack" in result
    assert "[x] __all__" in result
    assert "[x] Python syntax valid" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_missing_pack(tmp_path: Path) -> None:
    """Verify validate_ext() fails for missing pack."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "no_pack.py"
    ext_file.write_text('''"""My tool."""

__all__ = ["run"]

def run(*, input: str) -> str:
    return input
''')

    result = validate_ext(path=str(ext_file))

    assert "Validation FAILED" in result
    assert "pack" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_missing_all(tmp_path: Path) -> None:
    """Verify validate_ext() fails for missing __all__."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "no_all.py"
    ext_file.write_text('''"""My tool."""

pack = "mytool"

def run(*, input: str) -> str:
    return input
''')

    result = validate_ext(path=str(ext_file))

    assert "Validation FAILED" in result
    assert "__all__" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_syntax_error(tmp_path: Path) -> None:
    """Verify validate_ext() catches syntax errors."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "syntax_error.py"
    ext_file.write_text('''"""My tool."""

pack = "mytool"
__all__ = ["run"]

def run(*, input: str) -> str
    return input  # Missing colon above
''')

    result = validate_ext(path=str(ext_file))

    assert "Syntax error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_warns_ot_sdk_deprecated(tmp_path: Path) -> None:
    """Verify validate_ext() warns about deprecated ot_sdk imports."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "old_style.py"
    ext_file.write_text('''"""My tool using deprecated SDK."""

from __future__ import annotations

pack = "mytool"
__all__ = ["run"]

from ot_sdk import log, worker_main

def run(*, input: str) -> str:
    """Run the tool.

    Args:
        input: The input

    Returns:
        The result

    Example:
        mytool.run(input="test")
    """
    with log("mytool.run"):
        return input

if __name__ == "__main__":
    worker_main()
''')

    result = validate_ext(path=str(ext_file))

    assert "DEPRECATED" in result
    assert "ot_sdk" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_file_not_found() -> None:
    """Verify validate_ext() handles missing file."""
    from ottools.ot_forge import validate_ext

    result = validate_ext(path="/nonexistent/path/tool.py")

    assert "Error" in result
    assert "not found" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_not_python_file(tmp_path: Path) -> None:
    """Verify validate_ext() rejects non-Python files."""
    from ottools.ot_forge import validate_ext

    txt_file = tmp_path / "file.txt"
    txt_file.write_text("not python")

    result = validate_ext(path=str(txt_file))

    assert "Error" in result
    assert "Not a Python file" in result


@pytest.mark.unit
@pytest.mark.tools
def test_validate_ext_best_practices_warnings(tmp_path: Path) -> None:
    """Verify validate_ext() shows warnings for best practice violations."""
    from ottools.ot_forge import validate_ext

    ext_file = tmp_path / "missing_practices.py"
    ext_file.write_text('''pack = "mytool"
__all__ = ["run"]

def run(input: str) -> str:  # Missing keyword-only args
    return input
''')

    result = validate_ext(path=str(ext_file))

    assert "Validation PASSED" in result
    assert "Warnings:" in result
