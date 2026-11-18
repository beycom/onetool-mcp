"""Owned log sinks, redaction, cap, rotation and handler cleanup."""

import json
from pathlib import Path

from onetool.config import load_config
from onetool.diagnostics import event, logging_context


def test_rotation_and_no_duplicate_handlers(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("version: 4\nservers: {}\nlogging: {level: DEBUG, file: gateway.log}\n")
    config = load_config(path)
    for _ in range(2):
        with logging_context(config) as (logger, redact):
            redact.values = ("literal-secret",)
            event(logger, "literal-secret", request_id="first")
    log = tmp_path / "gateway.log"
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 2 and all(record["event"] == "[redacted]" for record in records)
    with logging_context(config) as (logger, _):
        for _ in range(1400):
            event(logger, "x" * 7800)
    assert (tmp_path / "gateway.log.1").exists()
    assert len(list(tmp_path.glob("gateway.log*"))) <= 4
    assert all(
        len(line.encode()) <= 8192
        for item in tmp_path.glob("gateway.log*")
        for line in item.read_text().splitlines()
    )


def test_log_cap_is_valid_json_for_unicode_fields(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("version: 4\nservers: {}\nlogging: {file: gateway.log}\n")
    with logging_context(load_config(path)) as (logger, _):
        event(logger, "x" * 20000, request_id="🧿" * 2000, server="🧿" * 2000, tool="🧿" * 2000)
    line = (tmp_path / "gateway.log").read_text().strip()
    assert len(line.encode()) <= 8192
    assert json.loads(line)["event"] == "message_too_large"


def test_short_overlapping_masks_are_single_pass_idempotent_and_refresh() -> None:
    from onetool.diagnostics import Redactor

    redact = Redactor(("a", "e", "d", "[", "]", "long-secret"))
    first = redact("a long-secret")
    assert first == "[redacted] [redacted]"
    assert redact(first) == first
    redact.values = ("new-secret",)
    assert redact("new-secret") == "[redacted]"
