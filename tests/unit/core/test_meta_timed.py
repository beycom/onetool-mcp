"""Unit tests for ot.timed() function."""

from __future__ import annotations

import time

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestTimed:
    """Tests for ot.timed() helper function."""

    def test_returns_result(self) -> None:
        """Result is captured correctly."""
        from ot.meta import timed

        def add(a: int, b: int) -> int:
            return a + b

        result = timed(add, a=2, b=3)

        assert result["result"] == 5

    def test_measures_time(self) -> None:
        """Elapsed time is measured."""
        from ot.meta import timed

        def slow() -> str:
            time.sleep(0.01)
            return "done"

        result = timed(slow)

        assert result["ms"] >= 10
        assert result["result"] == "done"

    def test_passes_kwargs(self) -> None:
        """Keyword arguments are passed through."""
        from ot.meta import timed

        def echo(**kwargs: str) -> dict[str, str]:
            return kwargs

        result = timed(echo, foo="bar", baz="qux")

        assert result["result"] == {"foo": "bar", "baz": "qux"}
