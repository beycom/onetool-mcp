"""Unit tests for serialize_result() helper."""

from __future__ import annotations

import json

import pytest
import yaml

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


@pytest.mark.unit
@pytest.mark.core
class TestSerializeResultFormats:
    """Test serialize_result format modes."""

    def test_json_format_default(self):
        """Default format is compact JSON."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data)
        assert result == '{"name":"test","value":123}'

    def test_json_format_explicit(self):
        """Explicit json format produces compact output."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data, fmt="json")
        assert result == '{"name":"test","value":123}'
        assert "\n" not in result

    def test_json_h_format(self):
        """json_h format produces human-readable JSON with 2-space indent."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data, fmt="json_h")
        assert "\n" in result
        assert "  " in result  # 2-space indent
        assert json.loads(result) == data

    def test_yml_format_flow_style(self):
        """yml format produces YAML flow style (compact)."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data, fmt="yml")
        parsed = yaml.safe_load(result)
        assert parsed == data

    def test_yml_h_format_block_style(self):
        """yml_h format produces YAML block style (human-readable)."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data, fmt="yml_h")
        assert "\n" in result
        parsed = yaml.safe_load(result)
        assert parsed == data

    def test_raw_format(self):
        """raw format uses str() conversion."""
        data = {"name": "test", "value": 123}
        result = serialize_result(data, fmt="raw")
        assert result == str(data)

    def test_raw_format_string(self):
        """raw format converts strings with str()."""
        result = serialize_result("hello", fmt="raw")
        assert result == "hello"

    def test_string_passthrough_all_formats(self):
        """Strings pass through unchanged for non-raw formats."""
        for fmt in ["json", "json_h", "yml", "yml_h"]:
            assert serialize_result("hello world", fmt=fmt) == "hello world"

    def test_unicode_preserved_all_formats(self):
        """Unicode is preserved across all formats."""
        data = {"name": "日本語", "emoji": "🎉"}
        for fmt in ["json", "json_h", "yml", "yml_h"]:
            result = serialize_result(data, fmt=fmt)
            assert "日本語" in result
            assert "🎉" in result


@pytest.mark.unit
@pytest.mark.core
class TestFormatMagicVariable:
    """Test __format__ magic variable integration with executor."""

    def test_format_default_compact_json(self, executor):
        """Default format (no __format__) produces compact JSON."""
        result = executor('{"name": "test", "value": 123}')
        assert result == '{"name":"test","value":123}'
        assert "\n" not in result

    def test_format_json_h(self, executor):
        """__format__ = 'json_h' produces human-readable JSON."""
        code = '''__format__ = "json_h"
{"name": "test", "value": 123}'''
        result = executor(code)
        assert "\n" in result
        assert "  " in result  # 2-space indent
        assert json.loads(result) == {"name": "test", "value": 123}

    def test_format_yml(self, executor):
        """__format__ = 'yml' produces YAML flow style."""
        code = '''__format__ = "yml"
{"name": "test", "value": 123}'''
        result = executor(code)
        parsed = yaml.safe_load(result)
        assert parsed == {"name": "test", "value": 123}

    def test_format_yml_h(self, executor):
        """__format__ = 'yml_h' produces YAML block style."""
        code = '''__format__ = "yml_h"
{"name": "test", "value": 123}'''
        result = executor(code)
        assert "\n" in result
        parsed = yaml.safe_load(result)
        assert parsed == {"name": "test", "value": 123}

    def test_format_raw(self, executor):
        """__format__ = 'raw' uses str() conversion."""
        code = '''__format__ = "raw"
{"name": "test", "value": 123}'''
        result = executor(code)
        # Should be Python repr-style, not JSON
        assert "'name'" in result or "name" in result

    def test_format_invalid_falls_back(self, executor):
        """Invalid __format__ value falls back to compact JSON."""
        code = '''__format__ = "invalid_format"
{"name": "test", "value": 123}'''
        result = executor(code)
        # Should fall back to compact JSON
        assert result == '{"name":"test","value":123}'

    def test_format_set_mid_execution(self, executor):
        """__format__ can be set after other statements."""
        code = '''data = {"name": "test"}
data["value"] = 123
__format__ = "json_h"
data'''
        result = executor(code)
        assert "\n" in result
        assert json.loads(result) == {"name": "test", "value": 123}
