"""Compatibility tests for Console protocol JSON fixtures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ot.console_outbox import build_display_payload, build_instance_snapshot
from ot.display.models import BoundedPreview, MessageMetadata, PayloadReference

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
        ("inline-display-message.json", "display-message.schema.json"),
        ("file-ref-display-message.json", "display-message.schema.json"),
        ("file-diff-ref-display-message.json", "display-message.schema.json"),
        ("display-message-event.json", "event-envelope.schema.json"),
    ]
    for fixture_name, schema_name in cases:
        Draft202012Validator(_schema(schema_name)).validate(
            _json(FIXTURE_ROOT / "fixtures" / fixture_name)
        )


@pytest.mark.unit
@pytest.mark.core
def test_current_mcp_display_payload_validates_against_console_schema() -> None:
    """Current Python event payloads validate against the Console contract."""
    metadata = MessageMetadata(
        id="abc123def456",
        kind="text",
        metadata={"title": "Run"},
        preview_lines=1,
        created_at=datetime(2026, 6, 7, tzinfo=UTC),
        updated_at=datetime(2026, 6, 7, tzinfo=UTC),
        payload=PayloadReference(mode="inline", size_bytes=5),
    )
    payload = build_display_payload(
        metadata=metadata,
        preview=BoundedPreview(text="hello", truncated=False, size_bytes=5, limit_bytes=65536),
        inline_payload="hello",
    )

    Draft202012Validator(_schema("display-message.schema.json")).validate(payload)


@pytest.mark.unit
@pytest.mark.core
def test_current_mcp_instance_snapshot_validates_against_console_schema() -> None:
    """Current Python instance snapshots validate against the Console contract."""
    payload = build_instance_snapshot(message_count=0, status="running")

    Draft202012Validator(_schema("instance-snapshot.schema.json")).validate(payload)
