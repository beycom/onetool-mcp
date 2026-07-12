"""Tests for metadata-only Console state and disk-backed message bodies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from ot.console.models import MessageMetadata, ShowRequest
from ot.console.state import PREVIEW_LIMIT_BYTES, ConsoleState
from ot.console.storage import message_body_path


@pytest.mark.unit
@pytest.mark.core
class TestConsoleState:
    """Test metadata retention and message-body persistence."""

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
        instance = state.get_or_create_instance()
        assert isinstance(instance.messages[metadata.id], MessageMetadata)

    def test_add_writes_json_body_that_round_trips(self) -> None:
        state = ConsoleState()
        metadata = state.add_message(
            request=ShowRequest(
                kind="json",
                content={"status": "ready"},
                metadata={"source": "unit"},
            )
        )
        instance = state.get_or_create_instance()
        path = message_body_path(message_id=metadata.id, instance_id=instance.id)

        record = json.loads(path.read_text(encoding="utf-8"))

        assert record["id"] == metadata.id
        assert record["metadata"] == metadata.model_dump(mode="json")
        assert record["preview"]["text"] == '{\n  "status": "ready"\n}'
        assert record["inline_payload"] == {"status": "ready"}

    def test_failed_body_write_fails_add_and_removes_temporary_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = ConsoleState()

        def _fail_replace(_path: Path, _target: Path) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr(Path, "replace", _fail_replace)

        with pytest.raises(OSError, match="disk full"):
            state.add_message(request=ShowRequest(kind="text", content="hello"))

        instance = state.get_or_create_instance()
        messages_dir = message_body_path(
            message_id="unused", instance_id=instance.id
        ).parent
        assert state.list_messages(limit=10, offset=0).total == 0
        assert list(messages_dir.iterdir()) == []

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

    def test_read_loads_body_outside_state_lock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ot.console import storage

        state = ConsoleState()
        metadata = state.add_message(request=ShowRequest(kind="text", content="hello"))
        real_read = storage.read_message_body

        def _read_without_lock(*, message_id: str, instance_id: str | None = None):
            assert state._lock.acquire(blocking=False)
            state._lock.release()
            return real_read(message_id=message_id, instance_id=instance_id)

        monkeypatch.setattr(storage, "read_message_body", _read_without_lock)

        assert state.read_message(id=metadata.id) is not None

    def test_list_does_not_read_message_bodies(self) -> None:
        state = ConsoleState()
        state.add_message(request=ShowRequest(kind="text", content="hello"))

        with patch(
            "ot.console.storage.read_message_body",
            side_effect=AssertionError("list touched disk"),
        ):
            page = state.list_messages(limit=10, offset=0)

        assert page.total == 1

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
        assert not message_body_path(
            message_id=first.id,
            instance_id=state.get_or_create_instance().id,
        ).parent.exists()

    def test_retention_bound_drops_oldest_records(self) -> None:
        state = ConsoleState(max_records=3)
        first_id = ""

        for index in range(5):
            metadata = state.add_message(
                request=ShowRequest(kind="text", content=f"message {index}")
            )
            if index == 0:
                first_id = metadata.id

        instance = state.get_or_create_instance()
        page = state.list_messages(limit=10, offset=0)
        assert page.total == 3
        assert first_id not in [item.id for item in page.items]
        assert state.read_message(id=first_id) is None
        assert not message_body_path(
            message_id=first_id, instance_id=instance.id
        ).exists()

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


@pytest.mark.unit
@pytest.mark.core
class TestConsoleFileMessages:
    """Test file-reference message construction."""

    def test_textual_file_ref_carries_head_preview(self, tmp_path) -> None:
        state = ConsoleState()
        target = tmp_path / "sample.py"
        target.write_text("a = 1\nb = 2\n")

        metadata = state.add_file_message(kind="code", path=str(target))

        assert metadata.payload.mode == "file_ref"
        assert metadata.payload.path == str(target)
        assert metadata.payload.language == "python"
        assert metadata.payload.size_bytes == len("a = 1\nb = 2\n")
        read = state.read_message(id=metadata.id)
        assert read is not None
        assert read.preview is not None
        assert read.preview.text == "a = 1\nb = 2\n"
        record = json.loads(
            message_body_path(
                message_id=metadata.id,
                instance_id=state.get_or_create_instance().id,
            ).read_text(encoding="utf-8")
        )
        assert record["id"] == metadata.id
        assert record["inline_payload"] is None
        assert read.preview.truncated is False

    def test_binary_file_ref_has_no_preview(self, tmp_path) -> None:
        state = ConsoleState()
        target = tmp_path / "blob.bin"
        target.write_bytes(b"\x00\x01\x02binary")

        metadata = state.add_file_message(kind="file", path=str(target))

        assert metadata.payload.mode == "file_ref"
        read = state.read_message(id=metadata.id)
        assert read is not None
        assert read.preview is None

    def test_diff_ref_records_both_paths(self, tmp_path) -> None:
        state = ConsoleState()
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("before\n")
        new.write_text("after\n")

        metadata = state.add_file_message(
            kind="diff", old_path=str(old), new_path=str(new)
        )

        assert metadata.payload.mode == "file_diff_ref"
        assert metadata.payload.old_path == str(old)
        assert metadata.payload.new_path == str(new)


@pytest.mark.unit
@pytest.mark.core
class TestHydrationRaces:
    """Body reads race clear()/eviction gracefully instead of raising."""

    def test_read_returns_none_when_body_file_vanished(self) -> None:
        from ot.console.storage import unlink_message_body

        state = ConsoleState()
        metadata = state.add_message(request=ShowRequest(kind="text", content="hello"))
        instance = state.get_or_create_instance()
        # Simulate clear()/eviction winning the race after the metadata snapshot
        unlink_message_body(message_id=metadata.id, instance_id=instance.id)

        assert state.read_message(id=metadata.id) is None

    def test_payload_view_returns_none_when_body_file_vanished(self) -> None:
        from ot.console.storage import unlink_message_body

        state = ConsoleState()
        metadata = state.add_message(request=ShowRequest(kind="text", content="hello"))
        instance = state.get_or_create_instance()
        unlink_message_body(message_id=metadata.id, instance_id=instance.id)

        assert state.payload_view(id=metadata.id) is None
