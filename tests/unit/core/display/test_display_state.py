from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from ot.display.models import ShowRequest
from ot.display.state import (
    HOT_MESSAGE_WINDOW,
    MAX_DIFF_INPUT_BYTES,
    MAX_MESSAGE_RECORDS,
    PREVIEW_LIMIT_BYTES,
    DisplayState,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.core
class TestDisplayState:
    """Test in-memory display state behavior."""

    def test_status_does_not_create_message(self) -> None:
        state = DisplayState()

        first = state.status(base_url="http://127.0.0.1:1")
        second = state.status(base_url="http://127.0.0.1:1")

        assert first.mcp_instance_id == second.mcp_instance_id
        assert first.message_count == 0
        assert second.message_count == 0

    def test_show_creates_stable_id_and_metadata_only_list(self) -> None:
        state = DisplayState()
        request = ShowRequest(kind="text", content="hello world", title="Greeting")

        metadata = state.add_message(request=request)
        page = state.list_messages(limit=10, offset=0)

        assert re.fullmatch(r"[0-9a-f]{12}", metadata.id) is not None
        assert metadata.preview_lines == 1
        assert page.total == 1
        assert page.items[0].id == metadata.id
        assert not hasattr(page.items[0], "inline_payload")

    def test_show_retries_message_id_collision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        values = iter(["111111111111", "111111111111", "222222222222"])
        monkeypatch.setattr("ot.display.state.token_hex", lambda _size: next(values))
        state = DisplayState()

        first = state.add_message(request=ShowRequest(kind="text", content="one"))
        second = state.add_message(request=ShowRequest(kind="text", content="two"))

        assert first.id == "111111111111"
        assert second.id == "222222222222"

    def test_show_records_preview_line_count(self) -> None:
        state = DisplayState()
        request = ShowRequest(kind="text", content="one\ntwo\nthree")

        metadata = state.add_message(request=request)

        assert metadata.preview_lines == 3

    def test_read_returns_bounded_preview(self) -> None:
        state = DisplayState()
        metadata = state.add_message(
            request=ShowRequest(kind="text", content="hello"),
        )

        result = state.read_message(id=metadata.id)

        assert result is not None
        assert result.preview is not None
        assert result.preview.text == "hello"

    def test_focus_reports_queued_without_clients(self) -> None:
        state = DisplayState()
        metadata = state.add_message(
            request=ShowRequest(kind="text", content="hello"),
        )

        result = state.focus(id=metadata.id)

        assert result is not None
        assert result.delivered is False
        assert result.queued is True

    def test_focus_reports_delivered_after_event_poll(self) -> None:
        state = DisplayState()
        instance = state.get_or_create_instance()
        metadata = state.add_message(
            request=ShowRequest(kind="text", content="hello"),
        )

        events = state.poll_events(instance_id=instance.id, token=instance.token)
        result = state.focus(id=metadata.id)

        assert events is not None
        assert result is not None
        assert result.delivered is True
        assert result.queued is False

    def test_message_events_are_coalesced_without_client(self) -> None:
        state = DisplayState()
        instance = state.get_or_create_instance()

        for index in range(25):
            state.add_message(request=ShowRequest(kind="text", content=f"message {index}"))

        assert len(instance.event_queue) == 1
        assert instance.event_queue[0]["type"] == "message"

    def test_hot_window_is_bounded_while_cached_messages_remain_readable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()
        instance = state.get_or_create_instance()
        first_id = ""

        for index in range(HOT_MESSAGE_WINDOW + 5):
            metadata = state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}"),
            )
            if index == 0:
                first_id = metadata.id

        assert len(instance.messages) == HOT_MESSAGE_WINDOW
        assert len(instance.message_ids) == HOT_MESSAGE_WINDOW + 5
        assert first_id not in instance.messages
        assert state.read_message(id=first_id) is not None
        assert state.payload_view(id=first_id, base_url="http://127.0.0.1:1") is not None
        assert state.focus(id=first_id) is not None
        page = state.list_messages(limit=1, offset=0)
        assert page.total == HOT_MESSAGE_WINDOW + 5
        assert page.items[0].id == first_id
        assert (tmp_path / ".onetool" / "state" / "display").is_dir()

    def test_tail_list_returns_latest_messages_in_oldest_to_newest_order(self) -> None:
        state = DisplayState()
        ids = [
            state.add_message(request=ShowRequest(kind="text", content=f"message {index}")).id
            for index in range(5)
        ]

        page = state.list_messages(limit=2, offset=0, tail=True)

        assert page.total == 5
        assert page.offset == 3
        assert [item.id for item in page.items] == ids[-2:]

    def test_cold_message_cache_is_bounded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()
        instance = state.get_or_create_instance()
        first_id = ""

        for index in range(MAX_MESSAGE_RECORDS + 1):
            metadata = state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}"),
            )
            if index == 0:
                first_id = metadata.id

        assert len(instance.message_ids) == MAX_MESSAGE_RECORDS
        assert first_id not in instance.message_ids
        assert state.read_message(id=first_id) is None
        assert instance.cache_dir is not None
        assert not (instance.cache_dir / f"{first_id}.json").exists()

    def test_large_inline_string_payload_view_is_bounded(self) -> None:
        state = DisplayState()
        metadata = state.add_message(
            request=ShowRequest(kind="text", content="x" * (PREVIEW_LIMIT_BYTES + 10)),
        )

        payload = state.payload_view(id=metadata.id, base_url="http://127.0.0.1:1")

        assert payload is not None
        assert payload["content"] == "x" * PREVIEW_LIMIT_BYTES
        assert payload["preview"] is not None
        assert payload["preview"]["truncated"] is True

    def test_large_dict_payload_view_is_bounded_to_preview_envelope(self) -> None:
        state = DisplayState()
        metadata = state.add_message(
            request=ShowRequest(
                kind="json",
                content={"large": "x" * (PREVIEW_LIMIT_BYTES + 10)},
            ),
        )

        payload = state.payload_view(id=metadata.id, base_url="http://127.0.0.1:1")

        assert payload is not None
        assert payload["content"]["truncated"] is True
        assert payload["content"]["size_bytes"] > PREVIEW_LIMIT_BYTES
        assert len(payload["content"]["preview"].encode("utf-8")) == PREVIEW_LIMIT_BYTES

    def test_large_list_payload_view_is_bounded_to_first_500_items(self) -> None:
        state = DisplayState()
        metadata = state.add_message(
            request=ShowRequest(kind="table", content=[{"row": index} for index in range(700)]),
        )

        payload = state.payload_view(id=metadata.id, base_url="http://127.0.0.1:1")

        assert payload is not None
        assert len(payload["content"]) == 500
        assert payload["content"][-1] == {"row": 499}

    def test_large_generated_file_diff_uses_skip_preview(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old_path = tmp_path / "old.txt"
        new_path = tmp_path / "new.txt"
        old_path.write_text("a" * (MAX_DIFF_INPUT_BYTES + 1), encoding="utf-8")
        new_path.write_text("b", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()

        metadata = state.add_message(
            request=ShowRequest(kind="file_diff", old_path="old.txt", new_path="new.txt"),
        )
        payload = state.payload_view(id=metadata.id, base_url="http://127.0.0.1:1")

        assert payload is not None
        assert payload["preview"] is not None
        assert "Diff preview skipped" in payload["preview"]["text"]
        assert payload["content"].startswith("Diff preview skipped")

    def test_generated_file_diff_uses_structured_path_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old_path = tmp_path / "old.txt"
        new_path = tmp_path / "new.txt"
        old_path.write_text("old\n", encoding="utf-8")
        new_path.write_text("new\n", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()

        metadata = state.add_message(
            request=ShowRequest(kind="file_diff", old_path="old.txt", new_path="new.txt"),
        )

        assert metadata.payload.mode == "file_diff"
        assert metadata.payload.path is None
        assert metadata.payload.old_path == str(old_path)
        assert metadata.payload.new_path == str(new_path)
        assert metadata.payload.language == "diff"

    def test_structured_content_gets_useful_default_summaries(self) -> None:
        state = DisplayState()

        json_metadata = state.add_message(
            request=ShowRequest(kind="json", content={"ok": True, "items": [1, 2]}),
        )
        table_metadata = state.add_message(
            request=ShowRequest(kind="table", content=[{"name": "alpha", "value": 1}, {"name": "beta", "value": 2}]),
        )

        assert json_metadata.summary == "2 keys: ok, items"
        assert table_metadata.summary == "2 rows: name, value"

    def test_missing_file_payload_returns_clear_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()

        with pytest.raises(ValueError, match=r"file path not found: missing\.txt"):
            state.add_message(request=ShowRequest(kind="file", path="missing.txt"))

    def test_missing_image_payload_returns_clear_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()

        with pytest.raises(ValueError, match=r"image path not found: missing\.png"):
            state.add_message(request=ShowRequest(kind="image", path="missing.png"))

    def test_missing_file_diff_payload_returns_clear_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        state = DisplayState()

        with pytest.raises(ValueError, match=r"file_diff path not found: missing\.diff"):
            state.add_message(request=ShowRequest(kind="file_diff", path="missing.diff"))
