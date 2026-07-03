"""Unit tests for play_util tool pack.

Covers the full annotation lifecycle and error handling via a mocked
playwright proxy. Also verifies that Playwright's markdown-wrapped response
format is correctly unwrapped.
"""

from __future__ import annotations

import json

import pytest

_READY = json.dumps({"ready": True, "version": "2.0.0"})


def _pw_wrap(value: str) -> str:
    """Wrap a value in Playwright browser_evaluate markdown format."""
    return (
        f"### Result\n{value}\n"
        f"### Ran Playwright code\n```js\nawait page.evaluate(...);\n```"
    )


@pytest.mark.unit
@pytest.mark.tools
class TestPlayUtil:
    def test_happy_path(self, mock_proxy_manager) -> None:
        """Full lifecycle via playwright server; handles markdown-wrapped responses."""
        from otdev.tools import play_util

        mock_proxy_manager.servers = ["playwright"]

        # inject — already ready; Playwright wraps the JSON response in markdown
        mock_proxy_manager.call_tool_sync.return_value = _pw_wrap(_READY)
        inject = play_util.inject_annotations()
        assert inject["success"] is True
        assert inject["version"] == "2.0.0"

        # highlight — inject check + wrapped result (2 calls)
        hl_json = json.dumps({"success": True, "count": 1, "ids": ["ann-0"]})
        mock_proxy_manager.call_tool_sync.side_effect = [_pw_wrap(_READY), _pw_wrap(hl_json)]
        hl = play_util.highlight_element(selector="#btn", label="Submit")
        assert hl["success"] is True
        assert hl["count"] == 1

        # scan — inject check + result (2 calls)
        ann_json = json.dumps([{"id": "ann-0", "label": "Submit"}])
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, ann_json]
        assert len(play_util.scan_annotations()) == 1

        # clear — single call
        mock_proxy_manager.call_tool_sync.side_effect = None
        mock_proxy_manager.call_tool_sync.return_value = json.dumps({"success": True, "cleared": 1})
        assert play_util.clear_annotations()["success"] is True

        # guide_user — inject check + step calls
        step = json.dumps({"success": True, "count": 1, "ids": ["g0"]})
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, step]
        guide = play_util.guide_user(
            task="Fill form",
            steps=[{"selector": "input", "label": "Enter name"}],
        )
        assert guide["highlighted"] == 1

    def test_enable_auto_inject(self, mock_proxy_manager) -> None:
        """enable_auto_inject calls browser_run_code and returns success."""
        from otdev.tools import play_util

        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = _pw_wrap('{"success": true}')

        result = play_util.enable_auto_inject()

        assert result["success"] is True
        assert result["auto_inject"] is True
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "playwright"
        assert call_args[0][1] == "browser_run_code"
        assert "addInitScript" in call_args[0][2]["code"]

    def test_error_handling(self, mock_proxy_manager) -> None:
        """All operations fail gracefully when playwright server is not connected."""
        from otdev.tools import play_util

        mock_proxy_manager.servers = []

        assert play_util.inject_annotations()["success"] is False
        assert play_util.enable_auto_inject()["success"] is False
        assert play_util.highlight_element(selector=".btn", label="X")["count"] == 0
        assert play_util.scan_annotations() == []
        assert play_util.clear_annotations()["success"] is False
        guide = play_util.guide_user(task="T", steps=[{"selector": ".a", "label": "A"}])
        assert guide["highlighted"] == 0
        assert "error" in guide

    def test_custom_server_name(self, mock_proxy_manager) -> None:
        """Annotation calls can target a compatible non-default server."""
        from otdev.tools import play_util

        mock_proxy_manager.servers = ["playwright_proxy"]
        mock_proxy_manager.call_tool_sync.return_value = _pw_wrap(_READY)

        result = play_util.inject_annotations(server="playwright_proxy")

        assert result["success"] is True
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "playwright_proxy"
        assert call_args[0][1] == "browser_evaluate"

    def test_enable_auto_inject_custom_server_name(self, mock_proxy_manager) -> None:
        """Auto-inject uses browser_run_code on the selected server."""
        from otdev.tools import play_util

        mock_proxy_manager.servers = ["playwright_proxy"]
        mock_proxy_manager.call_tool_sync.return_value = _pw_wrap('{"success": true}')

        result = play_util.enable_auto_inject(server="playwright_proxy")

        assert result["success"] is True
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "playwright_proxy"
        assert call_args[0][1] == "browser_run_code"
