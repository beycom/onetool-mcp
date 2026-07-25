"""Integration tests for the ot_context (ctx) pack.

Exercises real immutable-record I/O — no mocked connections.
Tests the full stack: write → read/grep/toc/slice/query/list/delete/stats.
"""

from __future__ import annotations

import json

import pytest


@pytest.mark.integration
@pytest.mark.tools
class TestCtxWriteRead:
    """Write content and read it back through real file store."""

    def test_write_returns_handle(self) -> None:
        """write() returns a handle immediately."""
        from otutil.tools.ctx import write

        result = write("hello world\nline two\nline three")

        assert "handle" in result
        assert len(result["handle"]) == 32

    def test_write_returns_format(self) -> None:
        """write() returns a format field."""
        from otutil.tools.ctx import write

        result = write("hello world")
        assert "format" in result
        assert result["format"] in ("json", "yaml", "markdown", "text")

    def test_write_status_ready(self) -> None:
        """write() returns status=ready immediately."""
        from otutil.tools.ctx import delete, write

        result = write("some content")
        assert result["status"] == "ready"
        delete(result["handle"])

    def test_write_and_read(self) -> None:
        """Content written is retrievable via read()."""
        from otutil.tools.ctx import delete, read, write

        result = write("alpha\nbeta\ngamma\ndelta")
        handle = result["handle"]
        try:
            read_result = read(handle)
            assert "content" in read_result
            assert "alpha" in read_result["content"]
        finally:
            delete(handle)

    def test_write_and_grep(self) -> None:
        """grep() finds matching lines in written content."""
        from otutil.tools.ctx import delete, grep, write

        result = write("apple pie\nbanana split\napricot jam\ncherry tart")
        handle = result["handle"]
        try:
            grep_result = grep(handle, pattern="ap")
            assert "returned" in grep_result
            assert grep_result["returned"] >= 2
        finally:
            delete(handle)

    def test_write_json_pretty_prints(self) -> None:
        """JSON content is pretty-printed on write."""
        from otutil.tools.ctx import delete, read, write

        compact = '{"name":"myapp","version":"1.0.0"}'
        result = write(compact)
        handle = result["handle"]
        try:
            assert result["format"] == "json"
            assert result["total_lines"] > 1  # pretty-printed has multiple lines
            read_result = read(handle)
            # Content should be valid JSON and readable
            parsed = json.loads(read_result["content"])
            assert parsed["name"] == "myapp"
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxLifecycle:
    """list, delete, stats reflect real state."""

    def test_delete_removes_handle(self) -> None:
        """delete() removes the handle from list()."""
        from otutil.tools.ctx import delete, list, write

        result = write("to be deleted")
        handle = result["handle"]
        delete(handle)
        handles = [entry["handle"] for entry in list()]
        assert handle not in handles

    def test_stats_returns_counts(self) -> None:
        """stats() reflects at least one handle after write."""
        from otutil.tools.ctx import delete, stats, write

        result = write("some content for stats")
        handle = result["handle"]
        try:
            s = stats()
            assert "total_handles" in s
            assert s["total_handles"] >= 1
            assert "db_size_bytes" not in s
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxQuery:
    """ctx.query() on json and yaml handles."""

    def test_json_handle_query(self) -> None:
        """query() evaluates jmespath on a json handle."""
        from otutil.tools.ctx import delete, query, write

        handle = write('{"name": "myapp", "version": "1.0.0"}')["handle"]
        try:
            result = query(handle, expr="name")
            assert "error" not in result
            assert result["result"] == "myapp"
        finally:
            delete(handle)

    def test_yaml_handle_query(self) -> None:
        """query() evaluates jmespath on a yaml handle."""
        from otutil.tools.ctx import delete, query, write

        handle = write("name: myapp\nversion: 1.0\n")["handle"]
        try:
            result = query(handle, expr="name")
            assert "error" not in result
            assert result["result"] == "myapp"
        finally:
            delete(handle)

    def test_query_no_match(self) -> None:
        """query() returns error+hint on no match."""
        from otutil.tools.ctx import delete, query, write

        handle = write('{"name": "myapp"}')["handle"]
        try:
            result = query(handle, expr="nonexistent.path")
            assert "error" in result
            assert "hint" in result
        finally:
            delete(handle)

    def test_query_wrong_format(self) -> None:
        """query() rejects non-json/yaml handles."""
        from otutil.tools.ctx import delete, query, write

        handle = write("# Markdown\nThis is not json.")["handle"]
        try:
            result = query(handle, expr="name")
            assert "error" in result
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxToc:
    """ctx.toc() is format-aware."""

    def test_markdown_toc(self) -> None:
        """toc() returns section list for markdown."""
        from otutil.tools.ctx import delete, toc, write

        handle = write("# Introduction\nText.\n## Background\nMore.\n### Details\nEtc.")["handle"]
        try:
            result = toc(handle)
            assert result["format"] == "markdown"
            assert result["sections"] == 3
            assert "display" in result
        finally:
            delete(handle)

    def test_json_toc(self) -> None:
        """toc() returns key list for json."""
        from otutil.tools.ctx import delete, toc, write

        handle = write('{"name": "app", "version": "1.0", "deps": {}}')["handle"]
        try:
            result = toc(handle)
            assert result["format"] == "json"
            assert "name" in result["display"]
        finally:
            delete(handle)

    def test_yaml_toc(self) -> None:
        """toc() returns key list for yaml."""
        from otutil.tools.ctx import delete, toc, write

        handle = write("name: myapp\nversion: 1.0\nreplicas: 3\n")["handle"]
        try:
            result = toc(handle)
            assert result["format"] == "yaml"
            assert "name" in result["display"]
        finally:
            delete(handle)

    def test_text_toc(self) -> None:
        """toc() returns note for plain text."""
        from otutil.tools.ctx import delete, toc, write

        handle = write("plain text content with no structure")["handle"]
        try:
            result = toc(handle)
            assert result["format"] == "text"
            assert "note" in result
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxTruncation:
    """Long-line truncation in read() and grep()."""

    def test_read_truncates_long_lines(self) -> None:
        """read() truncates lines > max_line_chars."""
        from otutil.tools.ctx import delete, read, write

        long_line = "x" * 600
        handle = write(long_line)["handle"]
        try:
            result = read(handle)
            assert "[+" in result["content"]
        finally:
            delete(handle)

    def test_grep_truncates_long_lines(self) -> None:
        """grep() truncates matching lines > max_line_chars."""
        from otutil.tools.ctx import delete, grep, write

        long_line = "MATCH" + "y" * 600
        handle = write(long_line)["handle"]
        try:
            result = grep(handle, pattern="MATCH")
            assert result["returned"] == 1
            assert "[+" in result["content"]
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxSlice:
    """ctx.slice() section by name and number."""

    def test_slice_markdown_by_name(self) -> None:
        """slice() returns section by heading substring."""
        from otutil.tools.ctx import delete, slice, write

        content = "# Introduction\nIntro content.\n## Prerequisites\nPrereq content.\n## Installation\nInstall content."
        handle = write(content)["handle"]
        try:
            result = slice(handle, select="Prerequisites")
            assert "error" not in result
            assert "Prereq content" in result["content"]
        finally:
            delete(handle)

    def test_slice_markdown_by_number(self) -> None:
        """slice() returns section by TOC number."""
        from otutil.tools.ctx import delete, slice, write

        content = "# First\nFirst content.\n## Second\nSecond content.\n## Third\nThird content."
        handle = write(content)["handle"]
        try:
            result = slice(handle, select="#2")
            assert "error" not in result
            assert "Second content" in result["content"]
        finally:
            delete(handle)
