"""Payload-free operational logging and configured-secret redaction."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from onetool.config import LoadedConfig


class Redactor:
    def __init__(self, values: tuple[str, ...]):
        self.values = values

    def __call__(self, value: str) -> str:
        for secret in self.values:
            value = value.replace(secret, "[redacted]")
        return value


class EventFormatter(logging.Formatter):
    """Only explicitly approved record fields reach a sink, with an 8 KiB cap."""

    def __init__(self, redact: Redactor):
        super().__init__()
        self.redact = redact

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "event": self.redact(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
            "server": getattr(record, "server", "-"),
            "tool": getattr(record, "tool", "-"),
            "duration": getattr(record, "duration", None),
            "outcome": getattr(record, "outcome", "-"),
            "error_category": getattr(record, "error_category", None),
        }
        text = self.redact(json.dumps(event, ensure_ascii=False))
        if len(text.encode()) > 8192:
            # Retain valid JSON even for a pathological external log record.
            event["event"] = "message_too_large"
            for key in ("request_id", "server", "tool", "outcome", "error_category"):
                event[key] = self.redact(str(event[key]))[:128]
            text = json.dumps(event, ensure_ascii=True)
        return text


@contextmanager
def logging_context(config: LoadedConfig) -> Iterator[tuple[logging.Logger, Redactor]]:
    """Own sinks once; suppress upstream payload/wire/debug traces and raw stderr."""
    redact = Redactor(config.secret_values)
    logger = logging.getLogger("onetool")
    names = ("fastmcp", "mcp", "httpx2", "httpcore2", "pydantic_monty")
    saved = [
        (item, item.level, item.propagate, item.handlers[:])
        for item in [logger, *(logging.getLogger(name) for name in names)]
    ]
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        if config.model.logging.file:
            handlers.append(
                RotatingFileHandler(
                    config.model.logging.file,
                    maxBytes=10 * 1024 * 1024,
                    backupCount=3,
                    encoding="utf-8",
                )
            )
        for item, _, _, _ in saved:
            item.handlers = []
            item.propagate = False
            item.setLevel(logging.CRITICAL + 1)
        logger.handlers = handlers
        logger.setLevel(config.model.logging.level)
        for handler in handlers:
            handler.setFormatter(EventFormatter(redact))
        yield logger, redact
    finally:
        for handler in handlers:
            handler.close()
        for item, level, propagate, original in saved:
            item.setLevel(level)
            item.propagate = propagate
            item.handlers = original


def event(logger: logging.Logger, name: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Call sites supply identifiers/categories only, never exception or payload text."""
    logger.log(level, name, extra=fields)
