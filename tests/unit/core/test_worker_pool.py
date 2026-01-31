"""Tests for worker pool module."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ot.executor.worker_pool import (
    Worker,
    WorkerPool,
    get_worker_pool,
    shutdown_worker_pool,
)


@pytest.mark.unit
@pytest.mark.core
class TestWorker:
    """Tests for Worker dataclass."""

    def test_is_alive_returns_true_for_running_process(self) -> None:
        """Should return True when process is running."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # None means still running

        worker = Worker(tool_path=Path("/path/to/tool.py"), process=mock_process)

        assert worker.is_alive() is True

    def test_is_alive_returns_false_for_terminated_process(self) -> None:
        """Should return False when process has terminated."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Any return code means terminated

        worker = Worker(tool_path=Path("/path/to/tool.py"), process=mock_process)

        assert worker.is_alive() is False

    def test_refresh_updates_timestamp_and_count(self) -> None:
        """Should update last_used and increment call_count."""
        mock_process = MagicMock()
        worker = Worker(tool_path=Path("/path/to/tool.py"), process=mock_process)

        old_time = worker.last_used
        old_count = worker.call_count

        time.sleep(0.01)  # Small delay to ensure time changes
        worker.refresh()

        assert worker.last_used >= old_time
        assert worker.call_count == old_count + 1


@pytest.mark.unit
@pytest.mark.core
class TestWorkerPool:
    """Tests for WorkerPool class."""

    def test_init_with_defaults(self) -> None:
        """Should initialize with default values."""
        pool = WorkerPool()

        assert pool.idle_timeout == 600.0
        assert pool._workers == {}

    def test_init_with_custom_timeout(self) -> None:
        """Should accept custom idle timeout."""
        pool = WorkerPool(idle_timeout=300.0)

        assert pool.idle_timeout == 300.0

    def test_get_stats_empty_pool(self) -> None:
        """Should return stats for empty pool."""
        pool = WorkerPool()

        stats = pool.get_stats()

        assert stats["worker_count"] == 0
        assert stats["idle_timeout"] == 600.0
        assert stats["workers"] == []

    def test_get_stats_with_workers(self) -> None:
        """Should return stats including worker info."""
        pool = WorkerPool()

        mock_process = MagicMock()
        mock_process.poll.return_value = None

        worker = Worker(
            tool_path=Path("/path/to/tool.py"),
            process=mock_process,
            call_count=5,
        )
        pool._workers[Path("/path/to/tool.py")] = worker

        stats = pool.get_stats()

        assert stats["worker_count"] == 1
        assert len(stats["workers"]) == 1
        assert stats["workers"][0]["tool"] == "tool.py"
        assert stats["workers"][0]["alive"] is True
        assert stats["workers"][0]["calls"] == 5

    def test_shutdown_terminates_workers(self) -> None:
        """Should terminate all workers on shutdown."""
        pool = WorkerPool()

        mock_process = MagicMock()
        mock_process.poll.return_value = None

        worker = Worker(tool_path=Path("/path/to/tool.py"), process=mock_process)
        pool._workers[Path("/path/to/tool.py")] = worker

        pool.shutdown()

        mock_process.terminate.assert_called_once()
        assert len(pool._workers) == 0


@pytest.mark.unit
@pytest.mark.core
class TestGlobalPool:
    """Tests for global pool functions."""

    def test_get_worker_pool_returns_singleton(self) -> None:
        """Should return same pool instance."""
        # Reset global pool
        shutdown_worker_pool()

        pool1 = get_worker_pool()
        pool2 = get_worker_pool()

        assert pool1 is pool2

        # Cleanup
        shutdown_worker_pool()

    def test_shutdown_clears_global_pool(self) -> None:
        """Should clear global pool on shutdown."""
        import ot.executor.worker_pool as pool_module

        # Get a pool first
        get_worker_pool()
        assert pool_module._pool is not None

        # Shutdown
        shutdown_worker_pool()
        assert pool_module._pool is None
