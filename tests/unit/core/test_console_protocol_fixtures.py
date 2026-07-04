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
        ("inline-display-message.json", "display-message.schema.json"),
        ("file-ref-display-message.json", "display-message.schema.json"),
        ("file-diff-ref-display-message.json", "display-message.schema.json"),
        ("display-message-event.json", "event-envelope.schema.json"),
    ]
    for fixture_name, schema_name in cases:
        Draft202012Validator(_schema(schema_name)).validate(
            _json(FIXTURE_ROOT / "fixtures" / fixture_name)
        )
