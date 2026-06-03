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

    @pytest.mark.parametrize(
        ("limit", "offset", "match"),
        [
            (0, 0, "limit must be between 1 and 500"),
            (501, 0, "limit must be between 1 and 500"),
            (1, -1, "offset must be greater than or equal to 0"),
        ],
    )
    def test_list_rejects_invalid_pagination(self, limit: int, offset: int, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            display.list(limit=limit, offset=offset)

    def test_unknown_read_returns_error(self) -> None:
        result = display.read(id="missing")

        assert isinstance(result, str)
        assert result.startswith("Error:")

    def test_seed_mock_messages_returns_metadata_only_for_all_v1_kinds(self) -> None:
        result = display.seed_mock_messages()

        expected_kinds = {
            "text",
            "markdown",
            "code",
            "file",
            "diff",
            "file_diff",
            "image",
            "json",
            "mermaid",
            "yaml",
            "table",
        }
        assert result["test_only"] is True
        assert result["url"].startswith("http://127.0.0.1:")
        assert expected_kinds <= set(result["ids_by_kind"])
        assert result["count"] >= len(expected_kinds)
        assert "content" not in result
