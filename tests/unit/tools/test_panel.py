"""Unit tests for the panel tool pack.

Tests cover:
- server.py file proxy: allowed path (200), outside root (403), traversal (403)
- panel.py guards: push/clear before open return errors; push unknown kind returns error;
  close when already closed is a no-op
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

import ottools._panel.server as server_module
import ottools.panel as panel_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_panel_state() -> None:
    """Reset panel module state between tests."""
    panel_module._browser = None
    panel_module._tab = None
    panel_module._server_running = False
    panel_module._port = 7770
    panel_module._loop = None
    panel_module._loop_thread = None


def _reset_server_state() -> None:
    """Reset server module state between tests."""
    server_module._ws_clients.clear()
    server_module._runner = None
    server_module._loop = None
    server_module._allowed_roots = []


# ===========================================================================
# 10.1 server.py file proxy tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestFileProxy:
    """Tests for the /file?path= endpoint path allowlist."""

    def setup_method(self) -> None:
        _reset_server_state()

    def _make_allowed_app(self, tmp_path: Path) -> Any:
        """Build an aiohttp app with tmp_path as the allowed root."""
        server_module._allowed_roots = [tmp_path]
        return server_module._make_app()

    @pytest.mark.asyncio
    async def test_allowed_file_served_200(self, tmp_path: Path) -> None:
        """File within allowed root is served with HTTP 200."""
        allowed_file = tmp_path / "report.html"
        allowed_file.write_text("<h1>OK</h1>")

        app = self._make_allowed_app(tmp_path)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/file?path={allowed_file}")
            assert resp.status == 200
            text = await resp.text()
            assert "OK" in text

    @pytest.mark.asyncio
    async def test_file_outside_root_returns_403(self, tmp_path: Path) -> None:
        """File outside allowed root returns HTTP 403."""
        app = self._make_allowed_app(tmp_path)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/file?path=/etc/passwd")
            assert resp.status == 403

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Path traversal sequences are neutralised and access is denied."""
        app = self._make_allowed_app(tmp_path)
        traversal = str(tmp_path) + "/../../../etc/passwd"
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/file?path={traversal}")
            assert resp.status == 403

    @pytest.mark.asyncio
    async def test_missing_path_param_returns_400(self, tmp_path: Path) -> None:
        """Missing path query parameter returns HTTP 400."""
        app = self._make_allowed_app(tmp_path)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/file")
            assert resp.status == 400


# ===========================================================================
# 10.2 panel.py guard tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestPanelGuards:
    """Tests for panel.py public tool guards (no browser/server started)."""

    def setup_method(self) -> None:
        _reset_panel_state()

    def teardown_method(self) -> None:
        _reset_panel_state()

    def test_push_before_open_returns_error(self) -> None:
        """panel.push before panel.open returns error string."""
        result = panel_module.push(kind="markdown", text="hello")
        assert result.startswith("Error:")
        assert "panel" in result.lower()

    def test_push_unknown_kind_after_open_returns_error(self) -> None:
        """panel.push with unknown kind returns error string."""
        # Fake the server as running so guard passes
        panel_module._server_running = True
        with patch.object(panel_module, "push", wraps=panel_module.push):
            result = panel_module.push(kind="nonexistent_kind", text="foo")
        panel_module._server_running = False
        assert result.startswith("Error:")
        assert "nonexistent_kind" in result

    def test_clear_before_open_returns_error(self) -> None:
        """panel.clear before panel.open returns error string."""
        result = panel_module.clear()
        assert result.startswith("Error:")

    def test_close_when_already_closed_is_noop(self) -> None:
        """panel.close when already closed returns success without error."""
        result = panel_module.close()
        assert result == "panel closed"

    def test_close_twice_is_noop(self) -> None:
        """Calling panel.close twice in a row is safe."""
        result1 = panel_module.close()
        result2 = panel_module.close()
        assert result1 == "panel closed"
        assert result2 == "panel closed"

    def test_push_broadcasts_on_success(self) -> None:
        """push with valid kind calls server.broadcast when panel is open."""
        panel_module._server_running = True
        from ottools._panel import server

        with patch.object(server, "broadcast") as mock_broadcast:
            result = panel_module.push(kind="markdown", text="# hi")
            assert result == "pushed markdown"
            mock_broadcast.assert_called_once()
            payload = json.loads(mock_broadcast.call_args[0][0])
            assert payload["kind"] == "markdown"
            assert payload["text"] == "# hi"
            assert "id" in payload

        panel_module._server_running = False

    def test_clear_broadcasts_on_success(self) -> None:
        """clear calls server.broadcast with kind=clear when panel is open."""
        panel_module._server_running = True
        from ottools._panel import server

        with patch.object(server, "broadcast") as mock_broadcast:
            result = panel_module.clear()
            assert result == "panel cleared"
            mock_broadcast.assert_called_once()
            payload = json.loads(mock_broadcast.call_args[0][0])
            assert payload["kind"] == "clear"

        panel_module._server_running = False
