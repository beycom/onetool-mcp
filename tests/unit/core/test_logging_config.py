"""Unit tests for logging configuration."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

import pytest
from loguru import logger
from pytest import MonkeyPatch

from ot.config import get_config, reset_config
from ot.logging.config import (
    _NOISY_THIRD_PARTY_LOGGERS,
    configure_logging,
    configure_test_logging,
)
from ot.logging.entry import LogEntry

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def reset_noisy_logger_levels() -> Generator[None, None, None]:
    """Restore logger levels mutated by logging configuration tests."""
    original_levels = {
        logger_name: logging.getLogger(logger_name).level
        for logger_name in _NOISY_THIRD_PARTY_LOGGERS
    }
    yield
    for logger_name, level in original_levels.items():
        logging.getLogger(logger_name).setLevel(level)
    logger.remove()
    reset_config()


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("reset_noisy_logger_levels")
def test_configure_logging_suppresses_noisy_third_party_info(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Runtime logging suppresses known noisy dependency INFO loggers."""
    for logger_name in _NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.INFO)

    _load_tmp_config(tmp_path)
    monkeypatch.setenv("OT_LOG_DIR", str(tmp_path / "logs"))
    configure_logging(log_name="serve")

    assert logging.getLogger("pydoll").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("google_genai").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("google.genai").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("ot").getEffectiveLevel() != logging.WARNING


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("reset_noisy_logger_levels")
def test_configure_test_logging_suppresses_same_third_party_info(
    tmp_path: Path,
) -> None:
    """Test logging uses the same third-party suppression list as runtime logging."""
    for logger_name in _NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.INFO)

    _load_tmp_config(tmp_path)
    configure_test_logging("test_logging_config", dev_output=False)

    assert all(
        logging.getLogger(logger_name).getEffectiveLevel() == logging.WARNING
        for logger_name in _NOISY_THIRD_PARTY_LOGGERS
    )


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("reset_noisy_logger_levels")
def test_configure_logging_adds_stable_mcp_identity_to_dev_lines(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Runtime dev logs include the same mcpId and pid on every line."""
    log_dir = tmp_path / "logs"
    _load_tmp_config(tmp_path)
    monkeypatch.setenv("OT_LOG_DIR", str(log_dir))
    configure_logging(log_name="serve")

    logger.info(LogEntry(event="test.first").success())
    logger.info(LogEntry(event="test.second").success())

    lines = (log_dir / "serve.log").read_text().splitlines()
    assert len(lines) == 2
    assert all(f"pid={os.getpid()}" in line for line in lines)

    mcp_ids = [re.search(r"mcpId=(\d{8}-[0-9a-f]{8})", line) for line in lines]
    assert all(match is not None for match in mcp_ids)
    assert mcp_ids[0].group(1) == mcp_ids[1].group(1)  # type: ignore[union-attr]


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("reset_noisy_logger_levels")
def test_configure_test_logging_adds_runtime_identity_to_json_records(
    tmp_path: Path,
) -> None:
    """Serialized test logs include MCP process identity."""
    _load_tmp_config(tmp_path)
    configure_test_logging("test_logging_config", dev_output=False)

    logger.info(LogEntry(event="test.identity").success())

    log_file = tmp_path / ".onetool" / "runtime" / "logs" / "test_logging_config.log"
    line = log_file.read_text().splitlines()[-1]
    record = json.loads(line)
    assert re.fullmatch(r"\d{8}-[0-9a-f]{8}", record["mcpId"])
    assert record["pid"] == os.getpid()
    assert record["event"] == "test.identity"


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("reset_noisy_logger_levels")
def test_runtime_identity_cannot_be_overridden_by_bound_extra(
    tmp_path: Path,
) -> None:
    """Runtime identity fields are authoritative even when callers bind same keys."""
    _load_tmp_config(tmp_path)
    configure_test_logging("test_logging_config", dev_output=False)

    logger.bind(mcpId="spoofed", pid=0).info(LogEntry(event="test.identity"))

    log_file = tmp_path / ".onetool" / "runtime" / "logs" / "test_logging_config.log"
    record = json.loads(log_file.read_text().splitlines()[-1])
    assert record["mcpId"] != "spoofed"
    assert re.fullmatch(r"\d{8}-[0-9a-f]{8}", record["mcpId"])
    assert record["pid"] == os.getpid()


def _load_tmp_config(tmp_path: Path) -> None:
    """Load a minimal config rooted under tmp_path."""
    reset_config()
    config_dir = tmp_path / ".onetool"
    config_dir.mkdir()
    config_path = config_dir / "onetool.yaml"
    config_path.write_text("version: 2\n")
    get_config(config_path=config_path, reload=True)
