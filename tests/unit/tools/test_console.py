"""Unit tests for the console pack (inline-only Console message store).

Covers: show/list/read/clear round-trip, inline truncation, retention bound,
no-consumer-required behavior, and pack discovery through execute_command.
"""

from __future__ import annotations

import re

import pytest

from ot.console.state import PREVIEW_LIMIT_BYTES, ConsoleState
from ottools import console


@pytest.fixture(autouse=True)
def _isolated_console_state(monkeypatch: pytest.MonkeyPatch) -> ConsoleState:
    """Give each test a fresh, isolated ConsoleState bound to the console pack.

    Without this, all tests would share the process-wide ``ot.console.state.STATE``
    singleton and leak retained messages across tests.
    """
    state = ConsoleState()
    monkeypatch.setattr(console, "STATE", state)
    return state


@pytest.mark.unit
@pytest.mark.tools
class TestConsoleTools:
    """Test public console tool functions."""

    def test_show_read_list_round_trip(self) -> None:
        created = console.show(
            kind="text",
            content="tool payload",
            metadata={"title": "Tool", "source": "unit"},
        )

        read = console.read(id=created["id"])
        page = console.list(limit=10, source="unit")

        assert created["kind"] == "text"
        assert created["payload"]["mode"] == "inline"
        assert isinstance(read, dict)
        assert read["metadata"]["id"] == created["id"]
        assert read["metadata"]["metadata"]["title"] == "Tool"
        assert read["preview"]["text"] == "tool payload"
        assert read["content"] == "tool payload"
        assert any(item["id"] == created["id"] for item in page["items"])

    def test_show_accepts_dict_and_list_content(self) -> None:
        dict_created = console.show(kind="json", content={"ok": True})
        list_created = console.show(kind="table", content=[{"row": 1}, {"row": 2}])

        dict_read = console.read(id=dict_created["id"])
        list_read = console.read(id=list_created["id"])

        assert isinstance(dict_read, dict)
        assert dict_read["content"] == {"ok": True}
        assert isinstance(list_read, dict)
        assert list_read["content"] == [{"row": 1}, {"row": 2}]

    def test_clear_removes_current_messages_and_returns_count(self) -> None:
        console.show(kind="text", content="first", metadata={"source": "clear-test"})
        console.show(kind="text", content="second", metadata={"source": "clear-test"})

        result = console.clear()

        assert result["cleared"] == 2
        assert result["message_count"] == 0
        assert console.list(limit=10)["total"] == 0

    def test_clear_makes_prior_messages_unreadable(self) -> None:
        created = console.show(kind="text", content="first")

        console.clear()

        assert (
            console.read(id=created["id"])
            == f"Error: console message not found: {created['id']}"
        )

    @pytest.mark.parametrize(
        ("limit", "offset", "match"),
        [
            (0, 0, "limit must be between 1 and 500"),
            (501, 0, "limit must be between 1 and 500"),
            (1, -1, "offset must be greater than or equal to 0"),
        ],
    )
    def test_list_rejects_invalid_pagination(
        self, limit: int, offset: int, match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            console.list(limit=limit, offset=offset)

    def test_unknown_read_returns_error(self) -> None:
        result = console.read(id="missing")

        assert result == "Error: console message not found: missing"

    def test_show_rejects_removed_file_params(self) -> None:
        with pytest.raises(TypeError):
            console.show(kind="text", content="x", path="a.txt")  # type: ignore[call-arg]

    def test_show_truncates_oversized_string_content_without_erroring(self) -> None:
        oversized = "x" * (PREVIEW_LIMIT_BYTES + 10)

        created = console.show(kind="text", content=oversized)
        read_result = console.read(id=created["id"])

        assert isinstance(read_result, dict)
        assert read_result["content"] == "x" * PREVIEW_LIMIT_BYTES
        assert read_result["preview"]["truncated"] is True

    def test_retention_bound_drops_oldest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = ConsoleState(max_records=3)
        monkeypatch.setattr(console, "STATE", state)

        ids = [
            console.show(kind="text", content=f"message {index}")["id"]
            for index in range(5)
        ]

        page = console.list(limit=10)

        assert page["total"] == 3
        assert [item["id"] for item in page["items"]] == ids[-3:]
        assert console.read(id=ids[0]) == f"Error: console message not found: {ids[0]}"

    def test_show_succeeds_without_any_consumer_polling(self) -> None:
        # No outbox poll has ever happened for this instance; show must still
        # succeed promptly and never require Console availability.
        result = console.show(kind="text", content="no consumer yet")

        assert re.fullmatch(r"[0-9a-f]{12}", result["id"]) is not None
        assert console.list(limit=10)["total"] == 1


@pytest.mark.unit
@pytest.mark.serve
class TestConsolePackDiscovery:
    """Confirm the console pack is discovered and executable end-to-end."""

    def test_console_pack_registered(self) -> None:
        from ot.executor.tool_loader import load_tool_registry

        registry = load_tool_registry()

        assert "console" in registry.packs

    @pytest.mark.asyncio
    async def test_console_show_executes_through_execute_command(self) -> None:
        from ot.executor.runner import execute_command

        result = await execute_command(
            "console.show(kind='text', content='hello from execute_command')"
        )

        assert result.success is True


@pytest.mark.unit
@pytest.mark.tools
class TestConsoleDisplay:
    """Test console.display: inference, receipts, path refs, fallbacks."""

    @pytest.fixture(autouse=True)
    def _transport_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Treat the direct host as enabled so receipts are returned.

        `direct.host.enabled` defaults to false, in which case `display`
        degrades to returning the bounded preview (covered explicitly by
        `test_direct_host_disabled_returns_bounded_preview`).
        """
        monkeypatch.setattr(console, "_transport_disabled", lambda: False)

    def test_uniform_records_infer_table_with_digest_receipt(self) -> None:
        rows = [
            {"title": f"Result {i}", "url": f"https://x/{i}", "snippet": "s"}
            for i in range(20)
        ]

        receipt = console.display(rows)

        assert receipt.startswith("console[")
        assert " table: 20 items (title, url, snippet)" in receipt
        assert '"Result 0"' in receipt
        assert len(receipt) <= console.RECEIPT_MAX_CHARS
        assert "\n" not in receipt

    def test_receipt_id_round_trips_through_read(self) -> None:
        receipt = console.display({"alpha": 1, "beta": 2})

        message_id = receipt.split("]")[0].removeprefix("console[")
        read = console.read(id=message_id)

        assert isinstance(read, dict)
        assert read["metadata"]["kind"] == "json"
        assert read["content"] == {"alpha": 1, "beta": 2}

    def test_string_inference_markdown_versus_text(self) -> None:
        markdown_receipt = console.display("# Title\n\nBody text")
        text_receipt = console.display("plain line of output")

        assert " markdown: " in markdown_receipt
        assert " text: " in text_receipt

    def test_explicit_kind_overrides_inference(self) -> None:
        receipt = console.display({"a": 1}, kind="yaml")

        assert " yaml: " in receipt

    def test_rejects_multiple_or_missing_input_forms(self) -> None:
        with pytest.raises(ValueError, match="exactly one input form"):
            console.display("value", path="/tmp/x")
        with pytest.raises(ValueError, match="exactly one input form"):
            console.display()
        with pytest.raises(ValueError, match="old_path and new_path"):
            console.display(old_path="/tmp/only-old")

    def test_in_root_path_publishes_file_ref(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "example.py"
        target.write_text("x = 1\n")
        monkeypatch.setattr(
            "ot.console.outbox.current_allowed_roots", lambda: [tmp_path.resolve()]
        )

        receipt = console.display(path=str(target))

        message_id = receipt.split("]")[0].removeprefix("console[")
        read = console.read(id=message_id)
        assert isinstance(read, dict)
        assert read["metadata"]["payload"]["mode"] == "file_ref"
        assert read["metadata"]["payload"]["language"] == "python"
        assert read["metadata"]["kind"] == "code"
        assert read["preview"]["text"] == "x = 1\n"
        assert " code: " in receipt
        assert "example.py" in receipt

    def test_image_extension_infers_image_kind(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "diagram.svg"
        target.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
        monkeypatch.setattr(
            "ot.console.outbox.current_allowed_roots", lambda: [tmp_path.resolve()]
        )

        receipt = console.display(path=str(target))

        message_id = receipt.split("]")[0].removeprefix("console[")
        read = console.read(id=message_id)
        assert isinstance(read, dict)
        assert read["metadata"]["kind"] == "image"
        assert read["metadata"]["payload"]["mode"] == "file_ref"
        assert read["metadata"]["payload"]["mime_type"] == "image/svg+xml"

    def test_outside_root_textual_path_falls_back_inline(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "notes.txt"
        target.write_text("outside the roots\n")
        other_root = tmp_path / "roots-elsewhere"
        other_root.mkdir()
        monkeypatch.setattr(
            "ot.console.outbox.current_allowed_roots",
            lambda: [other_root.resolve()],
        )

        receipt = console.display(path=str(target))

        message_id = receipt.split("]")[0].removeprefix("console[")
        read = console.read(id=message_id)
        assert isinstance(read, dict)
        assert read["metadata"]["payload"]["mode"] == "inline"
        assert read["metadata"]["metadata"]["fallback"] == "outside-allowed-roots"
        assert read["content"] == "outside the roots\n"
        assert "outside allowed roots" in receipt

    def test_missing_file_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="file not found"):
            console.display(path="/nonexistent/never/file.py")

    def test_relative_path_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must be absolute"):
            console.display(path="relative/file.py")

    def test_in_root_diff_paths_publish_file_diff_ref(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old = tmp_path / "old.py"
        new = tmp_path / "new.py"
        old.write_text("x = 1\n")
        new.write_text("x = 2\n")
        monkeypatch.setattr(
            "ot.console.outbox.current_allowed_roots", lambda: [tmp_path.resolve()]
        )

        receipt = console.display(old_path=str(old), new_path=str(new))

        message_id = receipt.split("]")[0].removeprefix("console[")
        read = console.read(id=message_id)
        assert isinstance(read, dict)
        assert read["metadata"]["payload"]["mode"] == "file_diff_ref"
        assert read["metadata"]["kind"] == "diff"
        assert read["metadata"]["payload"]["old_path"].endswith("old.py")
        assert read["metadata"]["payload"]["new_path"].endswith("new.py")

    def test_direct_host_disabled_returns_bounded_preview(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(console, "_transport_disabled", lambda: True)

        result = console.display("content the human should still get")

        assert result.startswith("console disabled")
        assert "content the human should still get" in result
