"""Unit tests for support module."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestGetSupportBanner:
    """Tests for get_support_banner()."""

    def test_returns_rich_markup(self) -> None:
        """Returns string with Rich markup tags."""
        from ot.support import get_support_banner

        result = get_support_banner()

        assert isinstance(result, str)
        assert "[yellow]" in result
        assert "[/yellow]" in result
        assert "[link=" in result

    def test_contains_kofi_url(self) -> None:
        """Banner contains the Ko-fi URL."""
        from ot.support import KOFI_URL, get_support_banner

        result = get_support_banner()

        assert KOFI_URL in result

    def test_contains_coffee_emoji(self) -> None:
        """Banner contains coffee emoji."""
        from ot.support import get_support_banner

        result = get_support_banner()

        assert "☕" in result
