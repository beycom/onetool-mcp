"""Compatibility tests for Console protocol JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

FIXTURE_ROOT = Path("tests/fixtures/console-protocol")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict[str, Any]:
    schema = _json(FIXTURE_ROOT / "schemas" / name)
    if name == "outbox-batch.schema.json":
        schema["properties"]["events"]["items"] = _schema("event-envelope.schema.json")
    return schema


@pytest.mark.unit
@pytest.mark.core
def test_vendored_console_fixtures_validate_against_schemas() -> None:
    """Vendored protocol fixtures remain JSON Schema-compatible."""
    cases = [
        ("empty-outbox-batch.json", "outbox-batch.schema.json"),
        ("outbox-batch.json", "outbox-batch.schema.json"),
        ("outbox-ack.json", "outbox-ack.schema.json"),
        ("instance-snapshot.json", "instance-snapshot.schema.json"),
        ("inline-console-message.json", "console-message.schema.json"),
        ("file-ref-console-message.json", "console-message.schema.json"),
        ("file-diff-ref-console-message.json", "console-message.schema.json"),
        ("console-message-event.json", "event-envelope.schema.json"),
    ]
    for fixture_name, schema_name in cases:
        Draft202012Validator(_schema(schema_name)).validate(
            _json(FIXTURE_ROOT / "fixtures" / fixture_name)
        )


@pytest.mark.unit
@pytest.mark.core
def test_live_emitted_outbox_batch_validates_against_shipped_schemas() -> None:
    """A batch emitted by a real `ConsoleOutboxState` matches the wire schemas.

    Exercises the actual runtime types (`ConsoleOutboxState`, `MessageMetadata`,
    `BoundedPreview`) end-to-end rather than only checking hand-authored fixture
    files, so a drift between the ported implementation and the shipped protocol
    contract fails CI here.
    """
    from datetime import UTC, datetime

    from ot.console.models import BoundedPreview, MessageMetadata, PayloadReference
    from ot.console.outbox import (
        ConsoleOutboxState,
        build_console_message_payload,
        build_instance_snapshot,
    )

    state = ConsoleOutboxState()
    state.configure_instance(instance_id="mcp-live-shape-test")
    state.append(
        event_type="instance.snapshot",
        payload=build_instance_snapshot(message_count=0, status="running"),
    )

    now = datetime.now(UTC)
    metadata = MessageMetadata(
        id="abc123def456",
        kind="text",
        metadata={"source": "unit"},
        preview_lines=1,
        created_at=now,
        updated_at=now,
        payload=PayloadReference(mode="inline", size_bytes=5),
    )
    preview = BoundedPreview(
        text="hello", truncated=False, size_bytes=5, limit_bytes=100
    )
    state.append(
        event_type="console.message.created",
        payload=build_console_message_payload(
            metadata=metadata, preview=preview, inline_payload="hello"
        ),
    )

    batch = state.poll(limit=10)

    outbox_batch_schema = _schema("outbox-batch.schema.json")
    envelope_schema = _schema("event-envelope.schema.json")
    snapshot_schema = _json(FIXTURE_ROOT / "schemas" / "instance-snapshot.schema.json")
    display_message_schema = _json(
        FIXTURE_ROOT / "schemas" / "console-message.schema.json"
    )

    Draft202012Validator(outbox_batch_schema).validate(batch)
    assert len(batch["events"]) == 2
    for event in batch["events"]:
        Draft202012Validator(envelope_schema).validate(event)
        if event["type"] == "instance.snapshot":
            Draft202012Validator(snapshot_schema).validate(event["payload"])
        elif event["type"] == "console.message.created":
            Draft202012Validator(display_message_schema).validate(event["payload"])
            assert event["payload"]["payload"]["mode"] == "inline"
