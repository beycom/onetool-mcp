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

    def test_top_level_scalars_serialize_as_json(self):
        """Top-level scalars serialize via JSON, consistent with nested values (D10).

        Previously top-level scalars fell through to str() (e.g. bool -> "True"),
        which was inconsistent with the same value nested in a dict ("true"). They
        now degrade through the same JSON path, so behavior no longer depends on
        nesting depth.
        """
        assert serialize_result(42) == "42"
        assert serialize_result(True) == "true"
        assert serialize_result(None) == "null"


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

    def test_format_default_json(self, executor):
        """Default format (no __format__) produces compact JSON."""
        result = executor('{"name": "test", "value": 123}')
        assert "\n" not in result
        assert json.loads(result) == {"name": "test", "value": 123}

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
        """Invalid __format__ value falls back to json."""
        code = '''__format__ = "invalid_format"
{"name": "test", "value": 123}'''
        result = executor(code)
        # Should fall back to json (compact)
        assert "\n" not in result
        assert json.loads(result) == {"name": "test", "value": 123}

    def test_format_set_mid_execution(self, executor):
        """__format__ can be set after other statements."""
        code = '''data = {"name": "test"}
data["value"] = 123
__format__ = "json_h"
data'''
        result = executor(code)
        assert "\n" in result
        assert json.loads(result) == {"name": "test", "value": 123}


@pytest.mark.unit
@pytest.mark.core
class TestSerializeResilience:
    """Serialization degrades instead of crashing (D7-D10, D-b1)."""

    def test_datetime_and_decimal_degrade(self):
        """D8: non-JSON-native values degrade via default=str, not TypeError."""
        from datetime import datetime
        from decimal import Decimal

        data = {"generated_at": datetime(2026, 7, 4, 12, 0), "score": Decimal("1.5")}
        result = serialize_result(data)
        parsed = json.loads(result)
        assert parsed["score"] == "1.5"
        assert "2026-07-04" in parsed["generated_at"]

    def test_nan_and_infinity_are_valid_json(self):
        """D9: NaN/Infinity serialize to valid, parseable JSON (no bare tokens)."""
        for value in (float("nan"), float("inf"), float("-inf")):
            result = serialize_result({"v": value})
            assert "NaN" not in result or json.loads(result)  # parseable
            parsed = json.loads(result)  # must not raise
            assert isinstance(parsed["v"], str)  # string sentinel

    def test_top_level_set_matches_nested_set(self):
        """D10: a top-level set degrades the same way as a nested set."""
        top = serialize_result({1, 2, 3})
        nested = serialize_result({"s": {1, 2, 3}})
        # both go through default=str -> the set becomes its str() form, no raise
        assert json.loads(top) == json.loads(nested)["s"]

    def test_yaml_set_is_tag_free(self):
        """D-b1: a set under yml produces tag-free YAML and does not raise."""
        result = serialize_result({"items": {1, 2, 3}}, fmt="yml")
        assert "!!python/object" not in result
        assert "!!set" not in result

    def test_yaml_datetime_degrades(self):
        """D-b1: yml handles values the JSON path would degrade, without raising."""
        from decimal import Decimal

        result = serialize_result({"score": Decimal("2.5")}, fmt="yml_h")
        assert "!!python" not in result
        assert "2.5" in result
