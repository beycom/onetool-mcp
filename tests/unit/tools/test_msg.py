"""Unit tests for msg tool.

Tests ot.push() topic routing and message formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from ot.config.loader import OneToolConfig


@pytest.fixture
def msg_config() -> OneToolConfig:
    """Create a config with msg topics for testing."""
    from ot.config.loader import (
        MsgConfig,
        MsgTopicConfig,
        OneToolConfig,
        ToolsConfig,
    )

    return OneToolConfig(
        tools=ToolsConfig(
            msg=MsgConfig(
                topics=[
                    MsgTopicConfig(pattern="status:*", file="/tmp/msg/status.yaml"),
                    MsgTopicConfig(pattern="doc:*", file="/tmp/msg/docs.yaml"),
                    MsgTopicConfig(pattern="*", file="/tmp/msg/default.yaml"),
                ]
            )
        )
    )


@pytest.fixture
def empty_msg_config() -> OneToolConfig:
    """Create a config with no msg topics."""
    from ot.config.loader import MsgConfig, OneToolConfig, ToolsConfig

    return OneToolConfig(tools=ToolsConfig(msg=MsgConfig(topics=[])))


@pytest.mark.unit
@pytest.mark.serve
def test_push_returns_ok_with_matching_topic(msg_config: OneToolConfig) -> None:
    """Verify push() returns OK with file path for matching topic."""
    from ot_tools.internal import push

    with (
        patch("ot_tools.internal.get_config", return_value=msg_config),
        patch("ot_tools.internal._write_to_file"),
    ):
        result = push(topic="status:scan", message="Scanning src/")

    assert result.startswith("OK: status:scan ->")
    assert "/tmp/msg/status.yaml" in result


@pytest.mark.unit
@pytest.mark.serve
def test_push_returns_ok_no_match_when_no_pattern_matches(
    empty_msg_config: OneToolConfig,
) -> None:
    """Verify push() returns 'OK: no matching topic' when no pattern matches."""
    from ot_tools.internal import push

    with patch("ot_tools.internal.get_config", return_value=empty_msg_config):
        result = push(topic="unknown:topic", message="test")

    assert result == "OK: no matching topic"


@pytest.mark.unit
@pytest.mark.serve
def test_push_uses_first_matching_pattern(msg_config: OneToolConfig) -> None:
    """Verify push() uses first matching pattern (status:* before *)."""
    from ot_tools.internal import push

    with (
        patch("ot_tools.internal.get_config", return_value=msg_config),
        patch("ot_tools.internal._write_to_file"),
    ):
        # status:scan should match status:* not *
        result = push(topic="status:scan", message="test")

    assert "status.yaml" in result
    assert "default.yaml" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_push_falls_through_to_catchall(msg_config: OneToolConfig) -> None:
    """Verify push() falls through to catchall pattern."""
    from ot_tools.internal import push

    with (
        patch("ot_tools.internal.get_config", return_value=msg_config),
        patch("ot_tools.internal._write_to_file"),
    ):
        # other:topic should match * catchall
        result = push(topic="other:topic", message="test")

    assert "default.yaml" in result


@pytest.mark.unit
@pytest.mark.serve
def test_match_topic_to_file_returns_none_for_no_match(
    empty_msg_config: OneToolConfig,
) -> None:
    """Verify _match_topic_to_file returns None when no pattern matches."""
    from ot_tools.internal import _match_topic_to_file

    with patch("ot_tools.internal.get_config", return_value=empty_msg_config):
        result = _match_topic_to_file("any:topic")

    assert result is None


@pytest.mark.unit
@pytest.mark.serve
def test_match_topic_to_file_returns_path_for_match(
    msg_config: OneToolConfig,
) -> None:
    """Verify _match_topic_to_file returns Path for matching pattern."""
    from ot_tools.internal import _match_topic_to_file

    with patch("ot_tools.internal.get_config", return_value=msg_config):
        result = _match_topic_to_file("doc:api")

    assert result is not None
    assert isinstance(result, Path)
    assert "docs.yaml" in str(result)


@pytest.mark.unit
@pytest.mark.serve
def test_resolve_path_expands_home() -> None:
    """Verify _resolve_path expands ~ to home directory."""
    from ot_tools.internal import _resolve_path

    result = _resolve_path("~/test/file.yaml")

    assert result.is_absolute()
    assert "~" not in str(result)
    assert "test/file.yaml" in str(result)


@pytest.mark.unit
@pytest.mark.serve
def test_resolve_path_preserves_absolute() -> None:
    """Verify _resolve_path preserves absolute paths."""
    from ot_tools.internal import _resolve_path

    result = _resolve_path("/absolute/path/file.yaml")

    assert str(result) == "/absolute/path/file.yaml"
