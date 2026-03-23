"""Integration tests for the panel tool pack.

Requires Chrome/Chromium to be installed. Tests marked `integration` + `tools`.
Run with: uv run pytest -m "integration and tools" tests/integration/tools/test_panel.py

These tests open a real browser and aiohttp server. Skip in standard CI.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.tools
class TestPanelIntegration:
    """End-to-end integration tests for the panel pack."""

    def test_open_push_close(self) -> None:
        """panel.open → panel.push(markdown) → panel.close — no exceptions."""
        import ottools.panel as panel

        # Reset state in case a previous test left things running
        if panel._server_running:
            panel.close()

        result_open = panel.open()
        assert result_open == "panel ready", f"open() returned: {result_open}"

        result_push = panel.push(kind="markdown", text="# Integration test")
        assert result_push == "pushed markdown", f"push() returned: {result_push}"

        result_close = panel.close()
        assert result_close == "panel closed", f"close() returned: {result_close}"

    def test_open_is_idempotent(self) -> None:
        """Calling panel.open twice returns success both times."""
        import ottools.panel as panel

        try:
            r1 = panel.open()
            r2 = panel.open()
            assert r1 == "panel ready"
            assert r2 == "panel ready"
        finally:
            panel.close()

    def test_push_clear_sequence(self) -> None:
        """push multiple blocks then clear returns panel cleared."""
        import ottools.panel as panel

        try:
            panel.open()
            panel.push(kind="markdown", text="block 1")
            panel.push(kind="markdown", text="block 2")
            result = panel.clear()
            assert result == "panel cleared"
        finally:
            panel.close()
