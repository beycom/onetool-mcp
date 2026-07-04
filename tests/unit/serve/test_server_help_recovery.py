"""Seam 1b: disconnected server help carries the enable recovery hint (p13)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ot.meta._help_formatting import _format_server_help


def _cfg() -> MagicMock:
    return MagicMock(source=None, instructions=None)


@pytest.mark.unit
@pytest.mark.serve
class TestServerHelpRecoveryHint:
    """A disconnected server's help output suggests ot_servers.enable(...)."""

    def test_disconnected_server_help_has_recovery(self) -> None:
        out = _format_server_help("playwright", _cfg(), "disconnected", [], "")
        assert "ot_servers.enable(name='playwright')" in out

    def test_connected_server_help_has_no_recovery(self) -> None:
        out = _format_server_help("playwright", _cfg(), "connected", [], "")
        assert "ot_servers.enable" not in out
