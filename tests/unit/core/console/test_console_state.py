"""Tests for the slim, in-memory, inline-only Console message state."""

from __future__ import annotations

import re

import pytest

from ot.console.models import ShowRequest
from ot.console.state import PREVIEW_LIMIT_BYTES, ConsoleState


@pytest.mark.unit
@pytest.mark.core
class TestConsoleState:
    """Test in-memory Console message state behavior."""

    def test_status_does_not_create_message(self) -> None:
        state = ConsoleState()

        first = state.status()
        second = state.status()

        assert first.mcp_instance_id == second.mcp_instance_id
        assert first.message_count == 0
        assert second.message_count == 0

    def test_show_creates_stable_id_and_metadata_only_list(self) -> None:
        state = ConsoleState()
        request = ShowRequest(
            kind="text", content="hello world", metadata={"title": "Greeting"}
        )

        metadata = state.add_message(request=request)
        page = state.list_messages(limit=10, offset=0)

        assert re.fullmatch(r"[0-9a-f]{12}", metadata.id) is not None
        assert metadata.preview_lines == 1
        assert page.total == 1
        assert page.items[0].id == metadata.id

    def test_show_retries_message_id_collision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        values = iter(["111111111111", "111111111111", "222222222222"])
        monkeypatch.setattr("ot.console.state.token_hex", lambda _size: next(values))
        state = ConsoleState()

        first = state.add_message(request=ShowRequest(kind="text", content="one"))
        second = state.add_message(request=ShowRequest(kind="text", content="two"))

        assert first.id == "111111111111"
        assert second.id == "222222222222"

    def test_show_records_preview_line_count(self) -> None:
        state = ConsoleState()
        request = ShowRequest(kind="text", content="one\ntwo\nthree")

        metadata = state.add_message(request=request)

        assert metadata.preview_lines == 3

    def test_read_returns_bounded_preview(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(request=ShowRequest(kind="text", content="hello"))

        result = state.read_message(id=metadata.id)

        assert result is not None
        assert result.preview is not None
        assert result.preview.text == "hello"

    def test_read_unknown_id_returns_none(self) -> None:
        state = ConsoleState()

        assert state.read_message(id="unknownunkno") is None

    def test_clear_messages_removes_messages(self) -> None:
        state = ConsoleState()
        first = state.add_message(request=ShowRequest(kind="text", content="one"))
        state.add_message(request=ShowRequest(kind="text", content="two"))

        cleared = state.clear_messages()

        assert cleared == 2
        assert state.status().message_count == 0
        assert state.list_messages(limit=10, offset=0).total == 0
        assert state.read_message(id=first.id) is None

    def test_retention_bound_drops_oldest_records(self) -> None:
        state = ConsoleState(max_records=3)
        first_id = ""

        for index in range(5):
            metadata = state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}")
            )
            if index == 0:
                first_id = metadata.id

        page = state.list_messages(limit=10, offset=0)
        assert page.total == 3
        assert first_id not in [item.id for item in page.items]
        assert state.read_message(id=first_id) is None

    def test_tail_list_returns_latest_messages_in_oldest_to_newest_order(self) -> None:
        state = ConsoleState()
        ids = [
            state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}")
            ).id
            for index in range(5)
        ]

        page = state.list_messages(limit=2, offset=0, tail=True)

        assert page.total == 5
        assert page.offset == 3
        assert [item.id for item in page.items] == ids[-2:]

    def test_large_inline_string_payload_view_is_bounded(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(
            request=ShowRequest(kind="text", content="x" * (PREVIEW_LIMIT_BYTES + 10))
        )

        payload = state.payload_view(id=metadata.id)

        assert payload is not None
        assert payload["content"] == "x" * PREVIEW_LIMIT_BYTES
        assert payload["preview"] is not None
        assert payload["preview"]["truncated"] is True

    def test_large_dict_payload_view_is_bounded_to_preview_envelope(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(
            request=ShowRequest(
                kind="json", content={"large": "x" * (PREVIEW_LIMIT_BYTES + 10)}
            ),
        )

        payload = state.payload_view(id=metadata.id)

        assert payload is not None
        assert payload["content"]["truncated"] is True
        assert payload["content"]["size_bytes"] > PREVIEW_LIMIT_BYTES
        assert len(payload["content"]["preview"].encode("utf-8")) == PREVIEW_LIMIT_BYTES

    def test_large_list_payload_view_is_bounded_to_first_500_items(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(
            request=ShowRequest(
                kind="table", content=[{"row": index} for index in range(700)]
            ),
        )

        payload = state.payload_view(id=metadata.id)

        assert payload is not None
        assert len(payload["content"]) == 500
        assert payload["content"][-1] == {"row": 499}

    def test_small_list_payload_view_passes_through(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(
            request=ShowRequest(
                kind="table", content=[{"row": index} for index in range(3)]
            ),
        )

        payload = state.payload_view(id=metadata.id)

        assert payload is not None
        assert payload["content"] == [{"row": 0}, {"row": 1}, {"row": 2}]

    def test_large_list_of_huge_items_is_bounded_to_preview_envelope(self) -> None:
        state = ConsoleState()
        huge_item = {"value": "x" * 1000}
        metadata = state.add_message(
            request=ShowRequest(kind="table", content=[huge_item] * 500),
        )

        payload = state.payload_view(id=metadata.id)

        assert payload is not None
        assert payload["content"]["truncated"] is True
        assert payload["content"]["size_bytes"] > PREVIEW_LIMIT_BYTES
        assert len(payload["content"]["preview"].encode("utf-8")) == PREVIEW_LIMIT_BYTES

    def test_structured_content_does_not_generate_summary_metadata(self) -> None:
        state = ConsoleState()

        json_metadata = state.add_message(
            request=ShowRequest(kind="json", content={"ok": True, "items": [1, 2]})
        )
        table_metadata = state.add_message(
            request=ShowRequest(
                kind="table",
                content=[{"name": "alpha", "value": 1}, {"name": "beta", "value": 2}],
            ),
        )

        assert "summary" not in json_metadata.metadata
        assert "summary" not in table_metadata.metadata

    def test_list_filters_source_against_metadata(self) -> None:
        state = ConsoleState()
        first = state.add_message(
            request=ShowRequest(
                kind="text", content="one", metadata={"source": "run-a"}
            )
        )
        state.add_message(
            request=ShowRequest(
                kind="text", content="two", metadata={"source": "run-b"}
            )
        )
        state.add_message(
            request=ShowRequest(
                kind="text", content="three", metadata={"title": "run-a"}
            )
        )

        page = state.list_messages(limit=10, offset=0, source="run-a")

        assert [item.id for item in page.items] == [first.id]
