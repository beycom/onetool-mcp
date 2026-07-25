"""Real-SQLite regression tests for knowledge graph and vector replacement."""

from __future__ import annotations

import contextlib
import hashlib
import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _connection() -> sqlite3.Connection:
    from otutil.tools._knowledge.db import _SCHEMA_SQL

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    conn.execute(
        "CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)"
    )
    conn.commit()
    return conn


def _insert_chunk(
    conn: sqlite3.Connection,
    chunk_id: str,
    topic: str,
    content: str,
    *,
    url: str = "",
    source_path: str | None = None,
    anchor: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO chunks (
            id, topic, content, content_hash, category, meta, source_path, anchor
        )
        VALUES (?, ?, ?, ?, 'reference', json_object('url', ?), ?, ?)
        """,
        [
            chunk_id,
            topic,
            content,
            hashlib.sha256(content.encode()).hexdigest(),
            url,
            source_path,
            anchor,
        ],
    )


def _edge_snapshot(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT id, src_id, dst_id, edge_type, anchor_text, created_at
        FROM edges
        ORDER BY id
        """
    ).fetchall()


def _link_rows(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    return conn.execute(
        """
        SELECT src_id, dst_id, anchor_text
        FROM edges
        WHERE edge_type = 'link'
        ORDER BY src_id, dst_id
        """
    ).fetchall()


def _seed_graph(conn: sqlite3.Connection) -> None:
    _insert_chunk(
        conn,
        "source",
        "source",
        "See [original](https://docs.test/destination)",
        url="https://docs.test/source",
    )
    _insert_chunk(
        conn,
        "destination",
        "destination",
        "Destination",
        url="https://docs.test/destination",
    )
    _insert_chunk(
        conn,
        "retarget",
        "retarget",
        "Retarget",
        url="https://docs.test/retarget",
    )
    conn.execute(
        """
        INSERT INTO edges (id, src_id, dst_id, edge_type, anchor_text)
        VALUES ('manual-edge', 'destination', 'retarget', 'manual', 'curated')
        """
    )
    conn.commit()


@pytest.mark.unit
@pytest.mark.tools
def test_link_graph_reconciles_removal_retarget_anchor_and_unresolved(
    tmp_path: Path,
) -> None:
    from otutil.tools._knowledge.indexer import _build_link_graph

    conn = _connection()
    _seed_graph(conn)

    before_count = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE edge_type = 'link'"
    ).fetchone()[0]
    added = _build_link_graph(conn, tmp_path)
    conn.commit()
    after_count = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE edge_type = 'link'"
    ).fetchone()[0]
    assert added == after_count - before_count == 1
    assert _link_rows(conn) == [("source", "destination", "original")]

    stable_snapshot = _edge_snapshot(conn)
    assert _build_link_graph(conn, tmp_path) == 0
    conn.commit()
    assert _edge_snapshot(conn) == stable_snapshot

    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        ["See [renamed](https://docs.test/destination)"],
    )
    assert _build_link_graph(conn, tmp_path) == 0
    conn.commit()
    assert _link_rows(conn) == [("source", "destination", "renamed")]

    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        ["See [new target](https://docs.test/retarget)"],
    )
    assert _build_link_graph(conn, tmp_path) == 1
    conn.commit()
    assert _link_rows(conn) == [("source", "retarget", "new target")]

    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        ["See [missing](https://docs.test/unresolved)"],
    )
    assert _build_link_graph(conn, tmp_path) == 0
    conn.commit()
    assert _link_rows(conn) == []

    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        ["See [restored](https://docs.test/destination)"],
    )
    assert _build_link_graph(conn, tmp_path) == 1
    conn.commit()
    assert _link_rows(conn) == [("source", "destination", "restored")]

    conn.execute("UPDATE chunks SET content = 'No links' WHERE id = 'source'")
    assert _build_link_graph(conn, tmp_path) == 0
    conn.commit()
    assert _link_rows(conn) == []
    assert conn.execute(
        "SELECT anchor_text FROM edges WHERE id = 'manual-edge'"
    ).fetchone() == ("curated",)


@pytest.mark.unit
@pytest.mark.tools
def test_link_graph_duplicate_unchanged_rebuild_counts_no_attempts(
    tmp_path: Path,
) -> None:
    from otutil.tools._knowledge.indexer import _build_link_graph

    conn = _connection()
    _seed_graph(conn)
    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        [
            "See [first](https://docs.test/destination) and "
            "[duplicate](https://docs.test/destination)"
        ],
    )

    assert _build_link_graph(conn, tmp_path) == 1
    conn.commit()
    assert _link_rows(conn) == [("source", "destination", "first")]
    snapshot = _edge_snapshot(conn)

    assert _build_link_graph(conn, tmp_path) == 0
    conn.commit()
    assert _edge_snapshot(conn) == snapshot


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("failure", ["delete", "insert_after_delete"])
def test_index_link_graph_failure_rolls_back_exact_snapshot(
    tmp_path: Path,
    failure: str,
) -> None:
    from otutil.tools._knowledge.indexer import _build_link_graph, index_directory

    conn = _connection()
    _seed_graph(conn)
    assert _build_link_graph(conn, tmp_path) == 1
    conn.commit()
    conn.execute(
        "UPDATE chunks SET content = ? WHERE id = 'source'",
        ["See [new target](https://docs.test/retarget)"],
    )
    conn.commit()
    before = _edge_snapshot(conn)
    deleted_ids: list[str] = []
    conn.create_function(
        "record_link_delete",
        1,
        lambda edge_id: deleted_ids.append(str(edge_id)) or 0,
    )
    if failure == "delete":
        conn.execute(
            """
            CREATE TRIGGER fail_link_delete
            BEFORE DELETE ON edges
            WHEN OLD.edge_type = 'link'
            BEGIN
                SELECT RAISE(ABORT, 'injected link delete failure');
            END
            """
        )
    else:
        conn.execute(
            """
            CREATE TRIGGER fail_link_insert
            BEFORE INSERT ON edges
            WHEN NEW.edge_type = 'link'
            BEGIN
                SELECT RAISE(ABORT, 'injected link insert failure');
            END
            """
        )
    conn.execute(
        """
        CREATE TRIGGER observe_link_delete
        BEFORE DELETE ON edges
        WHEN OLD.edge_type = 'link'
        BEGIN
            SELECT record_link_delete(OLD.id);
        END
        """
    )
    conn.commit()
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    with (
        patch("otutil.tools._knowledge.indexer.get_connection", return_value=conn),
        patch(
            "otutil.tools._knowledge.indexer._db_embeddings_enabled",
            return_value=False,
        ),
        pytest.raises(sqlite3.IntegrityError, match="injected link"),
    ):
        index_directory(path=str(empty_root), db_name="test")

    assert deleted_ids
    assert not conn.in_transaction
    assert _edge_snapshot(conn) == before
    conn.execute("DROP TRIGGER observe_link_delete")
    conn.execute(f"DROP TRIGGER fail_link_{'delete' if failure == 'delete' else 'insert'}")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 3


def _seed_vector_chunk(
    conn: sqlite3.Connection,
    chunk_id: str,
    topic: str,
    content: str,
    vector: bytes | None,
    *,
    source_path: str | None = None,
    anchor: str = "",
) -> None:
    _insert_chunk(
        conn,
        chunk_id,
        topic,
        content,
        source_path=source_path,
        anchor=anchor,
    )
    if vector is not None:
        conn.execute(
            "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
            [chunk_id, vector],
        )
    conn.commit()


def _install_vector_insert_failure(
    conn: sqlite3.Connection,
    chunk_id: str,
    deleted_ids: list[str],
) -> None:
    conn.create_function(
        "record_vector_delete",
        1,
        lambda deleted_id: deleted_ids.append(str(deleted_id)) or 0,
    )
    conn.execute(
        f"""
        CREATE TRIGGER observe_vector_delete
        BEFORE DELETE ON chunks_vec
        WHEN OLD.chunk_id = '{chunk_id}'
        BEGIN
            SELECT record_vector_delete(OLD.chunk_id);
        END
        """
    )
    conn.execute(
        f"""
        CREATE TRIGGER fail_vector_insert
        BEFORE INSERT ON chunks_vec
        WHEN NEW.chunk_id = '{chunk_id}'
        BEGIN
            SELECT RAISE(ABORT, 'injected vector insert failure');
        END
        """
    )
    conn.commit()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("operation", ["append", "update"])
def test_public_mutation_retains_exact_vector_after_post_delete_failure(
    operation: str,
) -> None:
    from otutil.tools._knowledge import crud

    conn = _connection()
    old_vector = b"\x01\x02\x03\x04old-vector"
    _seed_vector_chunk(conn, "chunk", "topic", "old", old_vector)
    deleted_ids: list[str] = []
    _install_vector_insert_failure(conn, "chunk", deleted_ids)

    with (
        patch(
            "otutil.tools._knowledge.crud.use_connection",
            return_value=contextlib.nullcontext(conn),
        ),
        patch(
            "otutil.tools._knowledge.crud.generate_embedding",
            return_value=[0.25, 0.5],
        ),
    ):
        if operation == "append":
            result = crud.append(
                topic="topic",
                content=" appended",
                db="test",
            )
            expected_content = "old appended"
        else:
            result = crud.update(
                topic="topic",
                content="replacement",
                db="test",
            )
            expected_content = "replacement"

    assert deleted_ids == ["chunk"]
    assert "warning: embedding failed" in result
    assert "injected vector insert failure" in result
    assert conn.execute(
        "SELECT content FROM chunks WHERE id = 'chunk'"
    ).fetchone() == (expected_content,)
    assert conn.execute(
        "SELECT embedding FROM chunks_vec WHERE chunk_id = 'chunk'"
    ).fetchone() == (old_vector,)
    assert not conn.in_transaction
    conn.execute("UPDATE chunks SET hit_count = 1 WHERE id = 'chunk'")
    conn.commit()
    assert conn.execute(
        "SELECT hit_count FROM chunks WHERE id = 'chunk'"
    ).fetchone() == (1,)


@pytest.mark.unit
@pytest.mark.tools
def test_update_vector_savepoints_isolate_chunks_and_absent_prior_vector() -> None:
    from otpack import serialize_embedding
    from otutil.tools._knowledge import crud

    conn = _connection()
    first_old = b"first-old-vector"
    second_old = b"second-old-vector"
    _seed_vector_chunk(
        conn,
        "first",
        "shared",
        "old first",
        first_old,
        source_path="doc.md",
        anchor="first",
    )
    _seed_vector_chunk(
        conn,
        "second",
        "shared",
        "old second",
        second_old,
        source_path="doc.md",
        anchor="second",
    )
    _seed_vector_chunk(
        conn,
        "absent",
        "no-vector",
        "old absent",
        None,
        source_path="other.md",
    )
    deleted_ids: list[str] = []
    _install_vector_insert_failure(conn, "first", deleted_ids)
    new_embedding = [0.25, 0.5]

    with (
        patch(
            "otutil.tools._knowledge.crud.use_connection",
            return_value=contextlib.nullcontext(conn),
        ),
        patch(
            "otutil.tools._knowledge.crud.generate_embedding",
            return_value=new_embedding,
        ),
    ):
        multi_result = crud.update(
            topic="shared",
            content="new shared content",
            db="test",
        )
        conn.execute("DROP TRIGGER fail_vector_insert")
        conn.execute(
            """
            CREATE TRIGGER fail_absent_vector_insert
            BEFORE INSERT ON chunks_vec
            WHEN NEW.chunk_id = 'absent'
            BEGIN
                SELECT RAISE(ABORT, 'injected absent insert failure');
            END
            """
        )
        conn.commit()
        absent_result = crud.update(
            topic="no-vector",
            content="new absent content",
            db="test",
        )

    assert "warning: embedding failed" in multi_result
    assert conn.execute(
        "SELECT content FROM chunks WHERE topic = 'shared' ORDER BY id"
    ).fetchall() == [("new shared content",), ("new shared content",)]
    assert conn.execute(
        "SELECT embedding FROM chunks_vec WHERE chunk_id = 'first'"
    ).fetchone() == (first_old,)
    assert conn.execute(
        "SELECT embedding FROM chunks_vec WHERE chunk_id = 'second'"
    ).fetchone() == (serialize_embedding(new_embedding),)
    assert "warning: embedding failed" in absent_result
    assert conn.execute(
        "SELECT content FROM chunks WHERE id = 'absent'"
    ).fetchone() == ("new absent content",)
    assert conn.execute(
        "SELECT embedding FROM chunks_vec WHERE chunk_id = 'absent'"
    ).fetchone() is None
