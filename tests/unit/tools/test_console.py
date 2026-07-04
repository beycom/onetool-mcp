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
