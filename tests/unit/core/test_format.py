"""Unit tests for format_result() helper."""

from __future__ import annotations

import json

import pytest

from ot.utils import format_result


@pytest.mark.unit
@pytest.mark.core
class TestFormatResult:
    """Test format_result JSON serialisation."""

    def test_dict_compact(self):
        """Compact mode outputs single-line JSON without whitespace."""
        data = {"name": "test", "value": 123}
        result = format_result(data)

        assert result == '{"name":"test","value":123}'
        assert json.loads(result) == data

    def test_dict_pretty(self):
        """Pretty mode outputs indented multi-line JSON."""
        data = {"name": "test", "value": 123}
        result = format_result(data, compact=False)

        assert "\n" in result
        assert "  " in result  # Indentation
        assert json.loads(result) == data

    def test_list_compact(self):
        """List data is serialised correctly in compact mode."""
        data = [{"a": 1}, {"b": 2}]
        result = format_result(data)

        assert result == '[{"a":1},{"b":2}]'
        assert json.loads(result) == data

    def test_list_pretty(self):
        """List data is serialised correctly in pretty mode."""
        data = [{"a": 1}, {"b": 2}]
        result = format_result(data, compact=False)

        assert "\n" in result
        assert json.loads(result) == data

    def test_unicode_preserved(self):
        """Unicode characters are not escaped."""
        data = {"name": "日本語", "emoji": "🎉"}
        result = format_result(data)

        assert "日本語" in result
        assert "🎉" in result
        assert json.loads(result) == data

    def test_nested_structures(self):
        """Nested dicts and lists are handled."""
        data = {
            "outer": {
                "inner": [1, 2, 3],
                "deep": {"key": "value"},
            }
        }
        result = format_result(data)

        assert json.loads(result) == data

    def test_primitives(self):
        """Primitive values are serialised correctly."""
        assert format_result(42) == "42"
        assert format_result("hello") == '"hello"'
        assert format_result(True) == "true"
        assert format_result(False) == "false"
        assert format_result(None) == "null"

    def test_empty_structures(self):
        """Empty dicts and lists are handled."""
        assert format_result({}) == "{}"
        assert format_result([]) == "[]"
