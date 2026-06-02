from __future__ import annotations

from collections import OrderedDict

import pytest

from ot.display.models import ShowRequest
from ot.display.state import MAX_DIFF_INPUT_BYTES, PREVIEW_LIMIT_BYTES, DisplayState


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

        assert metadata.id.startswith("msg-")
        assert metadata.preview_lines == 1
        assert page.total == 1
        assert page.items[0].id == metadata.id
        assert not hasattr(page.items[0], "inline_payload")

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

    def test_retention_is_bounded(self) -> None:
        state = DisplayState()
        instance = state.get_or_create_instance()
        instance.messages = OrderedDict()

        for index in range(1005):
            state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}"),
            )

        assert len(instance.messages) == 1000

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
