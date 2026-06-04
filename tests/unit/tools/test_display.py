from __future__ import annotations

import pytest

from ottools import display


@pytest.mark.unit
@pytest.mark.tools
class TestDisplayTools:
    """Test public display tool functions."""

    def test_status_returns_metadata_without_url_or_payloads(self) -> None:
        result = display.status()

        assert result["status"] == "running"
        assert "url" not in result
        assert "messages" not in result

    def test_show_read_list_and_focus(self) -> None:
        created = display.show(kind="text", content="tool payload", metadata={"title": "Tool", "source": "unit"})

        read = display.read(id=created["id"])
        page = display.list(limit=10, source="unit")
        focused = display.focus(id=created["id"])

        assert created["kind"] == "text"
        assert created["path"] is None
        assert isinstance(read, dict)
        assert read["metadata"]["id"] == created["id"]
        assert read["metadata"]["metadata"]["title"] == "Tool"
        assert read["preview"]["text"] == "tool payload"
        assert any(item["id"] == created["id"] for item in page["items"])
        assert isinstance(focused, dict)
        assert focused["id"] == created["id"]

    def test_clear_removes_current_display_messages(self) -> None:
        first = display.show(kind="text", content="first", metadata={"source": "clear-test"})
        display.show(kind="text", content="second", metadata={"source": "clear-test"})

        result = display.clear()

        assert result["cleared"] >= 2
        assert result["message_count"] == 0
        assert "url" not in result
        assert display.list(limit=10)["total"] == 0
        assert display.read(id=first["id"]) == f"Error: display message not found: {first['id']}"
        assert display.status()["message_count"] == 0

    def test_show_rejects_removed_metadata_fields(self) -> None:
        with pytest.raises(TypeError):
            display.show(kind="text", content="tool payload", title="Tool")  # type: ignore[call-arg]

    def test_show_clip_uses_clipboard_image_storage(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        stored = tmp_path / "stored.png"
        stored.write_bytes(b"png")

        monkeypatch.setattr(display, "clipboard_contains_image_object", lambda: True)
        def fake_load_image_source(*, img: str) -> object:
            del img
            return type("Loaded", (), {"path": str(stored)})()

        monkeypatch.setattr(display, "load_image_source", fake_load_image_source)
        calls = []
        monkeypatch.setattr(display, "show", lambda **kwargs: calls.append(kwargs) or {"id": "1", **kwargs})

        result = display.show_clip(metadata={"source": "clip-test"})

        assert isinstance(result, dict)
        assert result["kind"] == "image"
        assert calls == [{"kind": "image", "path": str(stored), "metadata": {"source": "clip-test"}}]

    def test_show_clip_displays_clipboard_path(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        clip_file = tmp_path / "note.txt"
        clip_file.write_text("hello", encoding="utf-8")

        monkeypatch.setattr(display, "clipboard_contains_image_object", lambda: False)
        monkeypatch.setattr(display, "resolve_clipboard_file_path", lambda: clip_file)
        def fake_path_is_image(path: object) -> bool:
            del path
            return False

        monkeypatch.setattr(display, "_path_is_image", fake_path_is_image)
        monkeypatch.setattr(display, "show", lambda **kwargs: {"id": "1", **kwargs})

        result = display.show_clip()

        assert isinstance(result, dict)
        assert result["kind"] == "file"
        assert result["path"] == str(clip_file)

    def test_show_clip_returns_clear_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(display, "clipboard_contains_image_object", lambda: False)
        monkeypatch.setattr(display, "resolve_clipboard_file_path", lambda: (_ for _ in ()).throw(ValueError("no path")))

        result = display.show_clip()

        assert result == "Error: no path"

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
        assert "url" not in result
        assert expected_kinds <= set(result["ids_by_kind"])
        assert result["count"] >= len(expected_kinds)
        assert "content" not in result
