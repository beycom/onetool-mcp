"""Regression tests for MCP wire-format error propagation.

The `run` MCP tool wraps results from `execute_command` in a `ToolResult`.
When the underlying Python execution fails (success=False), the wire result
must carry `isError: true` so MCP clients (Claude Code, etc.) recognise the
failure as a tool error instead of treating it as success content.

This guards against the bug class flagged in
https://composio.dev/blog/mcp-security-vulnerabilities where error strings
were returned in `content` while `isError` stayed false, causing LLMs to
ignore the failure.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_run_returns_toolresult_with_is_error_false_on_success() -> None:
    """A successful execution must produce is_error=False (default)."""
    from ot.executor.runner import CommandResult
    from ot.server import run

    ok_result = CommandResult(
        command="print('hi')",
        result="hi",
        success=True,
        error_type=None,
        should_sanitize=True,
        format="text",
    )

    with patch("ot.server.execute_command", return_value=ok_result), \
         patch("ot.server.prepare_command") as prep, \
         patch("ot.server._stats_writer", None), \
         patch("ot.server.get_client_name", return_value="test"):
        prep.return_value.error = None
        prep.return_value.code = "print('hi')"

        tool_result = asyncio.run(run(command="print('hi')", ctx=None))

    assert tool_result.is_error is False


@pytest.mark.unit
@pytest.mark.serve
def test_run_returns_toolresult_with_is_error_true_on_failure() -> None:
    """A failed execution must produce is_error=True so the wire CallToolResult
    carries isError=true and the LLM treats it as a tool failure."""
    from ot.executor.runner import CommandResult
    from ot.server import run

    fail_result = CommandResult(
        command="ground.search(query='x')",
        result="ValueError: invalid tools.ground configuration",
        success=False,
        error_type="ValueError",
        should_sanitize=True,
        format="text",
    )

    with patch("ot.server.execute_command", return_value=fail_result), \
         patch("ot.server.prepare_command") as prep, \
         patch("ot.server._stats_writer", None), \
         patch("ot.server.get_client_name", return_value="test"):
        prep.return_value.error = None
        prep.return_value.code = "ground.search(query='x')"

        tool_result = asyncio.run(run(command="ground.search(query='x')", ctx=None))

    assert tool_result.is_error is True
    # The error message is preserved in content for the LLM to read.
    assert tool_result.content is not None
    text_blocks = [
        b for b in tool_result.content if getattr(b, "type", None) == "text"
    ]
    assert text_blocks, "expected a text content block carrying the error"
    assert "ValueError" in text_blocks[0].text
