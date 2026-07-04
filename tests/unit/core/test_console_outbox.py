"""Tests for the MCP-owned Console outbox state and protocol helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from jsonschema import Draft202012Validator

if TYPE_CHECKING:
    from collections.abc import Iterator

from ot.console.models import BoundedPreview, MessageMetadata, PayloadReference
from ot.console.outbox import (
    PROTOCOL,
    PROTOCOL_VERSION,
    ConsoleOutboxState,
    ack_outbox,
    build_console_message_payload,
    build_instance_snapshot,
    ensure_instance_snapshot,
    poll_outbox,
)
from ot.console.outbox import STATE as GLOBAL_STATE


def _reset_global_state() -> None:
    GLOBAL_STATE.instance_id = None
    GLOBAL_STATE.sequence = 0
    GLOBAL_STATE.acked_through = 0
    GLOBAL_STATE.entries.clear()
    GLOBAL_STATE._last_snapshot = None


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Isolate the module-level Console outbox singleton across tests."""
    _reset_global_state()
    yield
    _reset_global_state()


def _make_metadata(message_id: str = "abc123def456") -> MessageMetadata:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return MessageMetadata(
        id=message_id,
        kind="text",
        metadata={"source": "unit"},
        preview_lines=1,
        created_at=now,
        updated_at=now,
        payload=PayloadReference(mode="inline", size_bytes=5),
    )


@pytest.mark.unit
@pytest.mark.core
class TestConsoleOutboxState:
    """Sequence, ack, retention, and instance-reset semantics."""

    def test_append_assigns_monotonic_sequence(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")

        first = state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})
        second = state.append(
            event_type="instance.snapshot", payload={"id": "mcp-test"}
        )

        assert first["sequence"] == 1
        assert second["sequence"] == 2
        assert first["protocol"] == PROTOCOL
        assert first["protocol_version"] == PROTOCOL_VERSION

    def test_poll_does_not_mutate_retained_events(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})

        first_batch = state.poll(limit=10)
        second_batch = state.poll(limit=10)

        assert first_batch["events"] == second_batch["events"]
        assert len(first_batch["events"]) == 1

    def test_at_least_once_delivery_without_ack(self) -> None:
        """Unacknowledged events remain eligible for later polls."""
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})
        state.append(event_type="console.message.created", payload={"id": "m1"})

        batch = state.poll(limit=1)
        assert len(batch["events"]) == 1
        assert batch["has_more"] is True

        # Polling again without acking returns the same first event.
        replay = state.poll(limit=1)
        assert replay["events"] == batch["events"]

    def test_ack_advances_cursor_and_drops_entries(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})
        state.append(event_type="console.message.created", payload={"id": "m1"})

        batch = state.poll(limit=10)
        ack_result = state.ack(
            acked_through=batch["next_cursor"],
            instance_id="mcp-test",
        )

        assert ack_result["acked_through"] == batch["next_cursor"]
        assert ack_result["retained"] == 0
        assert len(state.entries) == 0

        next_batch = state.poll(limit=10)
        assert next_batch["events"] == []
        assert next_batch["cursor"] == batch["next_cursor"]

    def test_ack_rejects_mismatched_instance(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})

        with pytest.raises(ValueError, match="does not match"):
            state.ack(acked_through=1, instance_id="mcp-other")

    def test_configure_instance_reset_on_id_change(self) -> None:
        """Re-configuring with a different instance id resets sequence/ack/entries."""
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-first")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-first"})
        state.ack(acked_through=1, instance_id="mcp-first")

        state.configure_instance(instance_id="mcp-second")

        assert state.instance_id == "mcp-second"
        assert state.sequence == 0
        assert state.acked_through == 0
        assert len(state.entries) == 0

    def test_configure_instance_same_id_is_noop(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})

        state.configure_instance(instance_id="mcp-test")

        assert state.sequence == 1
        assert len(state.entries) == 1

    def test_retention_bound_drops_oldest_unacked_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ot.console.outbox._retention_limit", lambda: 3)
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")

        for index in range(5):
            state.append(
                event_type="console.message.created", payload={"id": f"m{index}"}
            )

        assert len(state.entries) == 3
        remaining_ids = [entry.event["payload"]["id"] for entry in state.entries]
        assert remaining_ids == ["m2", "m3", "m4"]

    def test_poll_reports_oldest_retained_for_gap_detection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After retention evicts unacked events, `oldest_retained` reveals the gap.

        A fresh consumer polls with cursor 0, expecting sequence 1 next. Because
        bounded retention dropped sequences 1 and 2 before any acknowledgement,
        `oldest_retained` is 3 (> cursor + 1), so the consumer can detect that
        events 1 and 2 were lost.
        """
        monkeypatch.setattr("ot.console.outbox._retention_limit", lambda: 3)
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")

        for index in range(5):
            state.append(
                event_type="console.message.created", payload={"id": f"m{index}"}
            )

        batch = state.poll(limit=10)
        assert batch["cursor"] == 0
        assert batch["oldest_retained"] == 3
        # Consumer expected cursor + 1 == 1 next; oldest_retained > cursor + 1
        # signals that sequences 1 and 2 were evicted before acknowledgement.
        assert batch["oldest_retained"] > batch["cursor"] + 1

    def test_poll_empty_outbox_reports_oldest_retained_as_acked_through(self) -> None:
        """With no retained entries, `oldest_retained` equals `acked_through`."""
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "mcp-test"})
        batch = state.poll(limit=10)
        state.ack(acked_through=batch["next_cursor"], instance_id="mcp-test")

        empty = state.poll(limit=10)
        assert empty["events"] == []
        assert empty["oldest_retained"] == state.acked_through
        # No gap: oldest_retained == cursor, not greater than cursor + 1.
        assert empty["oldest_retained"] == empty["cursor"]

    def test_append_requires_configured_instance(self) -> None:
        state = ConsoleOutboxState()

        with pytest.raises(RuntimeError, match="not configured"):
            state.append(event_type="instance.snapshot", payload={})

    def test_note_snapshot_returns_false_for_unchanged_fingerprint(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")

        assert state.note_snapshot(status="running", message_count=0) is True
        assert state.note_snapshot(status="running", message_count=0) is False
        assert state.note_snapshot(status="running", message_count=0) is False

    def test_note_snapshot_returns_true_on_message_count_change(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.note_snapshot(status="running", message_count=0)

        assert state.note_snapshot(status="running", message_count=1) is True

    def test_note_snapshot_returns_true_on_status_change(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.note_snapshot(status="running", message_count=0)

        assert state.note_snapshot(status="stopped", message_count=0) is True

    def test_note_snapshot_resets_on_instance_change(self) -> None:
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-first")
        state.note_snapshot(status="running", message_count=0)

        state.configure_instance(instance_id="mcp-second")

        assert state.note_snapshot(status="running", message_count=0) is True

    def test_drop_message_only_removes_console_message_created_events(self) -> None:
        """A snapshot payload with a coincidentally-matching id must survive."""
        state = ConsoleOutboxState()
        state.configure_instance(instance_id="mcp-test")
        state.append(event_type="instance.snapshot", payload={"id": "m1"})
        state.append(event_type="console.message.created", payload={"id": "m1"})

        state.drop_message(message_id="m1")

        remaining_types = [entry.event["type"] for entry in state.entries]
        assert remaining_types == ["instance.snapshot"]


@pytest.mark.unit
@pytest.mark.core
class TestConsoleOutboxModuleHelpers:
    """Module-level publish/poll/ack helpers over the global singleton."""

    def test_ensure_instance_snapshot_appends_event(self) -> None:
        ensure_instance_snapshot(message_count=0)

        batch = poll_outbox(limit=10)
        assert batch["events"][0]["type"] == "instance.snapshot"
        assert batch["events"][0]["payload"]["message_count"] == 0

    def test_ensure_instance_snapshot_is_idempotent_for_unchanged_state(self) -> None:
        """Repeated calls with the same status/message_count emit exactly one event."""
        ensure_instance_snapshot(message_count=2)
        ensure_instance_snapshot(message_count=2)
        ensure_instance_snapshot(message_count=2)

        batch = poll_outbox(limit=10)
        snapshots = [e for e in batch["events"] if e["type"] == "instance.snapshot"]
        assert len(snapshots) == 1

    def test_ensure_instance_snapshot_emits_new_snapshot_on_message_count_change(
        self,
    ) -> None:
        ensure_instance_snapshot(message_count=0)
        ensure_instance_snapshot(message_count=1)

        batch = poll_outbox(limit=10)
        snapshots = [e for e in batch["events"] if e["type"] == "instance.snapshot"]
        assert len(snapshots) == 2

    def test_ensure_instance_snapshot_reemits_after_instance_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ot.console.outbox._runtime_instance_id", lambda: "mcp-a")
        ensure_instance_snapshot(message_count=0)

        monkeypatch.setattr("ot.console.outbox._runtime_instance_id", lambda: "mcp-b")
        ensure_instance_snapshot(message_count=0)

        batch = poll_outbox(limit=10)
        snapshots = [e for e in batch["events"] if e["type"] == "instance.snapshot"]
        assert len(snapshots) == 1
        assert batch["instance_id"] == "mcp-b"

    def test_ack_outbox_validates_protocol_identity(self) -> None:
        ensure_instance_snapshot(message_count=0)
        batch = poll_outbox(limit=10)

        with pytest.raises(ValueError, match="unsupported Console protocol"):
            ack_outbox(payload={"protocol": "other", "protocol_version": 1})

        result = ack_outbox(
            payload={
                "protocol": PROTOCOL,
                "protocol_version": PROTOCOL_VERSION,
                "instance_id": batch["instance_id"],
                "acked_through": batch["next_cursor"],
            }
        )
        assert result["acked_through"] == batch["next_cursor"]

    def test_build_instance_snapshot_matches_schema_shape(self) -> None:
        snapshot = build_instance_snapshot(message_count=3, status="running")

        assert snapshot["message_count"] == 3
        assert snapshot["status"] == "running"
        assert isinstance(snapshot["allowed_roots"], list)
        assert snapshot["allowed_roots"]
        assert snapshot["repo_root"]

    def test_build_console_message_payload_is_inline_only(self) -> None:
        metadata = _make_metadata()
        preview = BoundedPreview(
            text="hello", truncated=False, size_bytes=5, limit_bytes=100
        )

        payload = build_console_message_payload(
            metadata=metadata, preview=preview, inline_payload="hello"
        )

        assert payload["payload"]["mode"] == "inline"
        assert payload["payload"]["content"] == "hello"
        assert payload["preview"]["text"] == "hello"


@pytest.mark.unit
@pytest.mark.core
def test_emitted_events_validate_against_shipped_schemas() -> None:
    """Instance snapshot and display message events match the shipped wire schemas."""
    import json
    from pathlib import Path

    schema_root = Path("tests/fixtures/console-protocol/schemas")

    def _schema(name: str) -> dict:
        return json.loads((schema_root / name).read_text(encoding="utf-8"))

    envelope_schema = _schema("event-envelope.schema.json")
    snapshot_schema = _schema("instance-snapshot.schema.json")
    display_schema = _schema("console-message.schema.json")

    ensure_instance_snapshot(message_count=0)
    metadata = _make_metadata()
    preview = BoundedPreview(
        text="hello", truncated=False, size_bytes=5, limit_bytes=100
    )
    from ot.console.outbox import publish_console_message

    publish_console_message(metadata=metadata, preview=preview, inline_payload="hello")

    batch = poll_outbox(limit=10)
    for event in batch["events"]:
        Draft202012Validator(envelope_schema).validate(event)
        if event["type"] == "instance.snapshot":
            Draft202012Validator(snapshot_schema).validate(event["payload"])
        elif event["type"] == "console.message.created":
            Draft202012Validator(display_schema).validate(event["payload"])


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)


@pytest.mark.unit
@pytest.mark.core
class TestFileRefWirePayload:
    """File-reference wire payloads follow the protocol payload variants."""

    def test_file_ref_payload_has_path_and_no_content(self) -> None:
        metadata = MessageMetadata(
            id="a" * 12,
            kind="code",
            metadata={},
            created_at=_utcnow(),
            updated_at=_utcnow(),
            payload=PayloadReference(
                mode="file_ref",
                size_bytes=10,
                language="python",
                path="/repo/src/app.py",
            ),
        )

        payload = build_console_message_payload(
            metadata=metadata, preview=None, inline_payload=None
        )

        assert payload["payload"]["mode"] == "file_ref"
        assert payload["payload"]["path"] == "/repo/src/app.py"
        assert "content" not in payload["payload"]

    def test_file_diff_ref_payload_has_old_and_new_paths(self) -> None:
        metadata = MessageMetadata(
            id="b" * 12,
            kind="diff",
            metadata={},
            created_at=_utcnow(),
            updated_at=_utcnow(),
            payload=PayloadReference(
                mode="file_diff_ref",
                size_bytes=10,
                old_path="/repo/a.py",
                new_path="/repo/b.py",
            ),
        )

        payload = build_console_message_payload(
            metadata=metadata, preview=None, inline_payload=None
        )

        assert payload["payload"]["mode"] == "file_diff_ref"
        assert payload["payload"]["old_path"] == "/repo/a.py"
        assert payload["payload"]["new_path"] == "/repo/b.py"
        assert "content" not in payload["payload"]


@pytest.mark.unit
@pytest.mark.core
class TestSnapshotRoots:
    """Instance snapshots publish real, resolved allowed roots."""

    def test_snapshot_roots_include_cwd_and_are_resolved(self) -> None:
        snapshot = build_instance_snapshot(message_count=0, status="running")

        from ot.paths import get_effective_cwd

        roots = snapshot["allowed_roots"]
        assert str(get_effective_cwd().resolve()) in roots
        assert all(root.startswith("/") for root in roots)
        assert len(roots) == len(set(roots))
