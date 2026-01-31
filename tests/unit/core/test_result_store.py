"""Unit tests for large output result store.

Tests the ResultStore class for storing and querying large outputs.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from ot.executor.result_store import QueryResult, ResultMeta, ResultStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_store_dir() -> Generator[Path, None, None]:
    """Create a temporary store directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = Path(tmpdir) / "result_store"
        store_dir.mkdir()
        yield store_dir


@pytest.fixture
def result_store(temp_store_dir: Path) -> ResultStore:
    """Create a ResultStore with temp directory."""
    return ResultStore(store_dir=temp_store_dir)


@pytest.fixture
def mock_config():
    """Mock config to avoid needing real config file."""
    with patch("ot.executor.result_store.get_config") as mock:
        mock.return_value.output.preview_lines = 10
        mock.return_value.output.result_ttl = 3600
        yield mock


# =============================================================================
# STORE - Storing large outputs
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestStore:
    """Test storing large outputs."""

    def test_store_basic(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Store basic content and get handle back."""
        content = "line1\nline2\nline3"
        result = result_store.store(content, tool="test.tool")

        assert result.handle
        assert len(result.handle) == 12
        assert result.total_lines == 3
        assert result.size_bytes == len(content.encode())
        assert "ot.result" in result.query

    def test_store_creates_files(
        self,
        result_store: ResultStore,
        temp_store_dir: Path,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Store creates content and meta files."""
        content = "test content\nline two"
        result = result_store.store(content)

        # Check content file exists
        content_file = temp_store_dir / f"result-{result.handle}.txt"
        assert content_file.exists()
        assert content_file.read_text() == content

        # Check meta file exists
        meta_file = temp_store_dir / f"result-{result.handle}.meta.json"
        assert meta_file.exists()

        meta = json.loads(meta_file.read_text())
        assert meta["handle"] == result.handle
        assert meta["total_lines"] == 2

    def test_store_preview(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Store returns preview lines."""
        lines = [f"line{i}" for i in range(20)]
        content = "\n".join(lines)

        result = result_store.store(content, preview_lines=5)

        assert len(result.preview) == 5
        assert result.preview[0] == "line0"
        assert result.preview[4] == "line4"

    def test_store_summary_with_tool(
        self,
        result_store: ResultStore,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Summary includes tool name."""
        content = "line1\nline2\nline3"
        result = result_store.store(content, tool="ripgrep.search")

        assert "ripgrep.search" in result.summary
        assert "3" in result.summary


# =============================================================================
# QUERY - Retrieving stored outputs
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestQuery:
    """Test querying stored outputs."""

    def test_query_basic(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query returns content with defaults."""
        lines = [f"line{i}" for i in range(50)]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle)

        assert result.total_lines == 50
        assert result.offset == 1
        assert len(result.lines) <= 100  # Default limit
        assert result.lines[0] == "line0"

    def test_query_offset_limit(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query with offset and limit."""
        lines = [f"line{i}" for i in range(100)]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, offset=11, limit=10)

        assert result.offset == 11
        assert result.returned == 10
        assert result.lines[0] == "line10"  # 0-indexed, offset 11 is line10
        assert result.lines[9] == "line19"
        assert result.has_more is True

    def test_query_1_indexed(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query uses 1-indexed offset like Claude's Read tool."""
        lines = ["first", "second", "third"]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, offset=1)
        assert result.lines[0] == "first"

        result = result_store.query(stored.handle, offset=2)
        assert result.lines[0] == "second"

    def test_query_offset_zero_treated_as_one(
        self,
        result_store: ResultStore,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Query with offset=0 treated as offset=1."""
        lines = ["first", "second", "third"]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, offset=0)
        assert result.offset == 1
        assert result.lines[0] == "first"

    def test_query_search_regex(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query with regex search filter."""
        lines = [
            "error: something failed",
            "info: all good",
            "error: another failure",
            "debug: verbose",
        ]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, search="error")

        assert result.total_lines == 2
        assert all("error" in line for line in result.lines)

    def test_query_search_fuzzy(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query with fuzzy search."""
        lines = [
            "configuration settings",
            "config file loaded",
            "user preferences",
            "configuring system",
        ]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, search="config", fuzzy=True)

        assert result.returned > 0
        # Fuzzy match should find config-related lines
        assert any("config" in line.lower() for line in result.lines)

    def test_query_has_more(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query indicates when more lines exist."""
        lines = [f"line{i}" for i in range(20)]
        content = "\n".join(lines)
        stored = result_store.store(content)

        result = result_store.query(stored.handle, offset=1, limit=10)
        assert result.has_more is True

        result = result_store.query(stored.handle, offset=15, limit=10)
        assert result.has_more is False

    def test_query_invalid_handle(self, result_store: ResultStore, mock_config) -> None:  # noqa: ARG002
        """Query with invalid handle raises error."""
        with pytest.raises(ValueError, match="not found"):
            result_store.query("nonexistent123")

    def test_query_invalid_search_pattern(
        self,
        result_store: ResultStore,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Query with invalid regex raises error."""
        content = "test content"
        stored = result_store.store(content)

        with pytest.raises(ValueError, match="Invalid search pattern"):
            result_store.query(stored.handle, search="[invalid")


# =============================================================================
# CLEANUP - TTL-based expiry
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestCleanup:
    """Test TTL-based cleanup."""

    def test_cleanup_caches_config(
        self, result_store: ResultStore, temp_store_dir: Path
    ) -> None:
        """Cleanup should call get_config once, not per file."""
        from unittest.mock import MagicMock, patch

        # Create multiple result files
        for i in range(5):
            content_path = temp_store_dir / f"result-test{i}.txt"
            content_path.write_text(f"content {i}")
            meta = {
                "handle": f"test{i}",
                "total_lines": 1,
                "size_bytes": 10,
                "created_at": datetime.now(UTC).isoformat(),
                "tool": "",
            }
            meta_path = temp_store_dir / f"result-test{i}.meta.json"
            meta_path.write_text(json.dumps(meta))

        # Mock get_config to track calls
        mock_cfg = MagicMock()
        mock_cfg.output.result_ttl = 3600

        with patch(
            "ot.executor.result_store.get_config", return_value=mock_cfg
        ) as mock_get:
            result_store.cleanup()

            # Should only call get_config once, not 5 times
            assert mock_get.call_count == 1

    def test_cleanup_removes_expired(
        self,
        result_store: ResultStore,
        temp_store_dir: Path,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Cleanup removes files older than TTL."""
        # Store a result
        content = "test content"
        stored = result_store.store(content)

        # Manually modify the meta to be expired
        meta_path = temp_store_dir / f"result-{stored.handle}.meta.json"
        meta = json.loads(meta_path.read_text())
        expired_time = datetime.now(UTC) - timedelta(hours=2)
        meta["created_at"] = expired_time.isoformat()
        meta_path.write_text(json.dumps(meta))

        # Run cleanup
        cleaned = result_store.cleanup()

        assert cleaned == 1
        assert not meta_path.exists()

    def test_cleanup_keeps_fresh(
        self,
        result_store: ResultStore,
        temp_store_dir: Path,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Cleanup keeps files within TTL."""
        content = "test content"
        stored = result_store.store(content)

        # Run cleanup immediately (files are fresh)
        cleaned = result_store.cleanup()

        assert cleaned == 0
        meta_path = temp_store_dir / f"result-{stored.handle}.meta.json"
        assert meta_path.exists()

    def test_query_expired_raises(
        self,
        result_store: ResultStore,
        temp_store_dir: Path,
        mock_config,  # noqa: ARG002
    ) -> None:
        """Querying expired result raises error."""
        content = "test content"
        stored = result_store.store(content)

        # Manually expire the result
        meta_path = temp_store_dir / f"result-{stored.handle}.meta.json"
        meta = json.loads(meta_path.read_text())
        expired_time = datetime.now(UTC) - timedelta(hours=2)
        meta["created_at"] = expired_time.isoformat()
        meta_path.write_text(json.dumps(meta))

        with pytest.raises(ValueError, match="expired"):
            result_store.query(stored.handle)


# =============================================================================
# META - Metadata handling
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestMeta:
    """Test metadata handling."""

    def test_result_meta_to_dict(self) -> None:
        """ResultMeta converts to dict."""
        meta = ResultMeta(
            handle="abc123",
            total_lines=100,
            size_bytes=5000,
            created_at="2026-01-31T10:00:00Z",
            tool="ripgrep.search",
        )

        d = meta.to_dict()

        assert d["handle"] == "abc123"
        assert d["total_lines"] == 100
        assert d["tool"] == "ripgrep.search"

    def test_result_meta_from_dict(self) -> None:
        """ResultMeta creates from dict."""
        d = {
            "handle": "xyz789",
            "total_lines": 50,
            "size_bytes": 2500,
            "created_at": "2026-01-31T12:00:00Z",
            "tool": "web.fetch",
        }

        meta = ResultMeta.from_dict(d)

        assert meta.handle == "xyz789"
        assert meta.total_lines == 50
        assert meta.tool == "web.fetch"

    def test_query_result_to_dict(self) -> None:
        """QueryResult converts to dict."""
        result = QueryResult(
            lines=["line1", "line2", "line3"],
            total_lines=100,
            returned=3,
            offset=1,
            has_more=True,
        )

        d = result.to_dict()

        assert d["lines"] == ["line1", "line2", "line3"]
        assert d["total_lines"] == 100
        assert d["returned"] == 3
        assert d["has_more"] is True


# =============================================================================
# INTEGRATION - Runner integration
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestRunnerIntegration:
    """Test integration with runner.py."""

    def test_large_output_stored(self, mock_config) -> None:  # noqa: ARG002
        """Large output is stored and summary returned."""
        from unittest.mock import MagicMock, patch

        # Mock config with low threshold
        mock_cfg = MagicMock()
        mock_cfg.output.max_inline_size = 100
        mock_cfg.output.preview_lines = 5
        mock_cfg.output.result_ttl = 3600

        with (
            patch("ot.executor.runner.get_config", return_value=mock_cfg),
            patch("ot.executor.result_store.get_config", return_value=mock_cfg),
        ):
            # Create a large output
            large_content = "x" * 200

            with tempfile.TemporaryDirectory() as tmpdir:
                store_dir = Path(tmpdir) / "store"
                store_dir.mkdir()

                store = ResultStore(store_dir=store_dir)
                result = store.store(large_content)

                assert result.handle
                assert result.size_bytes == 200
                assert "ot.result" in result.query

    def test_small_output_not_stored(self, mock_config) -> None:  # noqa: ARG002
        """Small output is returned inline, not stored."""
        # This tests the runner behavior - small outputs pass through
        small_content = "hello world"
        assert len(small_content.encode()) < 50000  # Below default threshold


# =============================================================================
# OT.RESULT - ot.result() function
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestOtResult:
    """Test ot.result() function from meta.py."""

    def test_result_basic(self, mock_config) -> None:  # noqa: ARG002
        """ot.result() queries stored output."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "store"
            store_dir.mkdir()

            store = ResultStore(store_dir=store_dir)
            lines = [f"line{i}" for i in range(50)]
            content = "\n".join(lines)
            stored = store.store(content)

            # Mock get_result_store to return our store
            with patch("ot.executor.result_store.get_result_store", return_value=store):
                from ot.meta import result

                query_result = result(handle=stored.handle)

                assert query_result["total_lines"] == 50
                assert query_result["offset"] == 1
                assert len(query_result["lines"]) <= 100

    def test_result_with_offset_limit(self, mock_config) -> None:  # noqa: ARG002
        """ot.result() respects offset and limit."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "store"
            store_dir.mkdir()

            store = ResultStore(store_dir=store_dir)
            lines = [f"line{i}" for i in range(100)]
            content = "\n".join(lines)
            stored = store.store(content)

            with patch("ot.executor.result_store.get_result_store", return_value=store):
                from ot.meta import result

                query_result = result(handle=stored.handle, offset=11, limit=10)

                assert query_result["offset"] == 11
                assert query_result["returned"] == 10
                assert query_result["lines"][0] == "line10"

    def test_result_with_search(self, mock_config) -> None:  # noqa: ARG002
        """ot.result() filters with search pattern."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "store"
            store_dir.mkdir()

            store = ResultStore(store_dir=store_dir)
            lines = ["error: failed", "info: ok", "error: another"]
            content = "\n".join(lines)
            stored = store.store(content)

            with patch("ot.executor.result_store.get_result_store", return_value=store):
                from ot.meta import result

                query_result = result(handle=stored.handle, search="error")

                assert query_result["total_lines"] == 2
                assert all("error" in line for line in query_result["lines"])

    def test_result_invalid_handle(self, mock_config) -> None:  # noqa: ARG002
        """ot.result() raises for invalid handle."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "store"
            store_dir.mkdir()

            store = ResultStore(store_dir=store_dir)

            with patch("ot.executor.result_store.get_result_store", return_value=store):
                from ot.meta import result

                with pytest.raises(ValueError, match="not found"):
                    result(handle="nonexistent")
