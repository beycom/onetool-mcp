"""Unit tests for serialize_result() helper."""

from __future__ import annotations

import json

import pytest

from ot.utils import serialize_result


@pytest.mark.unit
@pytest.mark.core
class TestSerializeResult:
    """Test serialize_result serialization for MCP responses."""

    def test_string_passthrough(self):
        """String values pass through unchanged."""
        assert serialize_result("hello world") == "hello world"
        assert serialize_result("") == ""
        assert serialize_result("Error: something failed") == "Error: something failed"

    def test_dict_to_compact_json(self):
        """Dict is serialized to compact JSON."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data)

        assert result == '{"name":"test","value":123}'
        assert json.loads(result) == data

    def test_list_to_compact_json(self):
        """List is serialized to compact JSON."""
        data = [{"a": 1}, {"b": 2}]
        result = serialize_result(data)

        assert result == '[{"a":1},{"b":2}]'
        assert json.loads(result) == data

    def test_nested_structures(self):
        """Nested dicts and lists are serialized correctly."""
        data = {
            "outer": {
                "inner": [1, 2, 3],
                "deep": {"key": "value"},
            }
        }
        result = serialize_result(data)

        assert json.loads(result) == data
        # Verify compact (no extra whitespace)
        assert "\n" not in result
        assert ": " not in result

    def test_unicode_preserved(self):
        """Unicode characters are not escaped."""
        data = {"name": "日本語", "emoji": "🎉"}
        result = serialize_result(data)

        assert "日本語" in result
        assert "🎉" in result
        assert json.loads(result) == data

    def test_empty_structures(self):
        """Empty dicts and lists are handled."""
        assert serialize_result({}) == "{}"
        assert serialize_result([]) == "[]"

    def test_non_json_types_use_str(self):
        """Non-JSON types use str() fallback."""
        assert serialize_result(42) == "42"
        assert serialize_result(True) == "True"
        assert serialize_result(None) == "None"
