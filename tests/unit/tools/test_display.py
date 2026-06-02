from __future__ import annotations

import pytest

from ottools import display


@pytest.mark.unit
@pytest.mark.tools
class TestDisplayTools:
    """Test public display tool functions."""

    def test_status_returns_url_without_message_payloads(self) -> None:
        result = display.status()

        assert result["status"] == "running"
        assert result["url"].startswith("http://127.0.0.1:")
        assert "messages" not in result

    def test_show_read_list_and_focus(self) -> None:
        created = display.show(kind="text", content="tool payload", title="Tool", expand="expanded")

        read = display.read(id=created["id"])
        page = display.list(limit=10)
        focused = display.focus(id=created["id"])

        assert isinstance(read, dict)
        assert read["metadata"]["id"] == created["id"]
        assert read["metadata"]["expand"] == "expanded"
        assert read["preview"]["text"] == "tool payload"
        assert any(item["id"] == created["id"] for item in page["items"])
        assert isinstance(focused, dict)
        assert focused["id"] == created["id"]

    def test_unknown_read_returns_error(self) -> None:
        result = display.read(id="msg-missing")

        assert isinstance(result, str)
        assert result.startswith("Error:")
