"""Unit tests for ot_servers pack."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.tools
def test_ot_servers_enable_delegates() -> None:
    """ot_servers.enable() delegates to backend."""
    from ottools.ot_servers import enable

    with patch("ottools.ot_servers._enable", return_value="ok") as mock_enable:
        result = enable(name="github")

    mock_enable.assert_called_once_with(name="github")
    assert result == "ok"


@pytest.mark.unit
@pytest.mark.tools
def test_ot_servers_disable_delegates() -> None:
    """ot_servers.disable() delegates to backend."""
    from ottools.ot_servers import disable

    with patch("ottools.ot_servers._disable", return_value="ok") as mock_disable:
        result = disable(name="github")

    mock_disable.assert_called_once_with(name="github")
    assert result == "ok"


@pytest.mark.unit
@pytest.mark.tools
def test_ot_servers_restart_delegates() -> None:
    """ot_servers.restart() delegates to backend."""
    from ottools.ot_servers import restart

    with patch("ottools.ot_servers._restart", return_value="ok") as mock_restart:
        result = restart(name="github")

    mock_restart.assert_called_once_with(name="github")
    assert result == "ok"


@pytest.mark.unit
@pytest.mark.tools
def test_ot_servers_status_delegates() -> None:
    """ot_servers.status() delegates to backend."""
    from ottools.ot_servers import status

    with patch("ottools.ot_servers._status", return_value="ok") as mock_status:
        result = status(name="github")

    mock_status.assert_called_once_with(name="github")
    assert result == "ok"
