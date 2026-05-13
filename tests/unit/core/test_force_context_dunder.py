"""Unit tests for the __force_context__ dunder variable in the runner.

Tests that execute_command correctly reads __force_context__ from the namespace
and forces ctx storage regardless of output size.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(max_inline_size: int = 5000, compact: bool = False) -> MagicMock:
    """Build a minimal mock config for runner tests."""
    cfg = MagicMock()
    cfg.output.max_inline_size = max_inline_size
    cfg.output.compact = compact
    cfg.security.sanitize.enabled = False
    return cfg


def _fake_ctx_write(content: str, *, source: str = "", verbose: bool = False, **_) -> dict:
    del source, verbose
    return {
        "handle": "abcd1234",
        "total_lines": content.count("\n") + 1,
        "size_bytes": len(content.encode()),
        "content_type": "text",
        "preview": content[:200],
        "status": "ready",
    }


def _make_capture_writer() -> tuple:
    """Return (side_effect_fn, calls_list) for asserting ctx_write invocations."""
    calls: list[str] = []

    def _capture(content: str, *, source: str = "", verbose: bool = False, **_) -> dict:
        calls.append(content)
        return _fake_ctx_write(content, source=source, verbose=verbose)

    return _capture, calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestForceContextDunder:
    """Tests for __force_context__ dunder integration in execute_command."""

    def test_force_context_true_stores_small_output(self):
        """4.1 — __force_context__ = True on small output → ctx stored, handle returned."""
        cfg = _make_config(max_inline_size=5000)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
        ):
            mock_pm.return_value.servers = {}
            _capture_write, ctx_write_calls = _make_capture_writer()

            with patch("ot.ctx.write.ctx_write", side_effect=_capture_write):
                from ot.executor.runner import execute_command

                result = asyncio.run(execute_command('__force_context__ = True\n"tiny output"'))

        assert result.success, f"Command failed: {result.result}"
        assert len(ctx_write_calls) == 1, "ctx_write should have been called once"
        parsed = json.loads(result.result)
        assert "handle" in parsed, f"Expected handle summary, got: {result.result}"

    def test_force_context_false_small_output_stays_inline(self):
        """4.2 — __force_context__ = False on small output → returned inline."""
        cfg = _make_config(max_inline_size=5000)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.ctx.write.ctx_write") as mock_write,
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command('__force_context__ = False\n"tiny output"'))

        assert result.success, f"Command failed: {result.result}"
        mock_write.assert_not_called()
        assert "tiny output" in result.result

    def test_no_force_context_uses_size_gate(self):
        """4.3 — no __force_context__ → normal size gate applies."""
        cfg = _make_config(max_inline_size=5000)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.ctx.write.ctx_write") as mock_write,
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command('"small output"'))

        assert result.success, f"Command failed: {result.result}"
        mock_write.assert_not_called()
        assert "small output" in result.result

    def test_force_context_true_ctx_tool_exempt(self):
        """4.4 — ctx.* tool with __force_context__ = True → exempt, returned inline.

        Patches execute_python_code to return force_context=True, then verifies
        that _no_deflect (triggered by tool_name="ctx.read") prevents ctx_write.
        """
        cfg = _make_config(max_inline_size=5000)

        # Single-line so runner auto-detects tool_name="ctx.read"
        code = 'ctx.read(handle="abc")'

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.ctx.write.ctx_write") as mock_write,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=('{"content": "ctx result"}', None, False, "json", True),
            ),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command(code))

        assert result.success, f"Command failed: {result.result}"
        mock_write.assert_not_called()
        assert "ctx result" in result.result

    def test_force_context_true_ot_help_exempt(self):
        """Discovery calls ot.help/ot.tool_info stay inline even when forced."""
        cfg = _make_config(max_inline_size=10)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.ctx.write.ctx_write") as mock_write,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=('{"help":"value"}', None, False, "json", True),
            ),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("ot.help(query='proxy')"))

        assert result.success, f"Command failed: {result.result}"
        mock_write.assert_not_called()
        assert "help" in result.result

    def test_ide_focused_helpers_disable_sanitization(self):
        """IDE helper calls return inline text without external-content wrapping."""
        cfg = _make_config(max_inline_size=5000)
        cfg.security.sanitize.enabled = True

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=("/repo/src/app.py", "/repo/src/app.py", True, "json", False),
            ),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("ide.file()"))

        assert result.success, f"Command failed: {result.result}"
        assert result.should_sanitize is False
        assert result.result == "/repo/src/app.py"

    def test_ide_state_disables_sanitization(self):
        """ide.state() returns structured IDE state without external-content wrapping."""
        cfg = _make_config(max_inline_size=5000)
        cfg.security.sanitize.enabled = True
        state_json = '{"connection":{"id":"onetool-mcp"}}'

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=(state_json, {"connection": {"id": "onetool-mcp"}}, True, "json", False),
            ),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("ide.state()"))

        assert result.success, f"Command failed: {result.result}"
        assert result.should_sanitize is False
        assert result.result == state_json

    def test_deflect_summary_includes_next_commands(self):
        """Handle summary includes deterministic next commands."""
        cfg = _make_config(max_inline_size=10)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.ctx.write.ctx_write", side_effect=_fake_ctx_write),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("'this output will be deflected because threshold is tiny'"))

        assert result.success, f"Command failed: {result.result}"
        parsed = json.loads(result.result)
        assert "next_commands" in parsed
        assert parsed["next_commands"][0].startswith("ctx.toc(handle='")
        assert "ctx.ask(handle='" in parsed["next_commands"][1]
        assert "ctx.read(handle='" in parsed["next_commands"][2]

    def test_force_context_and_compact_compacts_then_stores(self):
        """4.5 — __compact__ = True + __force_context__ = True → compacted output stored."""
        cfg = _make_config(max_inline_size=5000, compact=False)

        _capture_write, ctx_write_calls = _make_capture_writer()

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch("ot.executor.runner._apply_compact", return_value="compacted text"),
            patch("ot.ctx.write.ctx_write", side_effect=_capture_write),
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(
                execute_command('__compact__ = True\n__force_context__ = True\n"verbose output"')
            )

        assert result.success, f"Command failed: {result.result}"
        assert len(ctx_write_calls) == 1, "ctx_write should have been called once"
        assert ctx_write_calls[0] == "compacted text", (
            f"Expected compacted text to be stored, got: {ctx_write_calls[0]}"
        )
        parsed = json.loads(result.result)
        assert "handle" in parsed

    def test_discovery_calls_keep_json_default(self):
        """Discovery calls keep compact JSON as default format."""
        cfg = _make_config(max_inline_size=5000)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=('{"name":"ot.help"}', None, False, "json", False),
            ) as mock_exec,
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("ot.help(query='proxy')"))

        assert result.success, f"Command failed: {result.result}"
        assert mock_exec.call_args is not None
        assert mock_exec.call_args.kwargs["default_format"] == "json"

    def test_non_discovery_calls_keep_json_default(self):
        """Non-discovery calls keep compact JSON as default format."""
        cfg = _make_config(max_inline_size=5000)

        with (
            patch("ot.executor.runner.get_config", return_value=cfg),
            patch("ot.executor.runner.load_tool_registry"),
            patch("ot.executor.runner.build_execution_namespace", return_value={}),
            patch("ot.proxy.get_proxy_manager") as mock_pm,
            patch(
                "ot.executor.runner.execute_python_code",
                return_value=('{"ok":true}', None, False, "json", False),
            ) as mock_exec,
        ):
            mock_pm.return_value.servers = {}
            from ot.executor.runner import execute_command

            result = asyncio.run(execute_command("brave.search(query='python')"))

        assert result.success, f"Command failed: {result.result}"
        assert mock_exec.call_args is not None
        assert mock_exec.call_args.kwargs["default_format"] == "json"
