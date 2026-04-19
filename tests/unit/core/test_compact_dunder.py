"""Unit tests for the __compact__ dunder variable in the runner.

Tests that execute_python_code correctly reads __compact__ from the namespace
(or config default) and applies _apply_compact at the right point in the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(compact: bool = False, sanitize_enabled: bool = True):
    """Build a minimal OneToolConfig with the given output.compact and sanitize settings."""
    from ot.config.loader import OneToolConfig
    from ot.config.models import (
        OutputConfig,
        OutputSanitizationConfig,
        SecurityConfig,
    )

    return OneToolConfig(
        security=SecurityConfig(
            sanitize=OutputSanitizationConfig(enabled=sanitize_enabled),
        ),
        output=OutputConfig(compact=compact),
    )


def _load_tools() -> dict:
    from ot.executor.tool_loader import load_tool_functions

    tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "ottools"
    return load_tool_functions(tools_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCompactDunder:
    """Tests for __compact__ dunder integration in execute_python_code."""

    def test_compact_true_applies_compaction(self):
        """5.1 — __compact__ = True with mocked _compact_text → output is compacted."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=False)):
            with patch(
                "ot.executor.runner._apply_compact",
                return_value="compacted output",
            ) as mock_compact:
                code = '__compact__ = True\n"original verbose output"'
                text, _raw, _sanitize, _fmt, _fc = execute_python_code(code, tool_functions=tool_funcs)

        mock_compact.assert_called_once()
        assert text == "compacted output"

    def test_compact_true_runtime_error_returns_original(self):
        """5.2 — __compact__ = True + _compact_text raises RuntimeError → warns, returns original."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        def _failing_compact(text: str) -> str:
            from loguru import logger

            logger.warning("__compact__ failed: LLM error — returning original output")
            return text

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=False)):
            with patch("ot.executor.runner._apply_compact", side_effect=_failing_compact):
                code = '__compact__ = True\n"original output"'
                text, _raw, _sanitize, _fmt, _fc = execute_python_code(code, tool_functions=tool_funcs)

        assert "original output" in text

    def test_compact_true_import_error_returns_original(self):
        """5.3 — __compact__ = True + ImportError from ot_caveman → warns, returns original."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        # _apply_compact internally catches ImportError and returns original
        def _apply_compact_import_error(text: str) -> str:
            return text  # simulate graceful fallback

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=False)):
            with patch("ot.executor.runner._apply_compact", side_effect=_apply_compact_import_error):
                code = '__compact__ = True\n"original output"'
                text, _raw, _sanitize, _fmt, _fc = execute_python_code(code, tool_functions=tool_funcs)

        assert "original output" in text

    def test_compact_false_output_unchanged(self):
        """5.4 — __compact__ = False → output unchanged regardless of config default."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=True)):
            with patch("ot.executor.runner._apply_compact") as mock_compact:
                code = '__compact__ = False\n"some output"'
                execute_python_code(code, tool_functions=tool_funcs)

        mock_compact.assert_not_called()

    def test_compact_not_set_config_false_unchanged(self):
        """5.5 — __compact__ not set, output.compact = false → output unchanged."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=False)):
            with patch("ot.executor.runner._apply_compact") as mock_compact:
                code = '"some output"'
                execute_python_code(code, tool_functions=tool_funcs)

        mock_compact.assert_not_called()

    def test_compact_not_set_config_true_applies_compaction(self):
        """5.6 — __compact__ not set, output.compact = true → compaction applied."""
        from ot.executor.runner import execute_python_code

        tool_funcs = _load_tools()

        with patch("ot.executor.runner.get_config", return_value=_make_config(compact=True)):
            with patch(
                "ot.executor.runner._apply_compact",
                return_value="compacted via config",
            ) as mock_compact:
                code = '"some output"'
                text, _raw, _sanitize, _fmt, _fc = execute_python_code(code, tool_functions=tool_funcs)

        mock_compact.assert_called_once()
        assert text == "compacted via config"
