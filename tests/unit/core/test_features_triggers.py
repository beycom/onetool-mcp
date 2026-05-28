"""Unit tests for OneTool trigger prefixes and invocation styles."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestPrefixStripping:
    """Test supported explicit invocation prefixes."""

    @pytest.mark.parametrize("prefix", ["__run", "__r", "__ot"])
    def test_supported_prefixes_are_stripped(self, prefix: str) -> None:
        """Supported prefixes are stripped before execution."""
        from ot.executor.fence_processor import strip_fences

        stripped, changed = strip_fences(f"{prefix} demo.foo()")

        assert stripped == "demo.foo()"
        assert changed is True

    @pytest.mark.parametrize(
        "prefix",
        [">>>", "__ot__run", "__onetool", "__onetool__run", "mcp__onetool__run"],
    )
    def test_removed_prefixes_are_not_stripped(self, prefix: str) -> None:
        """Removed prefixes are not accepted as runtime trigger syntax."""
        from ot.executor.fence_processor import strip_fences

        stripped, changed = strip_fences(f"{prefix} demo.foo()")

        assert stripped == f"{prefix} demo.foo()"
        assert changed is False


@pytest.mark.unit
@pytest.mark.core
class TestInvocationStyles:
    """Test code wrappers still strip after a supported prefix."""

    def test_inline_backticks_style(self) -> None:
        """Code wrapped in inline backticks is stripped."""
        from ot.executor.fence_processor import strip_fences

        stripped, changed = strip_fences("__run `demo.foo()`")

        assert stripped == "demo.foo()"
        assert changed is True

    def test_code_fence_style(self) -> None:
        """Multi-line code in fenced block is stripped."""
        from ot.executor.fence_processor import strip_fences

        code = """__run
```python
msg = "hello"
demo.foo(text=msg)
```"""
        stripped, changed = strip_fences(code)

        assert 'msg = "hello"' in stripped
        assert "demo.foo(text=msg)" in stripped
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

    def test_double_backticks_style(self) -> None:
        """Double backticks strip to inner content."""
        from ot.executor.fence_processor import strip_fences

        stripped, changed = strip_fences("``demo.foo()``")

        assert stripped == "demo.foo()"
        assert changed is True
