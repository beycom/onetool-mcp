"""Tests for the `run` MCP tool's response contract (p12 core-flow-hardening).

Covers the isError contract (D2), the load-bearing `output_schema is None` invariant
(F3), and the destructiveHint annotation.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult


async def _get_run_tool():  # noqa: ANN202
    from ot import server

    return await server.mcp.get_tool("run")


@pytest.mark.unit
@pytest.mark.serve
class TestRunToolMcpContract:
    """F3 + annotations: static invariants of the registered run tool."""

    async def test_output_schema_is_none(self) -> None:
        """F3: run must have no output schema.

        run's `-> ToolResult` return annotation is load-bearing. If it were changed
        to `-> str`/`-> dict`, FastMCP would auto-generate an output_schema; because
        run always returns structured_content=None, output-schema validation would
        then reject every call and return isError:true unconditionally. This test
        fails loudly if the annotation is ever changed.
        """
        run_tool = await _get_run_tool()
        assert run_tool.output_schema is None

    async def test_destructive_hint_is_true(self) -> None:
        """A meta-tool that can call file.delete is conservatively destructive."""
        run_tool = await _get_run_tool()
        assert run_tool.annotations is not None
        assert run_tool.annotations.destructiveHint is True


@pytest.mark.unit
@pytest.mark.serve
class TestRunToolErrorContract:
    """D2: failures surface as isError:true (raise); success returns a ToolResult."""

    async def test_preparation_failure_raises_toolerror(self) -> None:
        """A command failing preparation raises ToolError with the error text."""
        run_tool = await _get_run_tool()
        with pytest.raises(ToolError) as exc_info:
            await run_tool.fn(command="", ctx=None)
        assert "empty" in str(exc_info.value).lower()

    async def test_runtime_exception_raises_toolerror(self) -> None:
        """A command whose execution raises surfaces as ToolError, text intact."""
        run_tool = await _get_run_tool()
        with pytest.raises(ToolError) as exc_info:
            await run_tool.fn(command="{}['missing_key']", ctx=None)
        assert "KeyError" in str(exc_info.value)

    async def test_success_returns_toolresult(self) -> None:
        """A successful command returns a ToolResult (isError:false), not a raise."""
        run_tool = await _get_run_tool()
        result = await run_tool.fn(command="1 + 1", ctx=None)
        assert isinstance(result, ToolResult)
