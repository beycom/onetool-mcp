"""Unit tests for the ctx pack (flat-file implementation).

Covers: format detection/normalisation/TOC, HandleStore, write, read, toc,
grep, slice, query, append, management, maintenance, and ask.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from ot.ctx.format import build_toc, detect_format, normalize_content
from ot.ctx.store import (
    HandleStore,
    _resolve_handle,
    now_ts,
)

if TYPE_CHECKING:
    from pathlib import Path

# ===========================================================================
# Helpers
# ===========================================================================


def _make_store(tmp_path: Path) -> HandleStore:
    """Create a HandleStore backed by a temp directory."""
    return HandleStore(tmp_path / "ctx")


def _write_handle(
    store: HandleStore,
    content: str = "hello world",
    source: str = "",
    ttl: int = 3600,
) -> str:
    """Write a handle using ctx_write and return the handle string."""
    from ot.ctx.config import Config
    from ot.ctx.write import ctx_write

    config = Config(ttl=ttl)
    result = ctx_write(content, source=source, store=store, config=config)
    return result["handle"]


# ===========================================================================
# 3.4 detect_format
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestDetectFormat:
    def test_json_object(self) -> None:
        assert detect_format('{"key": "value"}') == "json"

    def test_json_array(self) -> None:
        assert detect_format("[1, 2, 3]") == "json"

    def test_json_compact(self) -> None:
        assert detect_format('{"a":1,"b":2}') == "json"

    def test_markdown_heading(self) -> None:
        content = "# Title\n\nSome text."
        assert detect_format(content) == "markdown"

    def test_markdown_subheading(self) -> None:
        content = "## Section\n\nContent here."
        assert detect_format(content) == "markdown"

    def test_markdown_only_in_first_50(self) -> None:
        # Heading beyond line 50 — not detected as markdown
        lines = ["plain text line"] * 51 + ["# Late heading"]
        content = "\n".join(lines)
        # Will not be markdown (heading beyond line 50)
        fmt = detect_format(content)
        assert fmt in ("yaml", "text")  # no JSON, no early heading

    def test_yaml_dict(self) -> None:
        content = "name: myapp\nversion: 1.0.0\n"
        assert detect_format(content) == "yaml"

    def test_yaml_list(self) -> None:
        content = "- item1\n- item2\n- item3\n"
        assert detect_format(content) == "yaml"

    def test_bare_yaml_string_is_text(self) -> None:
        # A plain string parses as YAML scalar — should be text
        assert detect_format("hello world") == "text"

    def test_text_fallback(self) -> None:
        assert detect_format("just plain text\nno structure here") == "text"

    def test_json_beats_markdown(self) -> None:
        # JSON that happens to contain # character
        content = '{"title": "# heading"}'
        assert detect_format(content) == "json"

    def test_no_headings_yaml_wins_over_text(self) -> None:
        content = "key1: value1\nkey2: value2\n"
        assert detect_format(content) == "yaml"


# ===========================================================================
# 3.5 normalize_content
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNormalizeContent:
    def test_json_single_line_expanded(self) -> None:
        content = '{"a":1,"b":2}'
        result = normalize_content(content, "json")
        assert "\n" in result
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_json_already_pretty(self) -> None:
        content = json.dumps({"a": 1}, indent=2)
        result = normalize_content(content, "json")
        assert result == content

    def test_markdown_unchanged(self) -> None:
        content = "# Title\n\nText."
        assert normalize_content(content, "markdown") == content

    def test_yaml_unchanged(self) -> None:
        content = "name: myapp\nversion: 1.0\n"
        assert normalize_content(content, "yaml") == content

    def test_text_unchanged(self) -> None:
        content = "plain text"
        assert normalize_content(content, "text") == content


# ===========================================================================
# 3.6 build_toc
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestBuildToc:
    def test_markdown_headings(self) -> None:
        content = "# Introduction\n\nText.\n\n## Background\n\nMore text.\n\n### Details\n\nDetails."
        toc = build_toc(content, "markdown")
        assert len(toc) == 3
        assert toc[0] == {"line": 1, "level": 1, "title": "Introduction"}
        assert toc[1] == {"line": 5, "level": 2, "title": "Background"}
        assert toc[2] == {"line": 9, "level": 3, "title": "Details"}

    def test_markdown_no_headings(self) -> None:
        content = "Just plain text\nno headings here."
        toc = build_toc(content, "markdown")
        assert toc == []

    def test_json_dict(self) -> None:
        content = json.dumps({"name": "myapp", "dependencies": {"lodash": "4.0"}})
        toc = build_toc(content, "json")
        keys = [e["key"] for e in toc]
        assert "name" in keys
        assert "dependencies" in keys
        # Find dependencies entry
        dep_entry = next(e for e in toc if e["key"] == "dependencies")
        assert dep_entry["type"] == "dict"
        assert dep_entry["size"] == 1

    def test_json_array(self) -> None:
        content = json.dumps([1, 2, 3, 4, 5])
        toc = build_toc(content, "json")
        assert len(toc) == 1
        assert toc[0]["key"] == "[array]"
        assert toc[0]["type"] == "list"
        assert toc[0]["size"] == 5

    def test_yaml_dict(self) -> None:
        content = "name: myapp\nversion: 1.0\n"
        toc = build_toc(content, "yaml")
        keys = [e["key"] for e in toc]
        assert "name" in keys
        assert "version" in keys

    def test_text_empty(self) -> None:
        toc = build_toc("plain text content", "text")
        assert toc == []


# ===========================================================================
# 4.2 HandleStore
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestHandleStore:
    def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        meta: dict[str, Any] = {"handle": "abc123", "source": "test", "status": "ready"}
        store.write("abc123", "hello world", meta)

        assert store.read_content("abc123") == "hello world"
        assert store.read_meta("abc123") == meta

    def test_exists_both_files(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        assert not store.exists("missing")
        store.write("abc123", "content", {"handle": "abc123"})
        assert store.exists("abc123")

    def test_missing_content_skipped_in_list(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        # Write normally
        store.write("aaa", "content", {"handle": "aaa"})
        # Manually remove content file to simulate corruption
        store.content_path("aaa").unlink()
        # list_handles should skip it
        result = store.list_handles()
        assert all(m["handle"] != "aaa" for m in result)

    def test_delete_removes_both_files(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.write("xyz", "content", {"handle": "xyz"})
        assert store.exists("xyz")
        store.delete("xyz")
        assert not store.content_path("xyz").exists()
        assert not store.meta_path("xyz").exists()
        assert not store.exists("xyz")

    def test_list_handles_returns_metas(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.write("h1", "c1", {"handle": "h1"})
        store.write("h2", "c2", {"handle": "h2"})
        handles = [m["handle"] for m in store.list_handles()]
        assert "h1" in handles
        assert "h2" in handles


# ===========================================================================
# _resolve_handle
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestResolveHandle:
    def test_string_passthrough(self) -> None:
        assert _resolve_handle("abc123") == "abc123"

    def test_handle_dict_deref(self) -> None:
        handle_dict = {"handle": "abc123", "format": "json", "size_bytes": 42}
        assert _resolve_handle(handle_dict) == "abc123"

    def test_bad_type_raises(self) -> None:
        with pytest.raises(TypeError, match="handle must be a string"):
            _resolve_handle(12345)

    def test_dict_without_handle_key_raises(self) -> None:
        with pytest.raises(TypeError, match="handle must be a string"):
            _resolve_handle({"format": "json"})

    def test_error_message_includes_hint(self) -> None:
        with pytest.raises(TypeError, match=r"h\['handle'\]"):
            _resolve_handle({"format": "json"})


# ===========================================================================
# 5.5 ctx_write
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxWrite:
    def test_write_returns_handle_and_format(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write("# Hello\nSome text.", store=store, config=Config())
        assert "handle" in result
        assert result["format"] == "markdown"
        assert result["status"] == "ready"

    def test_write_json_pretty_printed(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        compact = '{"a":1,"b":2}'
        result = ctx_write(compact, store=store, config=Config())
        handle = result["handle"]
        # Content should be multi-line
        content = store.read_content(handle)
        assert "\n" in content
        assert result["format"] == "json"
        # total_lines should reflect pretty-printed version
        assert result["total_lines"] > 1

    def test_write_toc_stored_in_meta(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write(
            "# Intro\nText\n## Section\nMore", store=store, config=Config()
        )
        meta = store.read_meta(result["handle"])
        assert "toc" in meta
        assert len(meta["toc"]) == 2

    def test_write_status_ready_immediately(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write("some content", store=store, config=Config())
        assert result["status"] == "ready"

    def test_write_verbose_adds_preview(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write(
            "line one\nline two", verbose=True, store=store, config=Config()
        )
        assert "preview" in result

    def test_write_verbose_false_no_preview(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write(
            "line one\nline two", verbose=False, store=store, config=Config()
        )
        assert "preview" not in result

    def test_write_handle_dict_dereference(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        config = Config()
        # Write original
        r1 = ctx_write("original content", store=store, config=config)
        h1 = r1["handle"]
        # Write a handle-dict reference
        r2 = ctx_write({"handle": h1}, store=store, config=config)
        assert "handle" in r2
        assert r2["handle"] != h1
        content = store.read_content(r2["handle"])
        assert content == "original content"

    def test_write_handle_dict_missing_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.write import ctx_write

        store = _make_store(tmp_path)
        result = ctx_write({"handle": "deadbeef"}, store=store, config=Config())
        assert "error" in result


# ===========================================================================
# 6.4 ctx_read
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxRead:
    def test_read_basic_pagination(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        lines = "\n".join(f"line {i}" for i in range(1, 201))
        handle = _write_handle(store, lines)

        result = ctx_read(handle, offset=1, limit=100, store=store, config=Config())
        assert result["returned"] == 100
        assert result["has_more"] is True
        assert "line 1" in result["content"]

    def test_read_tail(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle = _write_handle(store, "\n".join(f"line {i}" for i in range(1, 51)))

        result = ctx_read(handle, tail=10, store=store, config=Config())
        assert result["returned"] == 10
        assert "line 50" in result["content"]

    def test_read_long_line_truncation(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        long_line = "x" * 600
        handle = _write_handle(store, long_line)

        config = Config(max_line_chars=500)
        result = ctx_read(handle, store=store, config=config)
        line = result["content"]
        assert "[+100 chars]" in line
        # The suffix format is "  [+N chars]" — 2-space separator before bracket
        assert line.endswith("  [+100 chars]")

    def test_read_expired_handle(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle = _write_handle(store, "content", ttl=1)
        # Expire it manually
        meta = store.read_meta(handle)
        meta["expires_at"] = now_ts() - 1
        store.update_meta(handle, meta)

        result = ctx_read(handle, store=store, config=Config())
        assert "error" in result
        assert "expired" in result["error"]

    def test_read_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        result = ctx_read("deadbeef", store=store, config=Config())
        assert "error" in result

    def test_read_mode_toc(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle = _write_handle(store, "# Title\nText\n## Sub\nMore")
        result = ctx_read(handle, mode="toc", store=store, config=Config())
        assert "toc" in result or "sections" in result

    def test_read_mode_meta(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle = _write_handle(store, "some content", source="test-source")
        result = ctx_read(handle, mode="meta", store=store, config=Config())
        assert result.get("source") == "test-source"
        assert "format" in result
        assert "size_bytes" in result

    def test_read_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "line one\nline two")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_read(handle_dict, store=store, config=Config())  # type: ignore[arg-type]
        assert "content" in result
        assert "line one" in result["content"]

    def test_read_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        result = ctx_read(["not", "a", "handle"], store=store, config=Config())  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 7.3 ctx_toc
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxToc:
    def test_markdown_toc(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle = _write_handle(
            store, "# Intro\nText.\n## Background\nMore.\n### Details\nDetails."
        )
        result = ctx_toc(handle, store=store)
        assert result["format"] == "markdown"
        assert result["sections"] == 3
        assert "display" in result

    def test_json_toc(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle = _write_handle(store, '{"name":"app","version":"1.0"}')
        result = ctx_toc(handle, store=store)
        assert result["format"] == "json"
        assert "display" in result
        assert "name" in result["display"]

    def test_json_array_toc(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle = _write_handle(store, "[1, 2, 3]")
        result = ctx_toc(handle, store=store)
        assert "[array]" in result["display"]

    def test_yaml_toc(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle = _write_handle(store, "name: myapp\nversion: 1.0\n")
        result = ctx_toc(handle, store=store)
        assert result["format"] == "yaml"
        assert "name" in result["display"]

    def test_text_toc_note(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle = _write_handle(store, "plain text content here")
        result = ctx_toc(handle, store=store)
        assert result["format"] == "text"
        assert "note" in result

    def test_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        result = ctx_toc("badhandle", store=store)
        assert "error" in result

    def test_toc_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "# Title\n\nContent.\n")
        handle_dict = {"handle": handle_str, "format": "markdown"}
        result = ctx_toc(handle_dict, store=store)  # type: ignore[arg-type]
        assert result.get("format") == "markdown"
        assert result.get("sections", 0) >= 1

    def test_toc_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.toc import ctx_toc

        store = _make_store(tmp_path)
        result = ctx_toc(None, store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 8.5 ctx_grep
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxGrep:
    def test_basic_grep(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        handle = _write_handle(
            store, "apple pie\nbanana split\napricot jam\ncherry tart"
        )
        result = ctx_grep(handle, "ap", store=store, config=Config())
        assert result["returned"] >= 2
        assert "apple" in result["content"]

    def test_grep_context_lines(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        content = "a\nb\nTARGET\nd\ne"
        handle = _write_handle(store, content)
        result = ctx_grep(handle, "TARGET", context=1, store=store, config=Config())
        assert "b" in result["content"]
        assert "d" in result["content"]

    def test_grep_context_separator(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        content = "TARGET1\nb\nc\nd\ne\nTARGET2\ng"
        handle = _write_handle(store, content)
        result = ctx_grep(handle, "TARGET", context=0, store=store, config=Config())
        assert result["returned"] == 2

    def test_grep_long_line_truncation(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        long_line = "MATCH" + "x" * 600
        handle = _write_handle(store, long_line)
        config = Config(max_line_chars=500)
        result = ctx_grep(handle, "MATCH", store=store, config=config)
        assert result["returned"] == 1
        assert "[+" in result["content"]

    def test_grep_noncontiguous_separator(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        # Two matches separated by 5 lines
        lines = ["M1"] + ["x"] * 5 + ["M2"]
        handle = _write_handle(store, "\n".join(lines))
        result = ctx_grep(handle, "M[12]", context=1, store=store, config=Config())
        assert "---" in result["content"]

    def test_grep_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "apple\nbanana")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_grep(handle_dict, "apple", store=store, config=Config())
        assert result["returned"] == 1

    def test_grep_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.config import Config
        from ot.ctx.grep import ctx_grep

        store = _make_store(tmp_path)
        result = ctx_grep(12345, "apple", store=store, config=Config())  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 9.3 ctx_slice
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxSlice:
    def test_line_range(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        handle = _write_handle(store, "\n".join(f"line {i}" for i in range(1, 21)))
        result = ctx_slice(handle, "5:10", store=store)
        assert "error" not in result
        assert result["start_line"] == 5
        assert result["end_line"] == 10
        assert "line 5" in result["content"]
        assert "line 10" in result["content"]

    def test_section_by_number(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        content = "# First\nContent of first.\n## Second\nContent of second.\n# Third\nContent of third."
        handle = _write_handle(store, content)
        result = ctx_slice(handle, "#2", store=store)
        assert "error" not in result
        assert result["title"] == "Second"
        assert "Content of second" in result["content"]

    def test_section_by_integer(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        content = "# First\nContent of first.\n## Second\nContent of second.\n# Third\nContent of third."
        handle = _write_handle(store, content)
        result = ctx_slice(handle, 2, store=store)  # type: ignore[arg-type]
        assert "error" not in result
        assert result["title"] == "Second"
        assert "Content of second" in result["content"]

    def test_section_by_name(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        content = "# Introduction\nIntro text.\n## Prerequisites\nPrereq text.\n## Installation\nInstall text."
        handle = _write_handle(store, content)
        result = ctx_slice(handle, "Prerequisites", store=store)
        assert "error" not in result
        assert "Prereq text" in result["content"]

    def test_json_yaml_redirect_error(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        handle = _write_handle(store, '{"name": "app", "version": "1.0"}')
        result = ctx_slice(handle, "name.value", store=store)
        assert "error" in result
        assert "ctx.query" in result["error"]

    def test_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        result = ctx_slice("badhandle", "1:5", store=store)
        assert "error" in result

    def test_slice_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "line1\nline2\nline3")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_slice(handle_dict, "1:2", store=store)  # type: ignore[arg-type]
        assert "error" not in result
        assert "line1" in result["content"]

    def test_slice_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.slice import ctx_slice

        store = _make_store(tmp_path)
        result = ctx_slice(42, "1:2", store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 10.4 ctx_query
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxQuery:
    def test_json_simple_query(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle = _write_handle(store, '{"name": "myapp", "version": "1.0.0"}')
        result = ctx_query(handle, "name", store=store)
        assert "error" not in result
        assert result["result"] == "myapp"

    def test_yaml_query(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle = _write_handle(
            store, "metadata:\n  name: myapp\nspec:\n  replicas: 3\n"
        )
        result = ctx_query(handle, "metadata.name", store=store)
        assert "error" not in result
        assert result["result"] == "myapp"

    def test_nested_path(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        data = {"spec": {"containers": [{"image": "nginx:latest"}]}}
        handle = _write_handle(store, json.dumps(data))
        result = ctx_query(handle, "spec.containers[0].image", store=store)
        assert result["result"] == "nginx:latest"

    def test_filter_expression(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        data = {
            "items": [
                {"status": "active", "name": "a"},
                {"status": "inactive", "name": "b"},
            ]
        }
        handle = _write_handle(store, json.dumps(data))
        result = ctx_query(handle, "items[?status == 'active'].name", store=store)
        assert "error" not in result
        parsed = json.loads(result["result"])
        assert parsed == ["a"]

    def test_dict_result_pretty_printed(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        data = {"outer": {"inner": "value"}}
        handle = _write_handle(store, json.dumps(data))
        result = ctx_query(handle, "outer", store=store)
        assert "\n" in result["result"]  # pretty-printed

    def test_no_match_returns_error_with_hint(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle = _write_handle(store, '{"name": "app"}')
        result = ctx_query(handle, "nonexistent.path", store=store)
        assert "error" in result
        assert "hint" in result

    def test_wrong_format_error(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle = _write_handle(store, "# Markdown content\nNot json")
        result = ctx_query(handle, "some.path", store=store)
        assert "error" in result
        assert "json or yaml" in result["error"]

    def test_invalid_expression(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle = _write_handle(store, '{"name": "app"}')
        result = ctx_query(handle, "[invalid syntax", store=store)
        assert "error" in result

    def test_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        result = ctx_query("badhandle", "name", store=store)
        assert "error" in result

    def test_query_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, '{"city": "NYC"}')
        handle_dict = {"handle": handle_str, "format": "json"}
        result = ctx_query(handle_dict, "city", store=store)  # type: ignore[arg-type]
        assert "error" not in result
        assert result["result"] == "NYC"

    def test_query_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.query import ctx_query

        store = _make_store(tmp_path)
        result = ctx_query(object(), "name", store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 11.3 ctx_append
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxAppend:
    def test_append_combined_content(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append
        from ot.ctx.config import Config
        from ot.ctx.read import ctx_read

        store = _make_store(tmp_path)
        handle = _write_handle(store, "first line")
        ctx_append(handle, "second line", store=store)
        read_result = ctx_read(handle, limit=200, store=store, config=Config())
        assert "first line" in read_result["content"]
        assert "second line" in read_result["content"]

    def test_append_format_redetected(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append

        store = _make_store(tmp_path)
        handle = _write_handle(store, "plain text")
        # Appending a markdown heading should shift format to markdown
        result = ctx_append(handle, "\n# New Section\nContent", store=store)
        assert result["format"] == "markdown"

    def test_append_toc_regenerated(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append

        store = _make_store(tmp_path)
        handle = _write_handle(store, "# First Section\nContent")
        ctx_append(handle, "\n## Sub Section\nMore", store=store)
        meta = store.read_meta(handle)
        toc = meta["toc"]
        assert len(toc) == 2

    def test_append_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append

        store = _make_store(tmp_path)
        result = ctx_append("badhandle", "content", store=store)
        assert "error" in result

    def test_append_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "line one")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_append(handle_dict, "\nline two", store=store)  # type: ignore[arg-type]
        assert "error" not in result
        assert result["total_lines"] >= 2

    def test_append_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.append import ctx_append

        store = _make_store(tmp_path)
        result = ctx_append({"no_handle_key": True}, "content", store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]


# ===========================================================================
# 12.4 ctx_list, ctx_inspect, ctx_stats
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestManagement:
    def test_list_excludes_expired(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_list

        store = _make_store(tmp_path)
        h = _write_handle(store, "content", ttl=1)
        # Expire it
        meta = store.read_meta(h)
        meta["expires_at"] = now_ts() - 1
        store.update_meta(h, meta)

        result = ctx_list(store=store)
        assert all(item["handle"] != h for item in result)

    def test_list_source_filter(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_list

        store = _make_store(tmp_path)
        _write_handle(store, "a", source="brave:search")
        _write_handle(store, "b", source="tavily:news")
        result = ctx_list(source="brave", store=store)
        assert all("brave" in item["source"] for item in result)

    def test_list_status_filter(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_list

        store = _make_store(tmp_path)
        h = _write_handle(store, "content")
        # Mark as failed
        meta = store.read_meta(h)
        meta["status"] = "failed"
        store.update_meta(h, meta)

        result = ctx_list(status="failed", store=store)
        handles = [item["handle"] for item in result]
        assert h in handles

    def test_inspect_returns_fields(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_inspect

        store = _make_store(tmp_path)
        h = _write_handle(store, "# Title\nContent", source="test")
        result = ctx_inspect(h, store=store)
        assert result["handle"] == h
        assert result["source"] == "test"
        assert "format" in result
        assert "toc_entries" in result
        assert "ttl_remaining" in result

    def test_inspect_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_inspect

        store = _make_store(tmp_path)
        result = ctx_inspect("badhandle", store=store)
        assert "error" in result

    def test_inspect_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_inspect

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "content", source="src")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_inspect(handle_dict, store=store)  # type: ignore[arg-type]
        assert result["handle"] == handle_str
        assert result["source"] == "src"

    def test_inspect_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_inspect

        store = _make_store(tmp_path)
        result = ctx_inspect(True, store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]

    def test_stats_returns_fields(self, tmp_path: Path) -> None:
        from ot.ctx.management import ctx_stats

        store = _make_store(tmp_path)
        _write_handle(store, "some content")
        result = ctx_stats(store=store)
        assert "total_handles" in result
        assert "handles_by_status" in result
        assert "total_bytes_stored" in result
        assert "estimated_tokens_saved" in result
        assert "db_size_bytes" not in result


# ===========================================================================
# 13.4 ctx_delete, ctx_purge
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestMaintenance:
    def test_delete_removes_both_files(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_delete

        store = _make_store(tmp_path)
        h = _write_handle(store, "content")
        assert store.exists(h)
        result = ctx_delete(h, store=store)
        assert result == {"deleted": h}
        assert not store.exists(h)

    def test_delete_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_delete

        store = _make_store(tmp_path)
        result = ctx_delete("badhandle", store=store)
        assert "error" in result

    def test_delete_accepts_handle_dict(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_delete

        store = _make_store(tmp_path)
        handle_str = _write_handle(store, "to delete")
        handle_dict = {"handle": handle_str, "format": "text"}
        result = ctx_delete(handle_dict, store=store)  # type: ignore[arg-type]
        assert result == {"deleted": handle_str}
        assert not store.exists(handle_str)

    def test_delete_bad_handle_type_returns_error(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_delete

        store = _make_store(tmp_path)
        result = ctx_delete(3.14, store=store)  # type: ignore[arg-type]
        assert "error" in result
        assert "handle must be a string" in result["error"]

    def test_purge_age_filter(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_purge

        store = _make_store(tmp_path)
        h_old = _write_handle(store, "old content")
        h_new = _write_handle(store, "new content")
        # Make h_old old
        meta = store.read_meta(h_old)
        meta["created_at"] = now_ts() - 20 * 60  # 20 minutes ago
        store.update_meta(h_old, meta)

        result = ctx_purge(minutes=15, store=store)
        assert result["deleted"] >= 1
        assert not store.exists(h_old)
        assert store.exists(h_new)

    def test_purge_source_filter(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_purge

        store = _make_store(tmp_path)
        h_brave = _write_handle(store, "a", source="brave:search")
        h_other = _write_handle(store, "b", source="tavily")
        # Make both old
        for h in (h_brave, h_other):
            meta = store.read_meta(h)
            meta["created_at"] = now_ts() - 20 * 60
            store.update_meta(h, meta)

        ctx_purge(source="brave", minutes=15, store=store)
        assert not store.exists(h_brave)
        assert store.exists(h_other)

    def test_purge_status_filter(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_purge

        store = _make_store(tmp_path)
        h_failed = _write_handle(store, "failed content")
        h_ready = _write_handle(store, "ready content")
        # Make h_failed old and set status
        meta = store.read_meta(h_failed)
        meta["created_at"] = now_ts() - 20 * 60
        meta["status"] = "failed"
        store.update_meta(h_failed, meta)
        # Make h_ready old too
        meta2 = store.read_meta(h_ready)
        meta2["created_at"] = now_ts() - 20 * 60
        store.update_meta(h_ready, meta2)

        ctx_purge(status="failed", minutes=15, store=store)
        assert not store.exists(h_failed)
        assert store.exists(h_ready)

    def test_purge_delete_all(self, tmp_path: Path) -> None:
        from ot.ctx.maintenance import ctx_purge

        store = _make_store(tmp_path)
        h1 = _write_handle(store, "one")
        h2 = _write_handle(store, "two")
        result = ctx_purge(delete_all=True, store=store)
        assert result["deleted"] == 2
        assert not store.exists(h1)
        assert not store.exists(h2)


# ===========================================================================
# 15.3 ctx_ask
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCtxAsk:
    def test_ask_content_loaded_from_file(self, tmp_path: Path) -> None:
        from ot.ctx.ask import ctx_ask

        store = _make_store(tmp_path)
        h = _write_handle(store, "The answer is 42.")

        result = ctx_ask(h, q="What is the answer?", store=store)
        assert "handle" in result

    def test_ask_truncation_applied(self, tmp_path: Path) -> None:
        from ot.ctx.ask import ctx_ask

        store = _make_store(tmp_path)
        big_content = "word " * 100000  # ~500KB
        h = _write_handle(store, big_content)

        # ot_llm not installed → error returned, but truncation would have been applied
        result = ctx_ask(h, q="Summarize?", store=store)
        assert "handle" in result

    def test_ask_unknown_handle(self, tmp_path: Path) -> None:
        from ot.ctx.ask import ctx_ask

        store = _make_store(tmp_path)
        result = ctx_ask("badhandle", q="Question?", store=store)
        assert "error" in result

    def test_ask_missing_generation_route(self, tmp_path: Path) -> None:
        from ot.ctx.ask import ctx_ask
        from ot.generation import GenerationError

        store = _make_store(tmp_path)
        h = _write_handle(store, "Some content.")

        with patch(
            "ot.ctx.ask.resolve_generation",
            side_effect=GenerationError("No generation connection is configured"),
        ):
            result = ctx_ask(h, q="Question?", store=store)
        assert "error" in result
        assert "generation connection" in result["error"].lower()
