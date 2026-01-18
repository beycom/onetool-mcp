"""Unit tests for OneTool trigger prefixes and invocation styles.

Tests the fence processor without LLM involvement:
- All 5 trigger prefixes (__ot, __ot__run, __onetool, __onetool__run, mcp__onetool__run)
- All 3 invocation styles (simple call, inline backticks, code fence)

Migrated from demo/bench/features.yaml prefix/style tests to provide:
- Faster feedback (seconds vs minutes)
- Deterministic results (no LLM variance)
- No API costs
"""

from __future__ import annotations

import pytest


# =============================================================================
# TRIGGER PREFIXES - All 5 prefix forms
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestPrefixStripping:
    """Test stripping of all 5 trigger prefixes."""

    def test_ot_prefix(self) -> None:
        """__ot prefix is stripped."""
        from ot.executor.fence_processor import strip_fences

        # Simple call
        stripped, changed = strip_fences("__ot demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # With backticks
        stripped, changed = strip_fences("__ot `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

    def test_ot_run_prefix(self) -> None:
        """__ot__run prefix is stripped."""
        from ot.executor.fence_processor import strip_fences

        # Simple call
        stripped, changed = strip_fences("__ot__run demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # With backticks
        stripped, changed = strip_fences("__ot__run `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

    def test_onetool_prefix(self) -> None:
        """__onetool prefix is stripped."""
        from ot.executor.fence_processor import strip_fences

        # Simple call
        stripped, changed = strip_fences("__onetool demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # With backticks
        stripped, changed = strip_fences("__onetool `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

    def test_onetool_run_prefix(self) -> None:
        """__onetool__run prefix (full explicit) is stripped."""
        from ot.executor.fence_processor import strip_fences

        # Simple call
        stripped, changed = strip_fences("__onetool__run demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # With backticks
        stripped, changed = strip_fences("__onetool__run `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

    def test_mcp_onetool_run_prefix(self) -> None:
        """mcp__onetool__run prefix (explicit MCP) is stripped."""
        from ot.executor.fence_processor import strip_fences

        # Simple call
        stripped, changed = strip_fences("mcp__onetool__run demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # With backticks
        stripped, changed = strip_fences("mcp__onetool__run `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

    def test_invalid_prefix_not_stripped(self) -> None:
        """mcp__ot__run is NOT a valid prefix and should not be stripped."""
        from ot.executor.fence_processor import strip_fences

        # This is intentionally invalid - mcp__ot__run is not supported
        stripped, changed = strip_fences("mcp__ot__run demo.foo()")
        # The prefix should NOT be stripped since it's invalid
        assert "mcp__ot__run" in stripped
        assert changed is False


# =============================================================================
# INVOCATION STYLES - Simple, Backticks, Code Fence
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestInvocationStyles:
    """Test all 3 invocation styles for command execution."""

    def test_simple_call_style(self) -> None:
        """Simple direct call after prefix."""
        from ot.executor.fence_processor import strip_fences

        # Direct function call
        stripped, changed = strip_fences("__ot demo.foo(text='hello')")
        assert stripped == "demo.foo(text='hello')"
        assert changed is True

        # With method chaining
        stripped, changed = strip_fences("__ot demo.foo()[::-1].upper()")
        assert stripped == "demo.foo()[::-1].upper()"
        assert changed is True

    def test_inline_backticks_style(self) -> None:
        """Code wrapped in inline backticks."""
        from ot.executor.fence_processor import strip_fences

        # Single backticks
        stripped, changed = strip_fences("__ot `demo.foo()`")
        assert stripped == "demo.foo()"
        assert changed is True

        # Complex expression
        stripped, changed = strip_fences("__ot `demo.foo()[::-1].upper()`")
        assert stripped == "demo.foo()[::-1].upper()"
        assert changed is True

    def test_code_fence_style(self) -> None:
        """Multi-line code in fenced block."""
        from ot.executor.fence_processor import strip_fences

        # Code fence with python language
        code = """__ot
```python
msg = "hello"
demo.foo(text=msg)
```"""
        stripped, changed = strip_fences(code)
        assert 'msg = "hello"' in stripped
        assert "demo.foo(text=msg)" in stripped
        assert changed is True

        # Code fence without language specifier
        code = """__ot
```
demo.foo()
```"""
        stripped, changed = strip_fences(code)
        assert stripped == "demo.foo()"
        assert changed is True

    def test_double_backticks_style(self) -> None:
        """Double backticks for escaping."""
        from ot.executor.fence_processor import strip_fences

        # Double backtick wrapper `` `code` `` - strips outer delimiters
        stripped, changed = strip_fences("`` `demo.foo()` ``")
        # The outer "`` `" and "` ``" are stripped, leaving inner content
        assert stripped == "demo.foo()"
        assert changed is True

        # Plain double backticks strip to inner content
        stripped, changed = strip_fences("``demo.foo()``")
        assert stripped == "demo.foo()"
        assert changed is True


# =============================================================================
# COMBINED PREFIX + STYLE TESTS
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestCombinedPrefixStyle:
    """Test combinations of prefixes and styles."""

    def test_all_prefixes_with_fence(self) -> None:
        """All prefixes work with code fence style."""
        from ot.executor.fence_processor import strip_fences

        prefixes = [
            "__ot",
            "__ot__run",
            "__onetool",
            "__onetool__run",
            "mcp__onetool__run",
        ]

        for prefix in prefixes:
            code = f"""{prefix}
```python
x = 1 + 1
x
```"""
            stripped, changed = strip_fences(code)
            assert "x = 1 + 1" in stripped
            assert "x" in stripped
            assert prefix not in stripped
            assert changed is True

    def test_no_prefix_still_strips_fence(self) -> None:
        """Code fence without prefix still gets fence stripped."""
        from ot.executor.fence_processor import strip_fences

        code = """```python
demo.foo()
```"""
        stripped, changed = strip_fences(code)
        assert stripped == "demo.foo()"
        assert changed is True

    def test_whitespace_handling(self) -> None:
        """Whitespace is handled correctly."""
        from ot.executor.fence_processor import strip_fences

        # Extra whitespace between prefix and code
        stripped, changed = strip_fences("__ot    demo.foo()")
        assert stripped == "demo.foo()"
        assert changed is True

        # Leading/trailing whitespace
        stripped, changed = strip_fences("  __ot demo.foo()  ")
        assert stripped == "demo.foo()"
        assert changed is True
