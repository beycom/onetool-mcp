"""Deterministic concurrency tests for read-derived memory mutations."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from ot.utils.sqlite_pool import SqlitePool
from otutil.tools._mem import Config
from otutil.tools._mem.content import _content_hash
from otutil.tools._mem.db import _deserialize_embedding

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Generator
    from pathlib import Path


class _ObservedPool:
    """Real SQLite pool with connection-lock ownership instrumentation."""

    def __init__(self, path: Path, config: Config) -> None:
        from otutil.tools._mem import db

        self._pool = SqlitePool(lambda: path, db._mem_setup)
        self._guard = threading.Lock()
        self.active = 0
        self.max_active = 0
        with (
            patch("otutil.tools._mem.db._get_config", return_value=config),
            self._pool.use() as conn,
        ):
            conn.commit()

    @contextmanager
    def use(self) -> Generator[sqlite3.Connection, None, None]:
        with self._pool.use() as conn:
            with self._guard:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                yield conn
            finally:
                with self._guard:
                    self.active -= 1

    def close(self) -> None:
        self._pool.close()


class _EmbeddingBarrier:
    """Synchronize the first embedding from two public mutation calls."""

    def __init__(
        self,
        pool: _ObservedPool,
        *,
        delayed_text: str | None = None,
        winner_done: threading.Event | None = None,
        enabled: bool = True,
    ) -> None:
        self._pool = pool
        self._barrier = threading.Barrier(2)
        self._delayed_text = delayed_text
        self._winner_done = winner_done
        self._enabled = enabled
        self._guard = threading.Lock()
        self.inputs: list[str] = []

    @staticmethod
    def vector(content: str) -> list[float]:
        digest = hashlib.sha256(content.encode()).digest()
        return [float(digest[index] + 1) for index in range(4)]

    def __call__(self, content: str) -> list[float] | None:
        assert self._pool.active == 0, (
            "embedding ran while the connection lock was held"
        )
        with self._guard:
            call_index = len(self.inputs)
            self.inputs.append(content)
        if call_index < 2:
            self._barrier.wait(timeout=10)
            if self._delayed_text == content:
                assert self._winner_done is not None
                assert self._winner_done.wait(timeout=10)
        return self.vector(content) if self._enabled else None


def _config(mode: str) -> Config:
    return Config(
        dimensions=4,
        embeddings_enabled=mode != "disabled",
        embeddings_async=mode == "async",
    )


@contextmanager
def _memory_environment(
    tmp_path: Path, mode: str
) -> Generator[tuple[_ObservedPool, list[str]], None, None]:
    config = _config(mode)
    pool = _ObservedPool(tmp_path / "memory.db", config)
    enqueued: list[str] = []

    def record_enqueue(memory_id: str) -> None:
        if config.embeddings_enabled and config.embeddings_async:
            enqueued.append(memory_id)

    modules = ("mutations", "history", "maintenance", "refresh")
    with ExitStack() as stack:
        stack.enter_context(
            patch("otutil.tools._mem.db._get_config", return_value=config)
        )
        for module in modules:
            stack.enter_context(
                patch(f"otutil.tools._mem.{module}._use_connection", pool.use)
            )
            if module != "maintenance":
                stack.enter_context(
                    patch(
                        f"otutil.tools._mem.{module}._enqueue_after_commit",
                        side_effect=record_enqueue,
                    )
                )
        stack.enter_context(
            patch(
                "otutil.tools._mem.maintenance._enqueue_after_commit",
                side_effect=record_enqueue,
            )
        )
        stack.enter_context(
            patch("otutil.tools._mem.mutations._get_config", return_value=config)
        )
        try:
            yield pool, enqueued
        finally:
            pool.close()


def _insert_memory(
    pool: _ObservedPool,
    *,
    content: str = "base",
    meta: dict[str, str] | None = None,
    embedding: list[float] | None = None,
) -> None:
    from otutil.tools._mem.db import _serialize_embedding, _sync_vec_index

    with pool.use() as conn:
        conn.execute(
            """
            INSERT INTO memories
                (id, topic, content, content_hash, category, tags, embedding, meta)
            VALUES (?, ?, ?, ?, 'note', '[]', ?, ?)
            """,
            [
                "memory-1",
                "topic/one",
                content,
                _content_hash(content),
                _serialize_embedding(embedding),
                json.dumps(meta or {}),
            ],
        )
        if embedding is not None:
            _sync_vec_index(conn, "memory-1", embedding)
        conn.commit()


def _insert_history(pool: _ObservedPool, content: str = "older") -> None:
    with pool.use() as conn:
        conn.execute(
            "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
            ["history-1", "memory-1", content],
        )
        conn.commit()


def _snapshot(pool: _ObservedPool) -> dict[str, Any]:
    with pool.use() as conn:
        row = conn.execute(
            "SELECT content, content_hash, embedding, meta FROM memories WHERE id = ?",
            ["memory-1"],
        ).fetchone()
        history = conn.execute(
            "SELECT content FROM memory_history WHERE memory_id = ? ORDER BY rowid",
            ["memory-1"],
        ).fetchall()
        vec = conn.execute(
            "SELECT embedding FROM memories_vec WHERE memory_id = ?",
            ["memory-1"],
        ).fetchone()
    return {"row": row, "history": history, "vec": vec}


def _run_pair(
    first: Callable[[], str],
    second: Callable[[], str],
    *,
    winner_done: threading.Event | None = None,
) -> tuple[str, str]:
    def run_first() -> str:
        result = first()
        if winner_done is not None:
            winner_done.set()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(run_first)
        second_future = executor.submit(second)
        return first_future.result(timeout=15), second_future.result(timeout=15)


def _patch_embedders(gate: _EmbeddingBarrier, *modules: str) -> ExitStack:
    stack = ExitStack()
    for module in modules:
        stack.enter_context(
            patch(f"otutil.tools._mem.{module}._embed_now", side_effect=gate)
        )
    return stack


@pytest.mark.unit
@pytest.mark.tools
def test_concurrent_appends_retry_from_latest_predecessor(tmp_path: Path) -> None:
    from otutil.tools._mem.mutations import append

    with _memory_environment(tmp_path, "sync") as (pool, enqueued):
        _insert_memory(pool)
        first_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool, delayed_text="base\n\nsecond", winner_done=first_done
        )
        with _patch_embedders(gate, "mutations"):
            first, second = _run_pair(
                lambda: append(topic="topic/one", content="first"),
                lambda: append(topic="topic/one", content="second"),
                winner_done=first_done,
            )

        snapshot = _snapshot(pool)
        final_content = snapshot["row"][0]
        assert "Appended to memory" in first
        assert "Appended to memory" in second
        assert final_content == "base\n\nfirst\n\nsecond"
        assert [row[0] for row in snapshot["history"]] == [
            "base",
            "base\n\nfirst",
        ]
        assert gate.inputs == [
            "base\n\nfirst",
            "base\n\nsecond",
            "base\n\nfirst\n\nsecond",
        ]
        assert _deserialize_embedding(snapshot["row"][2]) == pytest.approx(
            gate.vector(final_content)
        )
        assert enqueued == []
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_concurrent_updates_async_commit_only_one_enqueue(tmp_path: Path) -> None:
    from otutil.tools._mem.mutations import update

    with _memory_environment(tmp_path, "async") as (pool, enqueued):
        _insert_memory(pool, embedding=[1.0, 0.0, 0.0, 0.0])
        first_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool,
            delayed_text="second replacement",
            winner_done=first_done,
            enabled=False,
        )
        with _patch_embedders(gate, "mutations"):
            first, second = _run_pair(
                lambda: update(topic="topic/one", content="first replacement"),
                lambda: update(topic="topic/one", content="second replacement"),
                winner_done=first_done,
            )

        snapshot = _snapshot(pool)
        assert "Updated memory" in first
        assert "changed concurrently" in second
        assert snapshot["row"][0] == "first replacement"
        assert snapshot["row"][2] is None
        assert snapshot["vec"] is None
        assert snapshot["history"] == [("base",)]
        assert enqueued == ["memory-1"]
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_update_and_rollback_compare_exact_predecessor_when_disabled(
    tmp_path: Path,
) -> None:
    from otutil.tools._mem.history import rollback
    from otutil.tools._mem.mutations import update

    with _memory_environment(tmp_path, "disabled") as (pool, enqueued):
        original_embedding = [1.0, 0.0, 0.0, 0.0]
        _insert_memory(pool, embedding=original_embedding)
        _insert_history(pool)
        first_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool, delayed_text="older", winner_done=first_done, enabled=False
        )
        with _patch_embedders(gate, "mutations", "history"):
            first, second = _run_pair(
                lambda: update(topic="topic/one", content="replacement"),
                lambda: rollback(topic="topic/one"),
                winner_done=first_done,
            )

        snapshot = _snapshot(pool)
        assert "Updated memory" in first
        assert "changed concurrently" in second
        assert snapshot["row"][0] == "replacement"
        assert _deserialize_embedding(snapshot["row"][2]) == pytest.approx(
            original_embedding
        )
        assert [row[0] for row in snapshot["history"]] == ["older", "base"]
        assert snapshot["vec"] is not None
        assert enqueued == []
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_append_retries_after_concurrent_rollback(tmp_path: Path) -> None:
    from otutil.tools._mem.history import rollback
    from otutil.tools._mem.mutations import append

    with _memory_environment(tmp_path, "sync") as (pool, _enqueued):
        _insert_memory(pool)
        _insert_history(pool)
        rollback_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool,
            delayed_text="base\n\naddition",
            winner_done=rollback_done,
        )
        with _patch_embedders(gate, "mutations", "history"):
            rolled_back, appended = _run_pair(
                lambda: rollback(topic="topic/one"),
                lambda: append(topic="topic/one", content="addition"),
                winner_done=rollback_done,
            )

        snapshot = _snapshot(pool)
        assert "Rolled back memory" in rolled_back
        assert "Appended to memory" in appended
        assert snapshot["row"][0] == "older\n\naddition"
        assert [row[0] for row in snapshot["history"]] == [
            "older",
            "base",
            "older",
        ]
        assert gate.inputs[-1] == "older\n\naddition"
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_update_and_update_batch_share_async_cas_boundary(tmp_path: Path) -> None:
    from otutil.tools._mem.maintenance import update_batch
    from otutil.tools._mem.mutations import update

    with _memory_environment(tmp_path, "async") as (pool, enqueued):
        _insert_memory(pool)
        batch_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool, delayed_text="replacement", winner_done=batch_done, enabled=False
        )
        with _patch_embedders(gate, "mutations", "maintenance"):
            batch_result, update_result = _run_pair(
                lambda: update_batch(
                    search_text="base", replace_text="batch", dry_run=False
                ),
                lambda: update(topic="topic/one", content="replacement"),
                winner_done=batch_done,
            )

        snapshot = _snapshot(pool)
        assert "Updated 1 memories" in batch_result
        assert "changed concurrently" in update_result
        assert snapshot["row"][0] == "batch"
        assert snapshot["history"] == [("base",)]
        assert enqueued == ["memory-1"]
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_update_and_refresh_share_disabled_embedding_cas_boundary(
    tmp_path: Path,
) -> None:
    from otutil.tools._mem.mutations import update
    from otutil.tools._mem.refresh import refresh

    source = tmp_path / "source.md"
    source.write_text("refreshed", encoding="utf-8")
    stale_meta = {
        "source": str(source),
        "source_mtime": str(source.stat().st_mtime - 10),
    }
    with _memory_environment(tmp_path, "disabled") as (pool, enqueued):
        _insert_memory(
            pool,
            meta=stale_meta,
            embedding=[1.0, 0.0, 0.0, 0.0],
        )
        update_done = threading.Event()
        gate = _EmbeddingBarrier(
            pool, delayed_text="refreshed", winner_done=update_done, enabled=False
        )
        with _patch_embedders(gate, "mutations", "refresh"):
            update_result, refresh_result = _run_pair(
                lambda: update(topic="topic/one", content="replacement"),
                lambda: refresh(topic="topic/one", dry_run=False),
                winner_done=update_done,
            )

        snapshot = _snapshot(pool)
        assert "Updated memory" in update_result
        assert "changed concurrently" in refresh_result
        assert snapshot["row"][0] == "replacement"
        assert snapshot["history"] == [("base",)]
        assert snapshot["vec"] is not None
        assert enqueued == []
        assert pool.max_active == 1


@pytest.mark.unit
@pytest.mark.tools
def test_deletion_during_embedding_gap_leaves_no_mutation_side_effects(
    tmp_path: Path,
) -> None:
    from otutil.tools._mem.mutations import delete, update

    with _memory_environment(tmp_path, "sync") as (pool, enqueued):
        _insert_memory(pool, embedding=[1.0, 0.0, 0.0, 0.0])
        embedding_started = threading.Event()
        release_embedding = threading.Event()

        def blocked_embedding(content: str) -> list[float]:
            assert pool.active == 0
            embedding_started.set()
            assert release_embedding.wait(timeout=10)
            return _EmbeddingBarrier.vector(content)

        with (
            patch(
                "otutil.tools._mem.mutations._embed_now",
                side_effect=blocked_embedding,
            ),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            future = executor.submit(update, topic="topic/one", content="replacement")
            assert embedding_started.wait(timeout=10)
            assert "Deleted memory" in delete(id="memory-1")
            release_embedding.set()
            result = future.result(timeout=15)

        with pool.use() as conn:
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE id = 'memory-1'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM memory_history WHERE memory_id = 'memory-1'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM memories_vec WHERE memory_id = 'memory-1'"
                ).fetchone()[0]
                == 0
            )
        assert "changed concurrently" in result
        assert enqueued == []
        assert pool.max_active == 1
