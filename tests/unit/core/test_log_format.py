"""Unit tests for log formatting module."""

from __future__ import annotations

import pytest

from ot.logging.format import (
    format_log_entry,
    format_value,
    sanitize_for_output,
    sanitize_url,
)


@pytest.mark.unit
@pytest.mark.core
class TestSanitizeUrl:
    """Test URL credential sanitisation."""

    def test_url_with_credentials(self):
        """Credentials in URL are masked."""
        url = "postgres://user:password@localhost/db"
        result = sanitize_url(url)
        assert result == "postgres://***:***@localhost/db"

    def test_url_without_credentials(self):
        """URL without credentials is unchanged."""
        url = "https://example.com/path"
        result = sanitize_url(url)
        assert result == url

    def test_url_with_port(self):
        """URL with port preserves port after masking."""
        url = "redis://admin:secret@host:6379/0"
        result = sanitize_url(url)
        assert result == "redis://***:***@host:6379/0"

    def test_complex_password(self):
        """Passwords with special characters are masked."""
        url = "mysql://root:p@ss:word@localhost/test"
        result = sanitize_url(url)
        assert "***:***@" in result
        assert "p@ss" not in result


@pytest.mark.unit
@pytest.mark.core
class TestFormatValue:
    """Test value truncation."""

    def test_short_string_unchanged(self):
        """Strings shorter than limit are not truncated."""
        result = format_value("short string", max_length=120)
        assert result == "short string"

    def test_long_string_truncated(self):
        """Long strings are truncated with ellipsis."""
        long_string = "a" * 200
        result = format_value(long_string, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_non_string_unchanged(self):
        """Non-string values pass through unchanged."""
        assert format_value(123) == 123
        assert format_value(True) is True
        assert format_value(None) is None
        assert format_value([1, 2, 3]) == [1, 2, 3]

    def test_field_based_limit_path(self):
        """Path fields use higher limit."""
        long_path = "/a/b/c" + "/d" * 50
        result = format_value(long_path, field_name="filepath")
        # filepath limit is 200
        assert len(result) <= 200

    def test_field_based_limit_error(self):
        """Error fields use higher limit."""
        long_error = "Error: " + "x" * 400
        result = format_value(long_error, field_name="error")
        # error limit is 300
        assert len(result) <= 300


@pytest.mark.unit
@pytest.mark.core
class TestSanitizeForOutput:
    """Test output sanitisation."""

    def test_url_field_sanitized(self):
        """Fields with 'url' in name are sanitized."""
        result = sanitize_for_output("postgres://user:pass@host/db", "db_url")
        assert "***:***@" in result

    def test_http_value_sanitized(self):
        """HTTP URLs are sanitized even without url in field name."""
        result = sanitize_for_output("https://user:pass@api.example.com", "endpoint")
        assert "***:***@" in result

    def test_non_url_unchanged(self):
        """Non-URL values are unchanged."""
        result = sanitize_for_output("regular text", "message")
        assert result == "regular text"


@pytest.mark.unit
@pytest.mark.core
class TestFormatLogEntry:
    """Test full log entry formatting."""

    def test_truncation_applied(self):
        """Long values are truncated in non-verbose mode."""
        entry = {"message": "a" * 500}
        result = format_log_entry(entry, verbose=False)
        assert len(result["message"]) <= 123  # 120 + "..."

    def test_verbose_no_truncation(self):
        """Long values preserved in verbose mode."""
        long_msg = "a" * 500
        entry = {"message": long_msg}
        result = format_log_entry(entry, verbose=True)
        assert result["message"] == long_msg

    def test_credentials_always_sanitized(self):
        """Credentials are sanitized even in verbose mode."""
        entry = {"db_url": "postgres://user:secret@localhost/db"}
        result = format_log_entry(entry, verbose=True)
        assert "***:***@" in result["db_url"]
        assert "secret" not in result["db_url"]

    def test_original_entry_unchanged(self):
        """Original entry dict is not modified."""
        entry = {"url": "https://user:pass@host/path"}
        original_url = entry["url"]
        format_log_entry(entry, verbose=False)
        assert entry["url"] == original_url

    def test_multiple_fields(self):
        """Multiple fields are all processed."""
        entry = {
            "query": "SELECT * FROM users",
            "url": "https://user:pass@db.example.com",
            "path": "/very/long/path" + "/segment" * 50,
        }
        result = format_log_entry(entry, verbose=False)

        # URL should be sanitized
        assert "***:***@" in result["url"]
        # Path should be truncated
        assert len(result["path"]) <= 203  # 200 + "..."
