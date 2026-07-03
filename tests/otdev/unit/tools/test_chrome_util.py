"""Unit tests for chrome_util tool pack.

Covers the full annotation lifecycle and error handling via a mocked
chrome_devtools proxy. Implementation details (_extract_result, _exec_js,
_check_server) are not tested directly — behaviour is verified through the
public API.
"""

from __future__ import annotations

import json

import pytest

_READY = json.dumps({"ready": True, "version": "2.0.0"})


@pytest.mark.unit
@pytest.mark.tools
class TestChromeUtil:
    def test_happy_path(self, mock_proxy_manager) -> None:
        """Full lifecycle: inject → highlight → scan → clear → guide_user succeed."""
        from otdev.tools import chrome_util

        mock_proxy_manager.servers = ["chrome_devtools"]

        # inject — already ready (1 call)
        mock_proxy_manager.call_tool_sync.return_value = _READY
        inject = chrome_util.inject_annotations()
        assert inject["success"] is True
        assert inject["version"] == "2.0.0"

        # highlight — inject check + result (2 calls)
        mock_proxy_manager.call_tool_sync.side_effect = [
            _READY,
            json.dumps({"success": True, "count": 2, "ids": ["ann-0", "ann-1"]}),
        ]
        hl = chrome_util.highlight_element(selector=".btn", label="Buttons")
        assert hl["success"] is True
        assert hl["count"] == 2

        # scan — inject check + result (2 calls)
        anns = [{"id": "ann-0", "label": "Buttons"}, {"id": "ann-1", "label": "Buttons"}]
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, json.dumps(anns)]
        assert len(chrome_util.scan_annotations()) == 2

        # clear — removes all annotations
        mock_proxy_manager.call_tool_sync.side_effect = None
        mock_proxy_manager.call_tool_sync.return_value = json.dumps({"success": True, "cleared": 2})
        cleared = chrome_util.clear_annotations()
        assert cleared["success"] is True
        assert cleared["cleared"] == 2

        # guide_user — inject check + N step calls
        step = json.dumps({"success": True, "count": 1, "ids": ["g0"]})
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, step, step]
        guide = chrome_util.guide_user(
            task="Fill and submit",
            steps=[
                {"selector": "input", "label": "1. Enter data"},
                {"selector": "button", "label": "2. Submit"},
            ],
        )
        assert guide["task"] == "Fill and submit"
        assert guide["total"] == 2
        assert guide["highlighted"] == 2

    def test_error_handling(self, mock_proxy_manager) -> None:
        """All operations return proper error shapes when server is not connected."""
        from otdev.tools import chrome_util

        mock_proxy_manager.servers = []

        assert chrome_util.inject_annotations()["success"] is False
        assert chrome_util.highlight_element(selector=".btn", label="X")["count"] == 0
        assert chrome_util.scan_annotations() == []
        assert chrome_util.clear_annotations()["success"] is False
        guide = chrome_util.guide_user(task="T", steps=[{"selector": ".a", "label": "A"}])
        assert guide["highlighted"] == 0
        assert "error" in guide

    def test_custom_server_name(self, mock_proxy_manager) -> None:
        """Annotation calls can target a compatible non-default server."""
        from otdev.tools import chrome_util

        mock_proxy_manager.servers = ["chrome_devtool_connect"]
        mock_proxy_manager.call_tool_sync.return_value = _READY

        result = chrome_util.inject_annotations(server="chrome_devtool_connect")

        assert result["success"] is True
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "chrome_devtool_connect"
        assert call_args[0][1] == "evaluate_script"
