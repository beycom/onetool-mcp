"""Unit tests for large output result store.

Tests the ResultStore wrapper interface — the ctx backend is mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ot.executor.result_store import QueryResult, ResultStore, StoredResult


# =============================================================================
# Helpers
# =============================================================================


def _fake_write(handle: str = "testhandle0123", content: str = "") -> dict:
    """Build a minimal ctx_write return value."""
    lines = content.splitlines()
    return {
        "handle": handle,
        "total_lines": len(lines),
        "size_bytes": len(content.encode()),
        "preview": lines[:5],
        "status": "pending",
    }


def _fake_read(
    lines: list[str],
    offset: int = 1,
    limit: int = 100,
    tail: int = 0,
) -> dict:
    """Build a ctx_read return value."""
    total = len(lines)
    if tail > 0:
        offset = max(1, total - tail + 1)
        limit = tail
    start = offset - 1
    chunk = lines[start : start + limit]
    returned = len(chunk)
    has_more = (start + limit) < total
    return {
        "content": "\n".join(chunk),
        "total_lines": total,
        "returned": returned,
        "offset": offset,
        "has_more": has_more,
        "total_size_bytes": sum(len(ln.encode()) for ln in lines),
    }


def _mock_cfg(preview_lines: int = 10, preview_max_chars: int = 500) -> MagicMock:
    cfg = MagicMock()
    cfg.output.preview_lines = preview_lines
    cfg.output.preview_max_chars = preview_max_chars
    return cfg


# =============================================================================
# STORE — ResultStore.store()
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestStore:
    """Test storing large outputs."""

    def test_store_returns_stored_result(self) -> None:
        content = "line1\nline2\nline3"
        fake = _fake_write("testhandle0123", content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            result = ResultStore().store(content, tool="test.tool")
        assert result.handle == "testhandle0123"
        assert result.total_lines == 3
        assert result.size_bytes == len(content.encode())

    def test_store_preview(self) -> None:
        lines = [f"line{i}" for i in range(20)]
        content = "\n".join(lines)
        fake = _fake_write("testhandle0123", content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            result = ResultStore().store(content, preview_lines=5)
        preview_lines = result.preview.splitlines()
        assert len(preview_lines) == 5
        assert preview_lines[0] == "line0"
        assert preview_lines[4] == "line4"

    def test_store_summary_with_tool(self) -> None:
        content = "line1\nline2\nline3"
        fake = _fake_write("testhandle0123", content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            result = ResultStore().store(content, tool="ripgrep.search")
        assert "ripgrep.search" in result.summary
        assert "3" in result.summary

    def test_store_summary_without_tool(self) -> None:
        content = "line1\nline2"
        fake = _fake_write("testhandle0123", content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            result = ResultStore().store(content)
        assert "stored" in result.summary.lower()


# =============================================================================
# QUERY — ResultStore.query()
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestQuery:
    """Test querying stored outputs."""

    def _make_store_with_handle(self, content: str) -> tuple[ResultStore, str]:
        handle = "queryhandle0123"
        fake = _fake_write(handle, content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            store = ResultStore()
            stored = store.store(content)
        return store, stored.handle

    def test_query_basic(self) -> None:
        lines = [f"line{i}" for i in range(50)]
        content = "\n".join(lines)
        store, handle = self._make_store_with_handle(content)
        with patch("ot.ctx.read.ctx_read", return_value=_fake_read(lines)):
            result = store.query(handle)
        assert result.total_lines == 50
        assert result.offset == 1
        assert result.content.splitlines()[0] == "line0"

    def test_query_offset_limit(self) -> None:
        lines = [f"line{i}" for i in range(100)]
        content = "\n".join(lines)
        store, handle = self._make_store_with_handle(content)
        with patch(
            "ot.ctx.read.ctx_read",
            return_value=_fake_read(lines, offset=11, limit=10),
        ):
            result = store.query(handle, offset=11, limit=10)
        assert result.offset == 11
        assert result.returned == 10
        assert result.content.splitlines()[0] == "line10"
        assert result.content.splitlines()[9] == "line19"
        assert result.has_more is True

    def test_query_1_indexed(self) -> None:
        lines = ["first", "second", "third"]
        store, handle = self._make_store_with_handle("\n".join(lines))
        with patch(
            "ot.ctx.read.ctx_read",
            return_value=_fake_read(lines, offset=1),
        ):
            result = store.query(handle, offset=1)
        assert result.content.splitlines()[0] == "first"

    def test_query_has_more_true(self) -> None:
        lines = [f"line{i}" for i in range(20)]
        store, handle = self._make_store_with_handle("\n".join(lines))
        with patch(
            "ot.ctx.read.ctx_read",
            return_value=_fake_read(lines, offset=1, limit=10),
        ):
            result = store.query(handle, offset=1, limit=10)
        assert result.has_more is True

    def test_query_has_more_false_at_end(self) -> None:
        lines = [f"line{i}" for i in range(20)]
        store, handle = self._make_store_with_handle("\n".join(lines))
        with patch(
            "ot.ctx.read.ctx_read",
            return_value=_fake_read(lines, offset=15, limit=10),
        ):
            result = store.query(handle, offset=15, limit=10)
        assert result.has_more is False

    def test_query_search_regex(self) -> None:
        lines = ["error: failed", "info: ok", "error: another", "debug: verbose"]
        store, handle = self._make_store_with_handle("\n".join(lines))
        error_lines = [ln for ln in lines if "error" in ln]
        with patch(
            "ot.ctx.grep.ctx_grep",
            return_value={"content": "\n".join(error_lines)},
        ):
            result = store.query(handle, search="error")
        assert result.total_lines == 2
        assert all("error" in ln for ln in result.content.splitlines())

    def test_query_invalid_handle(self) -> None:
        fake_read = {"error": "Handle not found: nonexistent123"}
        with patch("ot.ctx.read.ctx_read", return_value=fake_read):
            with pytest.raises(ValueError, match="not found"):
                ResultStore().query("nonexistent123")


# =============================================================================
# CLEANUP — ResultStore.cleanup()
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestCleanup:
    """Test cleanup delegating to ctx_purge."""

    def test_cleanup_returns_deleted_count(self) -> None:
        with patch(
            "ot.ctx.maintenance.ctx_purge",
            return_value={"deleted": 3, "bytes_freed": 1024},
        ):
            cleaned = ResultStore().cleanup()
        assert cleaned == 3

    def test_cleanup_returns_zero_when_nothing_expired(self) -> None:
        with patch(
            "ot.ctx.maintenance.ctx_purge",
            return_value={"deleted": 0, "bytes_freed": 0},
        ):
            cleaned = ResultStore().cleanup()
        assert cleaned == 0


# =============================================================================
# QUERY RESULT METADATA — QueryResult.to_dict()
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestQueryResultMetadata:
    """Test metadata fields on QueryResult.to_dict()."""

    def test_has_progress(self) -> None:
        result = QueryResult(
            content="\n".join(f"line{i}" for i in range(50)),
            total_lines=100,
            returned=50,
            offset=1,
            has_more=True,
            handle="abc123",
            limit=50,
        )
        d = result.to_dict()
        assert "progress" in d
        assert "lines 1" in d["progress"]
        assert "of 100" in d["progress"]

    def test_has_total_size_bytes(self) -> None:
        result = QueryResult(
            content="line1\nline2",
            total_lines=2,
            returned=2,
            offset=1,
            has_more=False,
            total_size_bytes=1234,
        )
        assert result.to_dict()["total_size_bytes"] == 1234

    def test_next_query_when_has_more(self) -> None:
        result = QueryResult(
            content="\n".join(f"line{i}" for i in range(50)),
            total_lines=100,
            returned=50,
            offset=1,
            has_more=True,
            handle="myhandle123",
            limit=50,
        )
        d = result.to_dict()
        assert "next_query" in d
        assert "offset=51" in d["next_query"]
        assert "myhandle123" in d["next_query"]

    def test_no_next_query_on_final_page(self) -> None:
        result = QueryResult(
            content="\n".join(f"line{i}" for i in range(20)),
            total_lines=20,
            returned=20,
            offset=1,
            has_more=False,
            handle="myhandle123",
        )
        assert not result.to_dict().get("next_query")

    def test_progress_percentage_at_end(self) -> None:
        result = QueryResult(
            content="\n".join(f"line{i}" for i in range(50)),
            total_lines=100,
            returned=50,
            offset=51,
            has_more=False,
            handle="myhandle123",
        )
        assert "100%" in result.to_dict()["progress"]



# =============================================================================
# TAIL — tail parameter
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestTail:
    """Test tail parameter."""

    def _make_store(self, content: str) -> tuple[ResultStore, str]:
        handle = "tailhandle01234"
        fake = _fake_write(handle, content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            store = ResultStore()
            stored = store.store(content)
        return store, stored.handle

    def test_tail_returns_last_n_lines(self) -> None:
        lines = [f"line{i}" for i in range(20)]
        store, handle = self._make_store("\n".join(lines))
        fake = _fake_read(lines, tail=5)
        with patch("ot.ctx.read.ctx_read", return_value=fake):
            result = store.query(handle, tail=5)
        assert result.returned == 5
        assert result.content.splitlines()[0] == "line15"
        assert result.content.splitlines()[-1] == "line19"

    def test_tail_larger_than_total(self) -> None:
        lines = ["a", "b", "c"]
        store, handle = self._make_store("\n".join(lines))
        fake = _fake_read(lines, tail=10)
        with patch("ot.ctx.read.ctx_read", return_value=fake):
            result = store.query(handle, tail=10)
        assert result.returned == 3
        assert result.content.splitlines() == ["a", "b", "c"]

    def test_tail_with_search(self) -> None:
        lines = ["error: one", "info: ok", "error: two", "error: three"]
        store, handle = self._make_store("\n".join(lines))
        error_lines = ["error: one", "error: two", "error: three"]
        with patch(
            "ot.ctx.grep.ctx_grep",
            return_value={"content": "\n".join(error_lines)},
        ):
            result = store.query(handle, search="error", tail=2)
        assert result.returned == 2
        assert "error: two" in result.content.splitlines()
        assert "error: three" in result.content.splitlines()


# =============================================================================
# CONTEXT — context parameter for search
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestContext:
    """Test context lines around search matches."""

    def _make_store(self, content: str) -> tuple[ResultStore, str]:
        handle = "ctxhandle012345"
        fake = _fake_write(handle, content)
        with (
            patch("ot.config.get_config", return_value=_mock_cfg()),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            store = ResultStore()
            stored = store.store(content)
        return store, stored.handle

    def test_context_returns_surrounding_lines(self) -> None:
        lines = ["a", "b", "TARGET", "d", "e"]
        store, handle = self._make_store("\n".join(lines))
        with patch(
            "ot.ctx.grep.ctx_grep",
            return_value={"content": "b\nTARGET\nd"},
        ):
            result = store.query(handle, search="TARGET", context=1)
        assert "b" in result.content.splitlines()
        assert "TARGET" in result.content.splitlines()
        assert "d" in result.content.splitlines()

    def test_context_no_effect_without_search(self) -> None:
        lines = [f"line{i}" for i in range(10)]
        store, handle = self._make_store("\n".join(lines))
        with patch("ot.ctx.read.ctx_read", return_value=_fake_read(lines)):
            result = store.query(handle, context=2)
        assert result.total_lines == 10


# =============================================================================
# CONFIG DEFAULTS
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestOutputConfigDefaults:
    """Test OutputConfig default values."""

    def test_max_inline_size_default(self) -> None:
        from ot.config.models import OutputConfig

        assert OutputConfig().max_inline_size == 5000

    def test_preview_max_chars_default(self) -> None:
        from ot.config.models import OutputConfig

        assert OutputConfig().preview_max_chars == 500

    def test_storage_defaults_are_runtime_scoped(self) -> None:
        from ot.config.models import OutputConfig

        config = OutputConfig()
        assert config.sessions_dir == "runtime/sessions"
        assert config.result_store_dir == "runtime/reports"


# =============================================================================
# PREVIEW TRUNCATION
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestPreviewTruncation:
    """Test that preview lines are truncated to preview_max_chars."""

    def _store(self, content: str, preview_max_chars: int = 500) -> StoredResult:
        fake = _fake_write("prevhandle01234", content)
        cfg = _mock_cfg(preview_max_chars=preview_max_chars)
        with (
            patch("ot.config.get_config", return_value=cfg),
            patch("ot.ctx.write.ctx_write", return_value=fake),
        ):
            return ResultStore().store(content)

    def test_long_line_truncated(self) -> None:
        result = self._store("x" * 1000, preview_max_chars=500)
        lines = result.preview.splitlines()
        assert len(lines) == 1
        assert lines[0] == "x" * 500 + "\u2026"

    def test_short_line_not_truncated(self) -> None:
        result = self._store("hello world", preview_max_chars=500)
        assert result.preview.splitlines()[0] == "hello world"

    def test_preview_max_chars_zero_disables_truncation(self) -> None:
        long_line = "y" * 2000
        result = self._store(long_line, preview_max_chars=0)
        assert result.preview.splitlines()[0] == long_line

    def test_large_single_line_preview_bounded(self) -> None:
        large_line = '{"data": "' + "a" * 40_000 + '"}'
        result = self._store(large_line, preview_max_chars=500)
        lines = result.preview.splitlines()
        assert len(lines) == 1
        assert len(lines[0]) <= 501
        assert lines[0].endswith("\u2026")


# =============================================================================
# OT.RESULT — ot.result() shim
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestOtResult:
    """Test ot.result() delegating to ctx backend."""

    def test_result_basic(self) -> None:
        lines = [f"line{i}" for i in range(50)]
        with patch("ot.ctx.read.ctx_read", return_value=_fake_read(lines)):
            from ot.meta import result

            r = result(handle="somehandle0123")
        assert r["total_lines"] == 50
        assert r["offset"] == 1
        assert len(r["content"].splitlines()) <= 100

    def test_result_with_offset_limit(self) -> None:
        lines = [f"line{i}" for i in range(100)]
        with patch(
            "ot.ctx.read.ctx_read",
            return_value=_fake_read(lines, offset=11, limit=10),
        ):
            from ot.meta import result

            r = result(handle="somehandle0123", offset=11, limit=10)
        assert r["offset"] == 11
        assert r["returned"] == 10
        assert r["content"].splitlines()[0] == "line10"

    def test_result_with_search(self) -> None:
        error_lines = ["error: failed", "error: another"]
        with patch(
            "ot.ctx.grep.ctx_grep",
            return_value={"content": "\n".join(error_lines)},
        ):
            from ot.meta import result

            r = result(handle="somehandle0123", search="error")
        assert r["total_lines"] == 2
        assert all("error" in ln for ln in r["content"].splitlines())

    def test_result_invalid_handle(self) -> None:
        with patch(
            "ot.ctx.read.ctx_read",
            return_value={"error": "Handle not found: nonexistent"},
        ):
            from ot.meta import result

            with pytest.raises(ValueError, match="not found"):
                result(handle="nonexistent")

    def test_result_offset_validation(self) -> None:
        from ot.meta import result

        with pytest.raises(ValueError, match="offset must be >= 1"):
            result(handle="abc123", offset=0)
        with pytest.raises(ValueError, match="offset must be >= 1"):
            result(handle="abc123", offset=-1)

    def test_result_limit_validation(self) -> None:
        from ot.meta import result

        with pytest.raises(ValueError, match="limit must be >= 1"):
            result(handle="abc123", limit=0)
        with pytest.raises(ValueError, match="limit must be >= 1"):
            result(handle="abc123", limit=-1)

    def test_result_next_query_uses_ot_result_format(self) -> None:
        """next_query in ot.result() output uses ot.result() format, not ctx.read()."""
        lines = [f"line{i}" for i in range(200)]
        fake = _fake_read(lines, offset=1, limit=100)
        # Inject a ctx-style next_query — ot.result() should remap it
        fake["next_query"] = "ctx.read('h', offset=101)"
        with patch("ot.ctx.read.ctx_read", return_value=fake):
            from ot.meta import result

            r = result(handle="somehandle0123", limit=100)
        assert "ot.result(" in r.get("next_query", "")
        assert "ctx.read(" not in r.get("next_query", "")


# =============================================================================
# DOUBLE-WRAP PREVENTION
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestDoubleWrapPrevention:
    """ot.result() output must never be re-stored as a ctx result."""

    def test_ot_result_not_rewrapped(self) -> None:
        lines = [f"line{i:04d}" for i in range(300)]
        fake_read = _fake_read(lines, offset=1, limit=200)

        mock_cfg = MagicMock()
        mock_cfg.output.max_inline_size = 100  # very low: any output > 100 bytes stored
        mock_cfg.security.sanitize.enabled = True

        from ot.meta import result as _result_fn

        class _OtProxy:
            result = staticmethod(_result_fn)

        with (
            patch("ot.executor.runner.get_config", return_value=mock_cfg),
            patch("ot.ctx.read.ctx_read", return_value=fake_read),
            patch("ot.proxy.get_proxy_manager") as mock_proxy_mgr,
            patch("ot.executor.runner.load_tool_registry"),
            patch(
                "ot.executor.runner.build_execution_namespace",
                return_value={"ot": _OtProxy()},
            ),
        ):
            mock_proxy_mgr.return_value.servers = {}

            cmd = 'ot.result(handle="somehandle0123", limit=200)'
            cmd_result = asyncio.run(
                __import__(
                    "ot.executor.runner", fromlist=["execute_command"]
                ).execute_command(cmd)
            )

        assert cmd_result.success, f"Command failed: {cmd_result.result}"
        raw = cmd_result.raw
        assert raw is not None
        assert "content" in raw, f"Expected QueryResult dict, got keys: {list(raw.keys())}"
        assert "total_lines" in raw
        assert "handle" not in raw, "ot.result() output was re-wrapped into a StoredResult"
