"""Unit tests for platform utilities."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_darwin() -> None:
    """Test install hint for macOS."""
    from ot.utils.platform import get_install_hint

    with patch("ot.utils.platform.sys.platform", "darwin"):
        hint = get_install_hint("rg")
        assert "brew install ripgrep" in hint


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_linux() -> None:
    """Test install hint for Linux."""
    from ot.utils.platform import get_install_hint

    with patch("ot.utils.platform.sys.platform", "linux"):
        hint = get_install_hint("rg")
        assert "apt install ripgrep" in hint


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_linux2() -> None:
    """Test install hint for Linux (linux2 variant)."""
    from ot.utils.platform import get_install_hint

    with patch("ot.utils.platform.sys.platform", "linux2"):
        hint = get_install_hint("rg")
        assert "apt install ripgrep" in hint


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_win32() -> None:
    """Test install hint for Windows."""
    from ot.utils.platform import get_install_hint

    with patch("ot.utils.platform.sys.platform", "win32"):
        hint = get_install_hint("rg")
        assert "winget install" in hint or "scoop install" in hint


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_unknown_tool() -> None:
    """Test install hint for unknown tool."""
    from ot.utils.platform import get_install_hint

    hint = get_install_hint("unknown_tool_xyz")
    assert "Install unknown_tool_xyz" in hint


@pytest.mark.unit
@pytest.mark.core
def test_get_install_hint_playwright() -> None:
    """Test install hint for playwright."""
    from ot.utils.platform import get_install_hint

    with patch("ot.utils.platform.sys.platform", "darwin"):
        hint = get_install_hint("playwright")
        assert "pip install playwright" in hint
        assert "playwright install" in hint


@pytest.mark.unit
@pytest.mark.core
def test_install_commands_structure() -> None:
    """Test that INSTALL_COMMANDS has expected structure."""
    from ot.utils.platform import INSTALL_COMMANDS

    # Check that rg and playwright are defined
    assert "rg" in INSTALL_COMMANDS
    assert "playwright" in INSTALL_COMMANDS

    # Check that each has platform-specific commands
    for tool in INSTALL_COMMANDS:
        assert "darwin" in INSTALL_COMMANDS[tool]
        assert "linux" in INSTALL_COMMANDS[tool]
        assert "win32" in INSTALL_COMMANDS[tool]
