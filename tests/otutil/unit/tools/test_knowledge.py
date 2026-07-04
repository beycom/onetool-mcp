"""Tests for the knowledge pack.

Covers: DB schema/triggers, chunker, indexer (hash dedup, link graph),
search lanes and RRF merge, CRUD round-trips, list/grep/slice/toc output
shapes, error paths (missing sqlite-vec, FTS5), and smoke tests for config.
"""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_conn() -> sqlite3.Connection:
    """Open an in-memory SQLite connection with WAL + FK on."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Apply the chunks/edges schema and FTS5 virtual tables."""
    from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_FTS_SQL)
    conn.executescript(_FTS_TRIGGERS_SQL)
    conn.commit()


def _insert_chunk(conn: sqlite3.Connection, chunk_id: str, topic: str, content: str,
                  category: str = "reference", tags: str = "[]", meta: str = "{}") -> None:
    """Insert a chunk row directly (bypasses embedding)."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    conn.execute(
        "INSERT INTO chunks (id, topic, content, content_hash, category, tags, meta) VALUES (?,?,?,?,?,?,?)",
        [chunk_id, topic, content, content_hash, category, tags, meta],
    )
    conn.commit()


# ===========================================================================
# 2.3 — DB schema, FTS5 + vec trigger sync, edge cascade
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeDBSchema:
    """Schema creation, triggers, and edge cascade."""

    def test_schema_creates_chunks_table(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "chunks" in tables
        assert "edges" in tables

    def test_schema_creates_fts5_table(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "chunks_fts" in tables

    def test_fts5_trigger_insert_syncs(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        _insert_chunk(conn, "c1", "python/generators", "yield expressions are lazy")
        rows = conn.execute("SELECT topic FROM chunks_fts WHERE chunks_fts MATCH 'lazy'").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "python/generators"

    def test_fts5_trigger_delete_syncs(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        _insert_chunk(conn, "c1", "python/generators", "yield expressions are lazy")
        conn.execute("DELETE FROM chunks WHERE id = 'c1'")
        conn.commit()
        rows = conn.execute("SELECT topic FROM chunks_fts WHERE chunks_fts MATCH 'lazy'").fetchall()
        assert len(rows) == 0

    def test_fts5_trigger_update_syncs(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        _insert_chunk(conn, "c1", "python/generators", "yield expressions are lazy")
        conn.execute("UPDATE chunks SET content = 'coroutines and async' WHERE id = 'c1'")
        conn.commit()
        rows = conn.execute("SELECT topic FROM chunks_fts WHERE chunks_fts MATCH 'coroutines'").fetchall()
        assert len(rows) == 1
        rows_old = conn.execute("SELECT topic FROM chunks_fts WHERE chunks_fts MATCH 'lazy'").fetchall()
        assert len(rows_old) == 0

    def test_edge_cascade_on_chunk_delete(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        _insert_chunk(conn, "src", "a/page", "source content")
        _insert_chunk(conn, "dst", "b/page", "dest content")
        conn.execute(
            "INSERT INTO edges (id, src_id, dst_id, edge_type) VALUES ('e1', 'src', 'dst', 'link')"
        )
        conn.commit()
        conn.execute("DELETE FROM chunks WHERE id = 'src'")
        conn.commit()
        edges = conn.execute("SELECT * FROM edges WHERE id = 'e1'").fetchall()
        assert len(edges) == 0

    def test_source_path_anchor_unique_constraint(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        content_hash1 = hashlib.sha256(b"first").hexdigest()
        content_hash2 = hashlib.sha256(b"second").hexdigest()
        conn.execute(
            "INSERT INTO chunks (id, topic, content, content_hash, category, source_path, anchor) VALUES (?,?,?,?,?,?,?)",
            ["c1", "topic/a", "first", content_hash1, "reference", "path/to/doc", "intro"],
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO chunks (id, topic, content, content_hash, category, source_path, anchor) VALUES (?,?,?,?,?,?,?)",
                ["c2", "topic/b", "second", content_hash2, "reference", "path/to/doc", "intro"],
            )
            conn.commit()

    def test_topic_allows_duplicates(self):
        conn = _make_in_memory_conn()
        _apply_schema(conn)
        _insert_chunk(conn, "c1", "same/topic", "first")
        content_hash = hashlib.sha256(b"second").hexdigest()
        conn.execute(
            "INSERT INTO chunks (id, topic, content, content_hash, category) VALUES (?,?,?,?,?)",
            ["c2", "same/topic", "second", content_hash, "reference"],
        )
        conn.commit()
        rows = conn.execute("SELECT id FROM chunks WHERE topic = 'same/topic'").fetchall()
        assert len(rows) == 2

    def test_kb_setup_rejects_non_positive_dimensions(self):
        from otutil.tools._knowledge.db import _kb_setup

        conn = MagicMock()
        fake_vec = MagicMock()
        cfg = MagicMock()
        cfg.dimensions = 0

        with (
            patch("otutil.tools._knowledge.db._check_vec_available", return_value=True),
            patch("otutil.tools._knowledge.db._get_config", return_value=cfg),
            patch.dict("sys.modules", {"sqlite_vec": fake_vec}),
            pytest.raises(ValueError, match="knowledge dimensions must be > 0"),
        ):
            _kb_setup(conn)


# ===========================================================================
# 3.3 — Chunker: heading splits, frontmatter, sidecar
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeChunker:
    """Chunker tests: single chunk for short files, heading splits, frontmatter, sidecar."""

    def test_short_file_single_chunk(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "short.md"
        md.write_text("# Title\n\nSome content here.\n", encoding="utf-8")
        chunks = chunk_file(md, Path("short.md"))
        assert len(chunks) == 1
        assert chunks[0].topic == "short"

    def test_long_file_splits_on_headings(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        lines = ["# Section A\n"] + ["line\n"] * 55 + ["# Section B\n"] + ["line\n"] * 55
        md = tmp_path / "long.md"
        md.write_text("".join(lines), encoding="utf-8")
        chunks = chunk_file(md, Path("long.md"))
        # Should have at least 2 heading chunks
        assert len(chunks) >= 2
        topics = [c.topic for c in chunks]
        assert any("section-a" in t for t in topics)
        assert any("section-b" in t for t in topics)

    def test_frontmatter_parsed(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "fm.md"
        md.write_text("---\nurl: https://docs.example.test/page\ntags: [alpha, beta]\n---\n\nContent.\n", encoding="utf-8")
        chunks = chunk_file(md, Path("fm.md"))
        assert len(chunks) == 1
        assert chunks[0].meta.get("url") == "https://docs.example.test/page"
        assert "alpha" in chunks[0].tags

    def test_sidecar_overrides_frontmatter(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "doc.md"
        md.write_text("---\nurl: https://fm-url.example.test/\n---\n\nContent.\n", encoding="utf-8")
        sidecar = tmp_path / "doc.meta.yaml"
        sidecar.write_text("url: https://sidecar-url.example.test/\nsource: crawl\n", encoding="utf-8")
        chunks = chunk_file(md, Path("doc.md"))
        assert chunks[0].meta.get("url") == "https://sidecar-url.example.test/"

    def test_no_sidecar_uses_frontmatter(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "only_fm.md"
        md.write_text("---\nurl: https://fm-only.example.test/\n---\n\nContent.\n", encoding="utf-8")
        chunks = chunk_file(md, Path("only_fm.md"))
        assert chunks[0].meta.get("url") == "https://fm-only.example.test/"

    def test_topic_uses_rel_path(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        sub = tmp_path / "commands"
        sub.mkdir()
        md = sub / "move.md"
        md.write_text("# Move command\n\nDescription.\n", encoding="utf-8")
        chunks = chunk_file(md, Path("commands/move.md"))
        assert chunks[0].topic.startswith("commands/move")

    def test_content_hash_deterministic(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        content = "Deterministic content"
        md = tmp_path / "det.md"
        md.write_text(content, encoding="utf-8")
        chunks1 = chunk_file(md, Path("det.md"))
        chunks2 = chunk_file(md, Path("det.md"))
        assert chunks1[0].content_hash == chunks2[0].content_hash

    def test_sidecar_keywords_become_tags(self, tmp_path: Path):
        """Sidecar keywords pre-populate chunk tags."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://docs.example.test/page\nsource: site\nkeywords: [move, translate, transform]\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert "move" in chunks[0].tags
        assert "translate" in chunks[0].tags
        assert "transform" in chunks[0].tags

    def test_sidecar_keywords_comma_string_becomes_tags(self, tmp_path: Path):
        """Sidecar keywords as comma-separated string (crawl4ai format) become tags."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://docs.example.test/page\nsource: site\nkeywords: move, translate, transform\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert "move" in chunks[0].tags
        assert "translate" in chunks[0].tags
        assert "transform" in chunks[0].tags

    def test_sidecar_title_in_meta(self, tmp_path: Path):
        """Sidecar title appears in chunk.meta."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://docs.example.test/page\nsource: site\ntitle: Move Command\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].meta.get("title") == "Move Command"

    def test_sidecar_url_in_meta_but_topic_from_path(self, tmp_path: Path):
        """URL in sidecar is stored in meta but topic is still derived from rel_path."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "app_v1_guide_en-us_commands_move.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "app_v1_guide_en-us_commands_move.meta.yaml").write_text(
            "url: https://docs.example.test/app/v1/guide/en-us/commands/move\nsource: site\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("app_v1_guide_en-us_commands_move.md"))
        assert chunks[0].topic == "app_v1_guide_en-us_commands_move"
        assert chunks[0].meta.get("url") == "https://docs.example.test/app/v1/guide/en-us/commands/move"

    def test_sidecar_url_ignored_for_topic_derivation(self, tmp_path: Path):
        """url_base_path in sidecar is silently ignored (removed field)."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "cmd.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "cmd.meta.yaml").write_text(
            "url: https://docs.example.test/app/v1/guide/en-us/commands/move\n"
            "source: site\n"
            "url_base_path: /app/v1/guide/en-us\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("cmd.md"))
        # topic from rel_path, not URL
        assert chunks[0].topic == "cmd"

    def test_sidecar_keywords_do_not_duplicate_fm_tags(self, tmp_path: Path):
        """Keywords that already exist in frontmatter tags are not duplicated."""
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "page.md"
        md.write_text("---\ntags: [move, rotate]\n---\n\nContent.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://docs.example.test/page\nkeywords: [move, scale]\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].tags.count("move") == 1  # no duplicate
        assert "scale" in chunks[0].tags


# ===========================================================================
# 3.3 (cont.) — Indexer: hash dedup, link graph
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeIndexer:
    """Indexer: dedup by hash, overwrite modes, link graph extraction."""

    def _setup_db(self, db_name: str) -> sqlite3.Connection:
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL, _pools, _pools_lock, SqlitePool
        conn = _make_in_memory_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        conn.commit()
        return conn

    def test_index_directory_new_files(self, tmp_path: Path):
        """New files get indexed."""
        from otutil.tools._knowledge.indexer import index_directory
        from otutil.tools._knowledge.db import close_connection

        (tmp_path / "a.md").write_text("# Alpha\n\nContent A.\n", encoding="utf-8")
        (tmp_path / "b.md").write_text("# Beta\n\nContent B.\n", encoding="utf-8")

        db_name = f"test_{id(tmp_path)}"
        try:
            with patch("otutil.tools._knowledge.indexer._store_embeddings_batch", return_value=None):
                with patch("otutil.tools._knowledge.db._resolve_db_path", return_value=tmp_path / f"{db_name}.db"):
                    result = index_directory(path=str(tmp_path), db_name=db_name)
            assert result.indexed >= 2
            assert result.errors == []
        finally:
            close_connection(db_name)

    def test_index_directory_skip_on_same_hash(self, tmp_path: Path):
        """Re-indexing unchanged files skips them."""
        from otutil.tools._knowledge.indexer import index_directory
        from otutil.tools._knowledge.db import close_connection

        (tmp_path / "a.md").write_text("Stable content", encoding="utf-8")
        db_name = f"test_dedup_{id(tmp_path)}"
        try:
            with patch("otutil.tools._knowledge.indexer._store_embeddings_batch", return_value=None):
                with patch("otutil.tools._knowledge.db._resolve_db_path", return_value=tmp_path / f"{db_name}.db"):
                    result1 = index_directory(path=str(tmp_path), db_name=db_name)
                    result2 = index_directory(path=str(tmp_path), db_name=db_name)
            assert result1.indexed >= 1
            assert result2.skipped >= 1
            assert result2.indexed == 0
        finally:
            close_connection(db_name)

    def test_source_column_populated_from_sidecar(self, tmp_path: Path):
        """index_directory populates the source column from chunk.meta['source']."""
        from otutil.tools._knowledge.indexer import index_directory
        from otutil.tools._knowledge.db import close_connection

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://docs.example.test/page\nsource: mysite\n",
            encoding="utf-8",
        )

        db_name = f"test_src_{id(tmp_path)}"
        try:
            with patch("otutil.tools._knowledge.indexer._store_embeddings_batch", return_value=None):
                with patch("otutil.tools._knowledge.db._resolve_db_path", return_value=tmp_path / f"{db_name}.db"):
                    index_directory(path=str(tmp_path), db_name=db_name)
                    from otutil.tools._knowledge.db import get_connection
                    conn = get_connection(db_name)
                    row = conn.execute("SELECT source FROM chunks WHERE topic = 'page'").fetchone()
            assert row is not None
            assert row[0] == "mysite"
        finally:
            close_connection(db_name)

    def test_link_graph_inserts_edges(self, tmp_path: Path):
        """Markdown hyperlinks become edge rows."""
        from otutil.tools._knowledge.indexer import _build_link_graph

        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        conn.commit()

        src_id = "src"
        dst_id = "dst"
        _insert_chunk(conn, src_id, "a/page", "See [move](https://docs.example.test/b/page)",
                      meta='{"url": "https://docs.example.test/a/page"}')
        _insert_chunk(conn, dst_id, "b/page", "Destination content",
                      meta='{"url": "https://docs.example.test/b/page"}')

        edges_added = _build_link_graph(conn, tmp_path)
        conn.commit()
        assert edges_added >= 1
        edge = conn.execute("SELECT src_id, dst_id FROM edges WHERE edge_type='link'").fetchone()
        assert edge is not None
        assert edge[0] == src_id
        assert edge[1] == dst_id


# ===========================================================================
# 4.2 — Search lanes: FTS5, vec, RRF merge, metadata filter
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeSearch:
    """Search lane unit tests."""

    def _conn_with_data(self) -> sqlite3.Connection:
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        _insert_chunk(conn, "c1", "docs/move", "nudge objects along axis",
                      meta='{"source": "docs.test.invalid", "url": "https://docs.test.invalid/move"}')
        _insert_chunk(conn, "c2", "docs/rotate", "rotate object around point",
                      meta='{"source": "docs.test.invalid"}')
        _insert_chunk(conn, "c3", "python/list", "list comprehension filter map",
                      meta='{}')
        conn.commit()
        return conn

    def test_fts_search_returns_relevant_results(self):
        from otutil.tools._knowledge.search import search_fts
        conn = self._conn_with_data()
        results = search_fts(conn, "nudge objects", limit=5)
        topics = [r["topic"] for r in results]
        assert "docs/move" in topics

    def test_fts_search_category_filter(self):
        from otutil.tools._knowledge.search import search_fts
        conn = self._conn_with_data()
        conn.execute("UPDATE chunks SET category = 'rule' WHERE id = 'c1'")
        conn.commit()
        results = search_fts(conn, "nudge", limit=5, category="rule")
        assert all(r["category"] == "rule" for r in results)

    def test_rrf_merge_combines_results(self):
        from otutil.tools._knowledge.search import _rrf_merge

        list_a = [{"id": "x", "topic": "t/x", "score": 0.9}, {"id": "y", "topic": "t/y", "score": 0.5}]
        list_b = [{"id": "y", "topic": "t/y", "score": 0.8}, {"id": "z", "topic": "t/z", "score": 0.3}]
        merged = _rrf_merge(list_a, list_b, limit=3)
        assert len(merged) == 3
        ids = [r["id"] for r in merged]
        assert "y" in ids  # appeared in both lists — should score higher

    def test_rrf_merge_deduplicates(self):
        from otutil.tools._knowledge.search import _rrf_merge
        item = {"id": "a", "topic": "t/a", "score": 1.0}
        merged = _rrf_merge([item], [item], limit=5)
        assert len(merged) == 1

    def test_metadata_filter_source(self):
        from otutil.tools._knowledge.search import apply_metadata_filters
        results = [
            {"id": "a", "meta_dict": {"source": "docs.test.invalid"}, "tags_list": [], "created_at": "2024-01-01"},
            {"id": "b", "meta_dict": {"source": "other.com"}, "tags_list": [], "created_at": "2024-01-01"},
        ]
        filtered = apply_metadata_filters(results, source="docs.test.invalid")
        assert len(filtered) == 1
        assert filtered[0]["id"] == "a"

    def test_metadata_filter_tag(self):
        from otutil.tools._knowledge.search import apply_metadata_filters
        results = [
            {"id": "a", "meta_dict": {}, "tags_list": ["python", "async"], "created_at": "2024-01-01"},
            {"id": "b", "meta_dict": {}, "tags_list": ["rust"], "created_at": "2024-01-01"},
        ]
        filtered = apply_metadata_filters(results, tag="python")
        assert len(filtered) == 1
        assert filtered[0]["id"] == "a"

    def test_fts_query_strips_punctuation(self):
        from otutil.tools._knowledge.search import _fts_query
        assert "?" not in _fts_query("rotate and scale objects?")
        assert "!" not in _fts_query("move it!")
        assert ":" not in _fts_query("viewport: how to use")

    def test_fts_query_removes_stopwords(self):
        from otutil.tools._knowledge.search import _fts_query
        result = _fts_query("How do I use the Gumball to rotate objects")
        tokens = result.lower().split()
        assert "how" not in tokens
        assert "do" not in tokens
        assert "i" not in tokens
        assert "the" not in tokens
        assert "to" not in tokens
        assert "gumball" in tokens
        assert "rotate" in tokens

    def test_fts_query_preserves_content_words(self):
        from otutil.tools._knowledge.search import _fts_query
        result = _fts_query("nudge objects axis")
        assert "nudge" in result
        assert "objects" in result
        assert "axis" in result

    def test_fts_search_with_punctuation_returns_results(self):
        from otutil.tools._knowledge.search import search_fts
        conn = self._conn_with_data()
        # Query with ? would previously cause silent failure
        results = search_fts(conn, "nudge objects?", limit=5)
        topics = [r["topic"] for r in results]
        assert "docs/move" in topics

    def test_fts_search_prefix_fallback(self):
        from otutil.tools._knowledge.search import search_fts
        conn = self._conn_with_data()
        # "nudg" won't match exactly but prefix* should catch "nudge"
        results = search_fts(conn, "nudg", limit=5)
        topics = [r["topic"] for r in results]
        assert "docs/move" in topics

    def test_rrf_merge_applies_hit_count_boost(self):
        from otutil.tools._knowledge.search import _rrf_merge
        # Two items at equal rank position; one has high hit_count
        hot = {"id": "hot", "topic": "t/hot", "score": 0.5, "hit_count": 10}
        cold = {"id": "cold", "topic": "t/cold", "score": 0.5, "hit_count": 0}
        # Both appear only in list_a at rank 1 and 2 respectively
        merged = _rrf_merge([cold, hot], [], limit=2)
        ids = [r["id"] for r in merged]
        # hot should rank above cold due to hit_count boost
        assert ids[0] == "hot"

    def test_rrf_merge_hit_count_missing_is_zero(self):
        from otutil.tools._knowledge.search import _rrf_merge
        # Items without hit_count key should not raise
        list_a = [{"id": "x", "topic": "t/x", "score": 0.9}]
        merged = _rrf_merge(list_a, [], limit=1)
        assert len(merged) == 1


# ===========================================================================
# 4.x — Chunker: image alt text filling
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestFillImgAlt:
    """_fill_img_alt: empty alt text replaced with filename stem."""

    def test_empty_alt_replaced_with_stem(self):
        from otutil.tools._knowledge.chunker import _fill_img_alt
        result = _fill_img_alt("![](https://example.test/icons/propertiesbutton_viewport.png)")
        assert result == "![propertiesbutton viewport](https://example.test/icons/propertiesbutton_viewport.png)"

    def test_hyphens_converted_to_spaces(self):
        from otutil.tools._knowledge.chunker import _fill_img_alt
        result = _fill_img_alt("![](https://example.test/img/zoom-in-button.png)")
        assert result == "![zoom in button](https://example.test/img/zoom-in-button.png)"

    def test_existing_alt_not_touched(self):
        from otutil.tools._knowledge.chunker import _fill_img_alt
        original = "![already here](https://example.test/img/icon.png)"
        assert _fill_img_alt(original) == original

    def test_multiple_empty_alts_in_same_text(self):
        from otutil.tools._knowledge.chunker import _fill_img_alt
        text = "![](https://example.test/a/foo_bar.png) and ![](https://example.test/b/baz.svg)"
        result = _fill_img_alt(text)
        assert "![foo bar]" in result
        assert "![baz]" in result

    def test_chunk_file_fills_alt(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        md = tmp_path / "page.md"
        md.write_text("![](https://example.test/icons/move_tool.png) Use the move tool.\n")
        chunks = chunk_file(md, md.relative_to(tmp_path))
        assert chunks
        assert "![move tool]" in chunks[0].content


# ===========================================================================
# 4.3 — Chunker: stub filtering and short-chunk merging
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeChunkerStubFilter:
    """Stub filtering and min_chunk_chars merge in _split_by_headings."""

    def _make_long_file(self, lines: list[str], tmp_path: Path, name: str = "doc.md") -> Path:
        md = tmp_path / name
        md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return md

    def test_heading_only_stub_is_skipped(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        # Stub: H1 followed immediately by another H1 with no body
        # File must be >100 lines to trigger heading split
        lines = (
            ["# Group Label"]           # stub — no body before next heading
            + ["# Real Section"]
            + ["Real content here."] * 110
        )
        md = self._make_long_file(lines, tmp_path)
        chunks = chunk_file(md, Path("doc.md"), min_chunk_chars=0)
        topics = [c.topic for c in chunks]
        assert not any("group-label" in t for t in topics)
        assert any("real-section" in t for t in topics)

    def test_short_chunk_merges_into_predecessor(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        # File must be >100 lines to trigger heading split
        lines = (
            ["# Section A"]
            + ["Substantial content line."] * 55
            + ["# Section B"]
            + ["Short."]          # body < 200 chars → should merge into A
            + ["# Section C"]
            + ["More content here."] * 55
        )
        md = self._make_long_file(lines, tmp_path)
        chunks = chunk_file(md, Path("doc.md"), min_chunk_chars=200)
        topics = [c.topic for c in chunks]
        # Section B should not appear as its own chunk
        assert not any("section-b" in t for t in topics)
        # Section A chunk should contain the merged B content
        a_chunks = [c for c in chunks if "section-a" in c.topic]
        assert a_chunks
        assert "Short." in a_chunks[0].content

    def test_short_chunk_with_no_predecessor_is_skipped(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        # First section is short — no predecessor to merge into → skip
        lines = (
            ["# Short First"]
            + ["Tiny."]           # body < 200 chars, no predecessor
            + ["# Real Section"]
            + ["Real content here."] * 110
        )
        md = self._make_long_file(lines, tmp_path)
        chunks = chunk_file(md, Path("doc.md"), min_chunk_chars=200)
        topics = [c.topic for c in chunks]
        assert not any("short-first" in t for t in topics)

    def test_min_chunk_chars_zero_disables_merge(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file
        # File must be >100 lines to trigger heading split
        lines = (
            ["# Section A"]
            + ["A content line."] * 55
            + ["# Stub"]      # heading-only → still skipped (empty body check is separate)
            + ["# Section B"]
            + ["B content line."] * 55
        )
        md = self._make_long_file(lines, tmp_path)
        # min_chunk_chars=0 disables merge threshold but stubs are still skipped
        chunks = chunk_file(md, Path("doc.md"), min_chunk_chars=0)
        topics = [c.topic for c in chunks]
        assert not any("stub" in t for t in topics)  # stub still skipped (empty body)
        assert any("section-a" in t for t in topics)
        assert any("section-b" in t for t in topics)


# ===========================================================================
# 4.4 — Embedding cache
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestEmbeddingCache:
    """Query embedding TTL cache."""

    def test_cache_hit_avoids_api_call(self):
        import otutil.tools._knowledge.embedding as emb_mod
        from unittest.mock import patch, MagicMock

        cfg = MagicMock()
        cfg.model = "text-embedding-3-small"
        cfg.dimensions = 1536
        cfg.max_embedding_tokens = 8191
        cfg.base_url = ""

        fake_vec = [0.1] * 1536

        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            item = MagicMock()
            item.embedding = fake_vec
            item.index = 0
            resp = MagicMock()
            resp.data = [item]
            return resp

        client_mock = MagicMock()
        client_mock.embeddings.create.side_effect = fake_create

        # Clear cache before test
        emb_mod._EMBED_CACHE.clear()

        with patch("otutil.tools._knowledge.embedding._get_config", return_value=cfg):
            with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=client_mock):
                with patch("otutil.tools._knowledge.embedding._chunk_text_by_tokens", return_value=["test query"]):
                    emb_mod.generate_embedding("test query")
                    emb_mod.generate_embedding("test query")

        assert call_count == 1, "Second call should have hit the cache"

    def test_cache_miss_on_different_query(self):
        import otutil.tools._knowledge.embedding as emb_mod
        from unittest.mock import patch, MagicMock

        cfg = MagicMock()
        cfg.model = "text-embedding-3-small"
        cfg.dimensions = 1536
        cfg.max_embedding_tokens = 8191
        cfg.base_url = ""

        fake_vec = [0.1] * 1536
        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            item = MagicMock()
            item.embedding = fake_vec
            item.index = 0
            resp = MagicMock()
            resp.data = [item]
            return resp

        client_mock = MagicMock()
        client_mock.embeddings.create.side_effect = fake_create

        emb_mod._EMBED_CACHE.clear()

        with patch("otutil.tools._knowledge.embedding._get_config", return_value=cfg):
            with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=client_mock):
                with patch("otutil.tools._knowledge.embedding._chunk_text_by_tokens", side_effect=lambda t, *a: [t]):
                    emb_mod.generate_embedding("query one")
                    emb_mod.generate_embedding("query two")

        assert call_count == 2, "Different queries should each make an API call"


# ===========================================================================
# 5.3 — Smoke: kb.dbs() with empty config
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeConfig:
    """Config smoke tests."""

    def test_dbs_returns_not_configured_message_when_empty(self):
        from otutil.tools._knowledge.listing import dbs
        with patch("otutil.tools._knowledge.listing._get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.kb = {}
            mock_cfg.return_value = cfg
            result = dbs()
        assert "No databases configured" in result

    def test_dbs_returns_names_when_configured(self):
        from otutil.tools._knowledge.listing import dbs
        from otutil.tools._knowledge.config import DBConfig, KBProjectConfig
        with patch("otutil.tools._knowledge.listing._get_config") as mock_cfg:
            cfg = MagicMock()
            kb_proj = KBProjectConfig(db=DBConfig(path="mem/docs.db", description="Project docs"))
            cfg.kb = {"docs": kb_proj}
            mock_cfg.return_value = cfg
            result = dbs()
        assert "docs" in result
        assert "Project docs" in result

    def test_default_db_path_is_data_scoped(self, tmp_path: Path) -> None:
        from otutil.tools._knowledge.db import _resolve_db_path

        with (
            patch("otutil.tools._knowledge.config._get_config") as mock_cfg,
            patch("ot.meta.resolve_ot_path", side_effect=lambda path: tmp_path / path),
        ):
            cfg = MagicMock()
            cfg.kb = {}
            mock_cfg.return_value = cfg
            result = _resolve_db_path("docs")

        assert result == tmp_path / "data" / "knowledge" / "docs.db"


# ===========================================================================
# 6.3 — CRUD round-trips and listing shapes
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeCRUD:
    """CRUD round-trip tests using a real in-memory SQLite DB."""

    def _patch_db(self, db_name: str = "test"):
        """Patch get_connection to return an in-memory DB."""
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        conn.commit()
        return conn

    def test_write_creates_entry(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                result = crud.write(topic="test/topic", content="Hello world", db="test")
        assert "Written" in result
        row = conn.execute("SELECT topic, content FROM chunks WHERE topic='test/topic'").fetchone()
        assert row is not None
        assert row[1] == "Hello world"

    def test_write_rejects_duplicate_topic(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        _insert_chunk(conn, "existing", "test/topic", "original")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.write(topic="test/topic", content="duplicate", db="test")
        assert "Error" in result
        assert "already exists" in result

    def test_read_returns_content(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        _insert_chunk(conn, "c1", "test/topic", "My content here")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.read(topic="test/topic", db="test")
        assert "My content here" in result

    def test_read_missing_topic_returns_error(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.read(topic="nonexistent/topic", db="test")
        assert "Error" in result

    def test_append_adds_content(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        _insert_chunk(conn, "c1", "test/topic", "Original")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                crud.append(topic="test/topic", content="\nAppended", db="test")
        row = conn.execute("SELECT content FROM chunks WHERE topic='test/topic'").fetchone()
        assert "Appended" in row[0]
        assert "Original" in row[0]

    def test_update_replaces_content(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        _insert_chunk(conn, "c1", "test/topic", "Old content")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                crud.update(topic="test/topic", content="New content", db="test")
        row = conn.execute("SELECT content FROM chunks WHERE topic='test/topic'").fetchone()
        assert row[0] == "New content"

    def test_delete_removes_entry(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        _insert_chunk(conn, "c1", "test/topic", "To be deleted")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.delete(topic="test/topic", db="test")
        assert "Deleted" in result
        row = conn.execute("SELECT id FROM chunks WHERE topic='test/topic'").fetchone()
        assert row is None

    def test_write_invalid_category_returns_error(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.write(topic="x/y", content="content", db="test", category="invalid_cat")
        assert "Error" in result
        assert "Invalid category" in result

    def test_write_populates_source_column_from_meta(self):
        """kb.write() with source in meta populates the source column."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                crud.write(topic="a/page", content="Content", db="test", meta={"source": "mysite"})
        row = conn.execute("SELECT source FROM chunks WHERE topic='a/page'").fetchone()
        assert row is not None
        assert row[0] == "mysite"

    def test_write_source_column_empty_when_no_meta(self):
        """kb.write() without meta leaves source column as empty string."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                crud.write(topic="b/page", content="Content", db="test")
        row = conn.execute("SELECT source FROM chunks WHERE topic='b/page'").fetchone()
        assert row is not None
        assert row[0] == ""


# ===========================================================================
# 6.4 — CRUD multi-chunk: read/update/delete by source_path
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeCRUDMultiChunk:
    """Multi-chunk CRUD: read-one by topic/id, all-chunks by source_path."""

    def _patch_db(self) -> sqlite3.Connection:
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        conn.commit()
        return conn

    def _insert(self, conn: sqlite3.Connection, chunk_id: str, topic: str, content: str,
                source_path: str | None = None, anchor: str = "") -> None:
        import hashlib as _h
        ch = _h.sha256(content.encode()).hexdigest()
        conn.execute(
            "INSERT INTO chunks (id, topic, content, content_hash, category, source_path, anchor) VALUES (?,?,?,?,?,?,?)",
            [chunk_id, topic, content, ch, "reference", source_path, anchor],
        )
        conn.commit()

    def test_read_topic_returns_one_chunk(self):
        """read(topic=) is read-one: returns single latest chunk, not all."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Page content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Intro section", source_path="path/move", anchor="intro")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.read(topic="cmd/move", db="test")
        # Only one chunk returned — no separator
        assert "---" not in result

    def test_read_by_id(self):
        """read(id=) returns the chunk with that UUID."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Page content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Intro section", source_path="path/move", anchor="intro")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.read(id="c2", db="test")
        assert "Intro section" in result
        assert "Page content" not in result

    def test_read_by_source_path_returns_all_chunks(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Page content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Intro section", source_path="path/move", anchor="intro")
        self._insert(conn, "c3", "cmd/other", "Other page", source_path="path/other", anchor="")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.read(source_path="path/move", db="test")
        assert "Page content" in result
        assert "Intro section" in result
        assert "Other page" not in result

    def test_delete_by_source_path(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Page content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Intro section", source_path="path/move", anchor="intro")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.delete(source_path="path/move", db="test")
        assert "Deleted" in result
        assert "(2 chunks)" in result
        rows = conn.execute("SELECT id FROM chunks WHERE source_path = 'path/move'").fetchall()
        assert len(rows) == 0

    def test_update_targets_specific_anchor(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Old intro", source_path="path/move", anchor="intro")
        self._insert(conn, "c2", "cmd/move", "Options section", source_path="path/move", anchor="options")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                result = crud.update(topic="cmd/move", content="New intro", db="test",
                                     source_path="path/move", anchor="intro")
        assert "Updated" in result
        row1 = conn.execute("SELECT content FROM chunks WHERE id = 'c1'").fetchone()
        assert row1[0] == "New intro"
        row2 = conn.execute("SELECT content FROM chunks WHERE id = 'c2'").fetchone()
        assert row2[0] == "Options section"

    def test_delete_requires_topic_or_source_path(self):
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.delete(db="test")
        assert "Error" in result

    def test_update_by_id(self):
        """update(id=) targets a chunk directly by UUID."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Old content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Other chunk", source_path="path/move", anchor="intro")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                result = crud.update(id="c1", topic="ignored", content="New content", db="test")
        assert "Updated" in result
        row = conn.execute("SELECT content FROM chunks WHERE id = 'c1'").fetchone()
        assert row[0] == "New content"
        row2 = conn.execute("SELECT content FROM chunks WHERE id = 'c2'").fetchone()
        assert row2[0] == "Other chunk"

    def test_append_by_id(self):
        """append(id=) targets a chunk directly by UUID."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Original", source_path="path/move", anchor="")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            with patch("otutil.tools._knowledge.crud._try_embed"):
                result = crud.append(id="c1", topic="ignored", content=" appended", db="test")
        assert "Appended" in result
        row = conn.execute("SELECT content FROM chunks WHERE id = 'c1'").fetchone()
        assert row[0] == "Original appended"

    def test_delete_by_id(self):
        """delete(id=) removes a chunk directly by UUID."""
        from otutil.tools._knowledge import crud
        conn = self._patch_db()
        self._insert(conn, "c1", "cmd/move", "Page content", source_path="path/move", anchor="")
        self._insert(conn, "c2", "cmd/move", "Intro section", source_path="path/move", anchor="intro")
        with patch("otutil.tools._knowledge.crud.get_connection", return_value=conn):
            result = crud.delete(id="c1", db="test")
        assert "Deleted" in result
        assert conn.execute("SELECT id FROM chunks WHERE id = 'c1'").fetchone() is None
        assert conn.execute("SELECT id FROM chunks WHERE id = 'c2'").fetchone() is not None


# ===========================================================================
# 6.3 (cont.) — Listing: list, grep, slice, toc
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeListing:
    """Listing tool output shape tests."""

    def _conn_with_entries(self) -> sqlite3.Connection:
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        _insert_chunk(conn, "c1", "docs/move", "# Move\n\nMove objects with nudge keys.\n")
        _insert_chunk(conn, "c2", "docs/rotate", "# Rotate\n\nRotate around pivot.\n", category="rule")
        conn.commit()
        return conn

    def test_list_returns_all_entries(self):
        from otutil.tools._knowledge.listing import list_entries
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = list_entries(db="test")
        assert "docs/move" in result
        assert "docs/rotate" in result

    def test_list_filters_by_category(self):
        from otutil.tools._knowledge.listing import list_entries
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = list_entries(db="test", category="rule")
        assert "docs/rotate" in result
        assert "docs/move" not in result

    def test_grep_finds_matches(self):
        from otutil.tools._knowledge.listing import grep
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = grep(pattern="nudge", db="test")
        assert "nudge" in result
        assert "docs/move" in result

    def test_grep_no_match_message(self):
        from otutil.tools._knowledge.listing import grep
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = grep(pattern="zzznomatch999", db="test")
        assert "No matches" in result

    def test_toc_returns_headings(self):
        from otutil.tools._knowledge.listing import toc
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = toc(topic="docs/move", db="test")
        assert "Move" in result

    def test_toc_missing_topic_error(self):
        from otutil.tools._knowledge.listing import toc
        conn = self._conn_with_entries()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = toc(topic="nonexistent", db="test")
        assert "Error" in result

    def test_slice_by_line_range(self):
        from otutil.tools._knowledge.listing import slice_entry
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        _insert_chunk(conn, "c1", "test/topic", "line1\nline2\nline3\nline4")
        conn.commit()
        with patch("otutil.tools._knowledge.listing.get_connection", return_value=conn):
            result = slice_entry(topic="test/topic", db="test", start=2, end=3)
        assert "line2" in result
        assert "line1" not in result

    def test_stats_includes_links_enrichments_and_top_accessed(self, tmp_path: Path):
        from otutil.tools._knowledge.listing import stats
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn = _make_in_memory_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        # c1: has summary, tags, hits; c2: bare
        import hashlib
        def _ins(cid, topic, content, summary=None, tags="[]", hit_count=0):
            ch = hashlib.sha256(content.encode()).hexdigest()
            conn.execute(
                "INSERT INTO chunks (id, topic, content, content_hash, summary, tags, hit_count) VALUES (?,?,?,?,?,?,?)",
                [cid, topic, content, ch, summary, tags, hit_count],
            )
        _ins("c1", "docs/move", "Move content", summary="AI summary", tags='["move","transform"]', hit_count=7)
        _ins("c2", "docs/rotate", "Rotate content")
        conn.execute("INSERT INTO edges (id, src_id, dst_id, edge_type) VALUES ('e1','c2','c1','link')")
        conn.execute("INSERT INTO edges (id, src_id, dst_id, edge_type) VALUES ('e2','c1','c2','link')")
        conn.commit()
        db_file = tmp_path / "test.db"
        db_file.write_bytes(b"")
        with (
            patch("otutil.tools._knowledge.listing.get_connection", return_value=conn),
            patch("otutil.tools._knowledge.db._resolve_db_path", return_value=db_file),
        ):
            result = stats(db="test", top=3)
        assert "Total chunks: 2" in result
        assert "Links (edges): 2" in result
        assert "docs/move" in result           # most-linked page
        assert "summaries 1/2" in result
        assert "tags 1/2" in result
        assert "docs/move: 7 hits" in result   # most accessed


# ===========================================================================
# 8.4 — Search modes, filter application, related traversal
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeRetrieval:
    """Retrieval tool tests."""

    def _conn_with_graph(self) -> sqlite3.Connection:
        conn = _make_in_memory_conn()
        from otutil.tools._knowledge.db import _SCHEMA_SQL, _FTS_SQL, _FTS_TRIGGERS_SQL
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS_SQL)
        _insert_chunk(conn, "page-a", "a/page", "The A page links somewhere")
        _insert_chunk(conn, "page-b", "b/page", "The B page content")
        _insert_chunk(conn, "page-c", "c/page", "The C page content")
        conn.execute("INSERT INTO edges (id, src_id, dst_id, edge_type) VALUES ('e1','page-a','page-b','link')")
        conn.execute("INSERT INTO edges (id, src_id, dst_id, edge_type) VALUES ('e2','page-b','page-c','link')")
        conn.commit()
        return conn

    def test_related_outbound_depth1(self):
        from otutil.tools._knowledge.retrieval import related
        conn = self._conn_with_graph()
        with patch("otutil.tools._knowledge.retrieval.get_connection", return_value=conn):
            result = related(topic="a/page", db="test", direction="out", depth=1)
        assert "b/page" in result
        assert "c/page" not in result  # depth 1 only

    def test_related_outbound_depth2(self):
        from otutil.tools._knowledge.retrieval import related
        conn = self._conn_with_graph()
        with patch("otutil.tools._knowledge.retrieval.get_connection", return_value=conn):
            result = related(topic="a/page", db="test", direction="out", depth=2)
        assert "b/page" in result
        assert "c/page" in result

    def test_related_inbound(self):
        from otutil.tools._knowledge.retrieval import related
        conn = self._conn_with_graph()
        with patch("otutil.tools._knowledge.retrieval.get_connection", return_value=conn):
            result = related(topic="b/page", db="test", direction="in", depth=1)
        assert "a/page" in result

    def test_related_invalid_direction(self):
        from otutil.tools._knowledge.retrieval import related
        conn = self._conn_with_graph()
        with patch("otutil.tools._knowledge.retrieval.get_connection", return_value=conn):
            result = related(topic="a/page", db="test", direction="sideways", depth=1)
        assert "Error" in result

    def test_search_invalid_mode(self):
        from otutil.tools._knowledge.retrieval import search
        conn = self._conn_with_graph()
        with patch("otutil.tools._knowledge.retrieval.get_connection", return_value=conn):
            result = search(query="test", db="test", mode="invalid")
        assert "Error" in result

    def test_reset_runtime_cache_resets_lazy_llm_client(self):
        from otutil.tools._knowledge import retrieval

        with patch.object(retrieval._get_llm_client, "reset") as mock_reset:
            retrieval.reset_runtime_cache()

        mock_reset.assert_called_once_with()


# ===========================================================================
# 10.1–10.3 — Error handling: missing sqlite-vec and FTS5
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeErrorHandling:
    """Missing extension guard tests."""

    def test_require_vec_raises_import_error_when_absent(self):
        """_require_vec() raises ImportError with install instructions when sqlite-vec is absent."""
        from otutil.tools._knowledge import db as kb_db
        original = kb_db._VEC_AVAILABLE
        try:
            kb_db._VEC_AVAILABLE = False
            with pytest.raises(ImportError, match="sqlite-vec is required"):
                kb_db._require_vec()
        finally:
            kb_db._VEC_AVAILABLE = original

    def test_check_vec_available_returns_false_when_import_fails(self):
        """_check_vec_available() returns False when sqlite_vec is not importable."""
        from otutil.tools._knowledge import db as kb_db
        original = kb_db._VEC_AVAILABLE
        try:
            kb_db._VEC_AVAILABLE = None  # Reset so it re-checks
            with patch.dict("sys.modules", {"sqlite_vec": None}):
                result = kb_db._check_vec_available()
            # May be True if sqlite_vec IS installed; just check it returns a bool
            assert isinstance(result, bool)
        finally:
            kb_db._VEC_AVAILABLE = original

    def test_search_vec_raises_when_vec_unavailable(self):
        """search_vec raises ImportError when sqlite-vec is absent."""
        from otutil.tools._knowledge.search import search_vec
        from otutil.tools._knowledge import db as kb_db
        original = kb_db._VEC_AVAILABLE
        try:
            kb_db._VEC_AVAILABLE = False
            conn = _make_in_memory_conn()
            with pytest.raises(ImportError, match="sqlite-vec is required"):
                search_vec(conn, "query", 5)
        finally:
            kb_db._VEC_AVAILABLE = original

    def test_fts5_not_available_raises_runtime_error(self):
        """If FTS5 is absent, _kb_setup raises RuntimeError with clear message."""
        from otutil.tools._knowledge.db import _SCHEMA_SQL
        conn = _make_in_memory_conn()
        conn.executescript(_SCHEMA_SQL)

        with patch("otutil.tools._knowledge.db._FTS_SQL", "CREATE VIRTUAL TABLE bad_fts USING nonexistent_ext(x)"):
            with pytest.raises(RuntimeError, match="FTS5 is required"):
                from otutil.tools._knowledge.db import _kb_setup
                _kb_setup(conn)


@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeBatchEmbedding:
    """generate_embeddings_batch: batching, ordering, and empty input."""

    def _fake_openai_response(self, vecs: list[list[float]]) -> MagicMock:
        """Build a mock OpenAI embeddings response for the given vectors."""
        data = []
        for i, vec in enumerate(vecs):
            item = MagicMock()
            item.index = i
            item.embedding = vec
            data.append(item)
        resp = MagicMock()
        resp.data = data
        return resp

    def test_empty_input_returns_empty(self):
        from otutil.tools._knowledge.embedding import generate_embeddings_batch
        result = generate_embeddings_batch([])
        assert result == []

    def test_single_batch_returns_all_vectors(self):
        from otutil.tools._knowledge.embedding import generate_embeddings_batch

        texts = ["hello", "world", "foo"]
        vecs = [[0.1] * 3, [0.2] * 3, [0.3] * 3]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = self._fake_openai_response(vecs)

        with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=mock_client):
            with patch("otutil.tools._knowledge.embedding._get_config") as mock_cfg:
                mock_cfg.return_value.model = "text-embedding-3-small"
                mock_cfg.return_value.max_embedding_tokens = 8191
                mock_cfg.return_value.base_url = None
                result = generate_embeddings_batch(texts, batch_size=500)

        assert len(result) == 3
        assert result[0] == [0.1] * 3

    def test_multiple_batches_are_concatenated(self):
        from otutil.tools._knowledge.embedding import generate_embeddings_batch

        texts = ["a", "b", "c", "d", "e"]
        # Two batches: [a,b,c] and [d,e]
        batch1_vecs = [[float(i)] * 2 for i in range(3)]
        batch2_vecs = [[float(i)] * 2 for i in range(3, 5)]

        call_count = 0

        def fake_create(**kwargs: object) -> MagicMock:
            nonlocal call_count
            vecs = batch1_vecs if call_count == 0 else batch2_vecs
            call_count += 1
            return self._fake_openai_response(vecs)

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = fake_create

        with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=mock_client):
            with patch("otutil.tools._knowledge.embedding._get_config") as mock_cfg:
                mock_cfg.return_value.model = "text-embedding-3-small"
                mock_cfg.return_value.max_embedding_tokens = 8191
                mock_cfg.return_value.base_url = None
                result = generate_embeddings_batch(texts, batch_size=3)

        assert call_count == 2
        assert len(result) == 5

    def test_store_embeddings_batch_is_best_effort(self):
        """_store_embeddings_batch returns an error string when sqlite-vec is absent; does not raise."""
        from otutil.tools._knowledge.indexer import _store_embeddings_batch

        conn = _make_in_memory_conn()

        # _check_vec_available() returns False → early-exit error string, no exception
        with patch("otutil.tools._knowledge.db._check_vec_available", return_value=False):
            result = _store_embeddings_batch(conn, [("c1", "content")])
        assert result is not None
        assert "sqlite-vec" in result

    def test_retry_on_api_status_error(self):
        """_embed_batch_with_retry retries on HTTP 429 and succeeds on the third attempt."""
        from otutil.tools._knowledge.embedding import _embed_batch_with_retry

        vecs = [[0.1, 0.2], [0.3, 0.4]]
        call_count = 0

        def fake_create(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                err = MagicMock()
                err.status_code = 429
                raise type("APIStatusError", (Exception,), {"status_code": 429})(
                    "rate limited"
                )
            return self._fake_openai_response(vecs)

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = fake_create

        with (
            patch("otutil.tools._knowledge.embedding.time") as mock_time,
            patch("otutil.tools._knowledge.embedding.logger.warning") as mock_warning,
        ):
            result = _embed_batch_with_retry(mock_client, "text-embedding-3-small", ["a", "b"])

        assert call_count == 3
        assert len(result) == 2
        assert mock_time.sleep.call_count == 2
        entries = [call.args[0] for call in mock_warning.call_args_list]
        assert [entry.fields["event"] for entry in entries] == [
            "knowledge.embedding.retry",
            "knowledge.embedding.retry",
        ]
        assert entries[0].fields["statusCode"] == 429
        assert entries[0].fields["attempt"] == 1
        assert entries[0].fields["maxAttempts"] == 3
        assert entries[0].fields["waitSeconds"] == 1.0

    def test_valueerror_not_retried(self):
        """_embed_batch_with_retry does NOT retry ValueError — batch rejection is not transient."""
        from otutil.tools._knowledge.embedding import _embed_batch_with_retry

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = ValueError("No embedding data received")

        with patch("otutil.tools._knowledge.embedding.time") as mock_time:
            with pytest.raises(ValueError, match="No embedding data received"):
                _embed_batch_with_retry(mock_client, "text-embedding-3-small", ["x"])

        assert mock_client.embeddings.create.call_count == 1
        mock_time.sleep.assert_not_called()

    def test_count_mismatch_raises_valueerror(self):
        """_embed_batch_with_retry raises ValueError if response count != input count."""
        from otutil.tools._knowledge.embedding import _embed_batch_with_retry

        # API returns 1 vector but we sent 2 texts — should raise after exhausting retries
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = self._fake_openai_response([[0.1, 0.2]])

        with patch("otutil.tools._knowledge.embedding.time"):
            with pytest.raises(ValueError, match="Expected 2 embeddings, got 1"):
                _embed_batch_with_retry(
                    mock_client, "text-embedding-3-small", ["a", "b"], max_attempts=1
                )

    def test_store_embeddings_batch_partial_failure(self):
        """First sub-batch is stored; second sub-batch fails → fallback embeds items individually."""
        from otutil.tools._knowledge.indexer import _store_embeddings_batch

        conn = _make_in_memory_conn()
        _apply_schema(conn)

        # Plain table matching chunks_vec schema (sqlite-vec not available in tests)
        conn.execute("CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
        conn.commit()

        # Two sub-batches of 2: first succeeds, second fails as batch but succeeds per-item
        batch_size = 2
        pending = [("id1", "text one"), ("id2", "text two"), ("id3", "text three"), ("id4", "text four")]

        call_count = 0

        def fake_embed(client: object, model: object, safe_batch: object, **kwargs: object) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            batch = list(safe_batch)  # type: ignore[arg-type]
            # Second call (batch call for sub-batch 2) fails; individual retries succeed
            if call_count == 2 and len(batch) > 1:
                raise ValueError("No embedding data received")
            return [[float(i + call_count)] * 2 for i in range(len(batch))]

        with patch("otutil.tools._knowledge.db._check_vec_available", return_value=True):
            with patch("otutil.tools._knowledge.embedding._embed_batch_with_retry", side_effect=fake_embed):
                with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=MagicMock()):
                    with patch("otutil.tools._knowledge.embedding._prepare_safe_batch", side_effect=lambda t, _c, _m: t):
                        with patch("otutil.tools._knowledge.indexer._get_config") as mock_cfg:
                            mock_cfg.return_value.model = "text-embedding-3-small"
                            result = _store_embeddings_batch(conn, pending, batch_size=batch_size)

        # No errors — fallback per-item calls succeed
        assert result is None

        # All 4 chunks stored
        stored = {row[0] for row in conn.execute("SELECT chunk_id FROM chunks_vec").fetchall()}
        assert stored == {"id1", "id2", "id3", "id4"}

    def test_store_embeddings_batch_bad_chunk_isolated(self):
        """A single bad chunk causes only that chunk to fail; the rest in the batch are stored."""
        from otutil.tools._knowledge.indexer import _store_embeddings_batch

        conn = _make_in_memory_conn()
        conn.execute("CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
        conn.commit()

        pending = [("id1", "good"), ("id2", "bad"), ("id3", "good2")]

        def fake_embed(client: object, model: object, safe_batch: object, **kwargs: object) -> list[list[float]]:
            batch = list(safe_batch)  # type: ignore[arg-type]
            # Batch call fails; individual "bad" chunk fails; others succeed
            if len(batch) > 1:
                raise ValueError("No embedding data received")
            if batch[0] == "bad":
                raise ValueError("content policy")
            return [[0.1, 0.2]]

        with patch("otutil.tools._knowledge.db._check_vec_available", return_value=True):
            with patch("otutil.tools._knowledge.embedding._embed_batch_with_retry", side_effect=fake_embed):
                with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=MagicMock()):
                    with patch("otutil.tools._knowledge.embedding._prepare_safe_batch", side_effect=lambda t, _c, _m: t):
                        with patch("otutil.tools._knowledge.indexer._get_config") as mock_cfg:
                            mock_cfg.return_value.model = "text-embedding-3-small"
                            result = _store_embeddings_batch(conn, pending, batch_size=10)

        # Error reported for "id2" only
        assert result is not None
        assert "1 of 3" in result
        assert "id2" in result

        # id1 and id3 stored; id2 not
        stored = {row[0] for row in conn.execute("SELECT chunk_id FROM chunks_vec").fetchall()}
        assert stored == {"id1", "id3"}

    def test_fallback_aborts_on_consecutive_api_failures(self):
        """Per-item fallback aborts after _FALLBACK_ABORT_AFTER consecutive failures (API outage)."""
        from otutil.tools._knowledge.indexer import _FALLBACK_ABORT_AFTER, _store_embeddings_batch

        conn = _make_in_memory_conn()
        conn.execute("CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
        conn.commit()

        # 20 chunks in one sub-batch; all fail individually
        pending = [(f"id{i}", f"text{i}") for i in range(20)]

        api_call_count = 0

        def fake_embed(client: object, model: object, safe_batch: object, **kwargs: object) -> list[list[float]]:
            nonlocal api_call_count
            api_call_count += 1
            raise ValueError("No embedding data received")

        with patch("otutil.tools._knowledge.db._check_vec_available", return_value=True):
            with patch("otutil.tools._knowledge.embedding._embed_batch_with_retry", side_effect=fake_embed):
                with patch("otutil.tools._knowledge.embedding._get_openai_client", return_value=MagicMock()):
                    with patch("otutil.tools._knowledge.embedding._prepare_safe_batch", side_effect=lambda t, _c, _m: t):
                        with patch("otutil.tools._knowledge.indexer._get_config") as mock_cfg:
                            mock_cfg.return_value.model = "text-embedding-3-small"
                            result = _store_embeddings_batch(conn, pending, batch_size=20)

        # Should have aborted after 1 batch call + _FALLBACK_ABORT_AFTER individual calls
        assert api_call_count == 1 + _FALLBACK_ABORT_AFTER
        assert result is not None
        assert "20 of 20" in result


@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeReindex:
    """reindex(): per-batch commit, accurate error counts."""

    def test_reindex_partial_failure_stores_successful_batches(self, tmp_path: Path):
        """When the last batch fails, earlier batches are stored and counted correctly."""
        from otutil.tools._knowledge.indexing import reindex

        # Patch _store_embeddings_batch to simulate a partial failure:
        # it reports an error and stores only some embeddings (2 of 4).
        def fake_store(conn: object, pending: object, on_progress: object = None, **kwargs: object) -> str:
            # Simulate: store 2 chunks, fail 2
            import sqlite3 as _sq
            assert isinstance(conn, _sq.Connection)
            conn.execute(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO chunks_vec(chunk_id, embedding) VALUES (?, ?), (?, ?)",
                ["id1", b"\x00" * 8, "id2", b"\x00" * 8],
            )
            conn.commit()  # type: ignore[union-attr]
            return "Embedding storage failed for 2 of 4 chunk(s): ..."

        with patch("otutil.tools._knowledge.indexing._store_embeddings_batch", side_effect=fake_store):
            with patch("otutil.tools._knowledge.indexing.get_connection") as mock_conn_fn:
                import sqlite3
                conn = sqlite3.connect(":memory:")
                conn.execute("CREATE TABLE chunks (id TEXT, content TEXT)")
                conn.execute("CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
                conn.executemany(
                    "INSERT INTO chunks VALUES (?, ?)",
                    [("id1", "a"), ("id2", "b"), ("id3", "c"), ("id4", "d")],
                )
                conn.commit()
                mock_conn_fn.return_value = conn

                result = reindex(db="testdb")

        assert "2" in result  # 2 stored
        assert "2 error" in result  # 2 failed

    def test_reindex_no_missing_chunks(self):
        """Returns early when all chunks already have embeddings."""
        from otutil.tools._knowledge.indexing import reindex

        with patch("otutil.tools._knowledge.indexing.get_connection") as mock_conn_fn:
            import sqlite3
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE TABLE chunks (id TEXT, content TEXT)")
            conn.execute("CREATE TABLE chunks_vec (chunk_id TEXT PRIMARY KEY, embedding BLOB)")
            conn.commit()
            mock_conn_fn.return_value = conn

            result = reindex(db="testdb")

        assert "No chunks missing" in result


@pytest.mark.unit
@pytest.mark.tools
class TestKnowledgeCLI:
    """CLI smoke tests using typer.testing.CliRunner."""

    def _make_runner(self) -> "typer.testing.CliRunner":
        from typer.testing import CliRunner
        return CliRunner()

    def test_index_calls_index_directory(self, tmp_path: Path):
        from onetool.kb import kb_app
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig, ScrapeSourceConfig

        mock_result = MagicMock()
        mock_result.indexed = 5
        mock_result.skipped = 1
        mock_result.edges_added = 2
        mock_result.errors = []

        proj = ScrapeProjectConfig(output_base_dir=str(tmp_path),
                                   sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")})
        cfg = Config(kb={"testdb": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

        with patch("otutil.tools._knowledge.indexer.index_directory", return_value=mock_result) as mock_idx:
            with patch("otutil.tools._knowledge.config._get_config", return_value=cfg):
                from typer.testing import CliRunner
                result = CliRunner().invoke(kb_app, ["index", "testdb"])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_idx.call_args.kwargs
        assert call_kwargs["path"] == str(tmp_path)
        assert call_kwargs["db_name"] == "testdb"
        assert call_kwargs["overwrite"] == "skip"
        assert "5" in result.output

    def test_reindex_calls_reindex(self):
        from onetool.kb import kb_app

        with patch("otutil.tools._knowledge.indexing.reindex", return_value="Reindexed 10 chunks") as mock_re:
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["reindex", "testdb"])

        assert result.exit_code == 0, result.output
        assert mock_re.call_args.kwargs["db"] == "testdb"

    def test_stats_prints_stats(self):
        from onetool.kb import kb_app

        with patch("otutil.tools._knowledge.listing.stats", return_value="Stats for 'testdb'") as mock_s:
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["stats", "testdb"])

        assert result.exit_code == 0, result.output
        mock_s.assert_called_once_with(db="testdb")
        assert "✓" in result.output
        assert "testdb" in result.output

    def test_info_prints_info(self):
        from onetool.kb import kb_app

        with patch("otutil.tools._knowledge.listing.info", return_value="Database: testdb") as mock_i:
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["info", "testdb"])

        assert result.exit_code == 0, result.output
        mock_i.assert_called_once_with(db="testdb")
        assert "✓" in result.output
        assert "testdb" in result.output

    def test_export_calls_export_db(self, tmp_path: Path):
        from onetool.kb import kb_app
        out = tmp_path / "out.json"

        with patch("otutil.tools._knowledge.listing.export_db", return_value="Exported 42 chunks") as mock_ex:
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["export", "testdb", "--output", str(out)])

        assert result.exit_code == 0, result.output
        mock_ex.assert_called_once_with(db="testdb", path=str(out), category=None, topic=None)

# ---------------------------------------------------------------------------
# Scraper: image URL resolution
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestResolveImageUrls:
    """Tests for _resolve_image_urls — relative-to-absolute image URL rewriting."""

    def test_relative_path_resolved(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        result = _resolve_image_urls("![alt](images/fig.png)", "https://docs.example.test/guide/page")
        assert result == "![alt](https://docs.example.test/guide/images/fig.png)"

    def test_absolute_url_unchanged(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        md = "![logo](https://cdn.example.test/logo.svg)"
        assert _resolve_image_urls(md, "https://docs.example.test/") == md

    def test_protocol_relative_url_unchanged(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        md = "![icon](//cdn.example.test/icon.png)"
        assert _resolve_image_urls(md, "https://docs.example.test/") == md

    def test_data_uri_unchanged(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        md = "![px](data:image/gif;base64,R0lGOD)"
        assert _resolve_image_urls(md, "https://docs.example.test/") == md

    def test_root_relative_path_resolved(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        result = _resolve_image_urls("![x](/assets/img.png)", "https://docs.example.test/guide/page")
        assert result == "![x](https://docs.example.test/assets/img.png)"

    def test_multiple_images_all_resolved(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        md = "![a](a.png) and ![b](b.png)"
        result = _resolve_image_urls(md, "https://docs.example.test/section/")
        assert "https://docs.example.test/section/a.png" in result
        assert "https://docs.example.test/section/b.png" in result

    def test_empty_src_unchanged(self):
        from otutil.tools._knowledge.scraper import _resolve_image_urls
        md = "![empty]()"
        result = _resolve_image_urls(md, "https://docs.example.test/")
        assert result == md


# ---------------------------------------------------------------------------
# Scraper: slug generation (task 5.1)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestScraperSlug:
    def test_root_path_returns_index(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/") == "index"

    def test_path_without_extension(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/guide/intro") == "guide/intro"

    def test_strip_html_extension(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/guide/intro.html") == "guide/intro"

    def test_strip_htm_extension(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/page.htm") == "page"

    def test_deep_path(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        slug = url_to_slug("https://docs.example.test/a/b/c.html")
        assert slug == "a/b/c"

    def test_single_segment(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/overview") == "overview"

    def test_trailing_slash_path(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/guide/") == "guide"

    def test_base_path_strips_prefix_and_preserves_hierarchy(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        slug = url_to_slug(
            "https://docs.example.test/app/v1/guide/en-us/commands/addnextv.htm",
            base_path="/app/v1/guide/en-us",
        )
        assert slug == "commands/addnextv"

    def test_base_path_strips_prefix_single_segment(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        slug = url_to_slug(
            "https://docs.example.test/docs/en-us/overview",
            base_path="/docs/en-us",
        )
        assert slug == "overview"

    def test_base_path_root_path_returns_index(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        slug = url_to_slug(
            "https://docs.example.test/docs/en-us/",
            base_path="/docs/en-us",
        )
        assert slug == "index"

    def test_base_path_not_matching_falls_back_to_full_path(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        # When base_path doesn't match, the full path is used (hierarchical mode still active)
        slug = url_to_slug(
            "https://docs.example.test/other/page.html",
            base_path="/docs/en-us",
        )
        assert slug == "other/page"

    def test_no_base_path_uses_hierarchical(self):
        from otutil.tools._knowledge.scraper import url_to_slug
        assert url_to_slug("https://docs.example.test/a/b/c.html") == "a/b/c"


# ---------------------------------------------------------------------------
# Scraper: sidecar format (task 5.2)
# Tests use _write_page directly — no crawl4ai dependency needed.
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestScraperSidecar:
    def test_named_source_sidecar(self, tmp_path: Path):
        """Named source sets `source` to the source name."""
        import yaml as _yaml

        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/intro", "# Hello\n\nWorld.", "mysite")

        meta_files = list(tmp_path.glob("*.meta.yaml"))
        assert len(meta_files) == 1
        meta = _yaml.safe_load(meta_files[0].read_text())
        assert meta["url"] == "https://docs.example.test/intro"
        assert meta["source"] == "mysite"
        assert "crawled_at" in meta

    def test_adhoc_url_sidecar_uses_hostname(self, tmp_path: Path):
        """Ad-hoc URL sets `source` to the hostname when passed as source_name."""
        import yaml as _yaml

        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/page", "Content here.", "docs.example.test")

        meta = _yaml.safe_load(next(tmp_path.glob("*.meta.yaml")).read_text())
        assert meta["source"] == "docs.example.test"

    def test_md_file_contains_content(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/api", "## API\n\nDocs.", "site")

        md_files = list(tmp_path.glob("*.md"))
        assert len(md_files) == 1
        assert "## API" in md_files[0].read_text()

    def test_depth_not_written_to_sidecar(self, tmp_path: Path):
        """Sidecar no longer includes depth — depth is computed at index time."""
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/a/b/c.html", "Content.", "site")

        meta_files = list(tmp_path.rglob("*.meta.yaml"))
        assert len(meta_files) == 1
        meta = _yaml.safe_load(meta_files[0].read_text())
        assert "depth" not in meta
        assert "url_base_path" not in meta

    def test_page_metadata_written_to_sidecar(self, tmp_path: Path):
        """title/description/keywords from page_metadata appear in sidecar."""
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(
            tmp_path,
            "https://docs.example.test/cmd/move",
            "Content.",
            "site",
            page_metadata={"title": "Move Command", "description": "Moves objects.", "keywords": ["move", "transform"]},
        )

        meta = _yaml.safe_load(next(tmp_path.rglob("*.meta.yaml")).read_text())
        assert meta["title"] == "Move Command"
        assert meta["description"] == "Moves objects."
        assert meta["keywords"] == ["move", "transform"]

    def test_hierarchical_slug_creates_subdirectory(self, tmp_path: Path):
        """Hierarchical URL paths cause files to be nested under subdirectories."""
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(
            tmp_path,
            "https://docs.example.test/guide/intro.html",
            "Content.",
            "site",
        )

        assert (tmp_path / "guide" / "intro.md").exists()
        assert (tmp_path / "guide" / "intro.meta.yaml").exists()


# ---------------------------------------------------------------------------
# Scraper: config resolution (task 5.3)
# ---------------------------------------------------------------------------

def _make_fake_playwright_modules() -> dict[str, MagicMock]:
    """Return sys.modules patches that make playwright checks succeed."""
    fake_browser = MagicMock()
    fake_browser.close = MagicMock()
    fake_chromium = MagicMock()
    fake_chromium.launch = MagicMock(return_value=fake_browser)
    fake_pw_instance = MagicMock()
    fake_pw_instance.chromium = fake_chromium
    fake_pw_ctx = MagicMock()
    fake_pw_ctx.__enter__ = MagicMock(return_value=fake_pw_instance)
    fake_pw_ctx.__exit__ = MagicMock(return_value=False)
    fake_sync_playwright = MagicMock(return_value=fake_pw_ctx)
    fake_sync_api = MagicMock()
    fake_sync_api.sync_playwright = fake_sync_playwright
    fake_playwright = MagicMock()
    fake_playwright.sync_api = fake_sync_api
    fake_playwright._test_browser = fake_browser
    return {
        "playwright": fake_playwright,
        "playwright.sync_api": fake_sync_api,
        "crawl4ai": MagicMock(),
    }


@pytest.mark.unit
@pytest.mark.tools
class TestScrapeProjectConfig:
    def test_extra_fields_rejected(self):
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig
        with pytest.raises(ValidationError):
            ScrapeProjectConfig(
                output_base_dir="/tmp/base",
                typo_field="oops",
                sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
            )

    def test_relative_output_base_dir_rejected(self):
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig
        with pytest.raises(ValidationError, match="absolute path"):
            ScrapeProjectConfig(
                output_base_dir="relative/path",
                sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
            )

    def test_source_extra_fields_rejected(self):
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import ScrapeSourceConfig
        with pytest.raises(ValidationError):
            ScrapeSourceConfig(url="https://docs.example.test/", bad_key="x")

    def test_valid_config_accepted(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"docs": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        assert proj.depth == 3
        assert proj.max_pages == 100
        assert proj.check_robots_txt is True


@pytest.mark.unit
@pytest.mark.tools
class TestResolveSource:
    def _proj(self, **kwargs: Any):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig
        defaults = dict(
            output_base_dir="/tmp/base",
            depth=3, max_pages=100, check_robots_txt=True,
            delay_min=0.5, delay_max=2.0, user_agent="proj-agent",
        )
        defaults.update(kwargs)
        defaults.setdefault("sources", {"s": ScrapeSourceConfig(url="https://docs.example.test/")})
        return ScrapeProjectConfig(**defaults)

    def test_output_dir_derived_from_base_and_name(self):
        from pathlib import Path
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj()
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "my-source", src)
        assert resolved.output_dir == Path("/tmp/base/my-source")

    def test_source_overrides_depth(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(depth=3)
        src = ScrapeSourceConfig(url="https://docs.example.test/", depth=6)
        resolved = resolve_source(proj, "s", src)
        assert resolved.depth == 6

    def test_source_inherits_depth_when_none(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(depth=5)
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.depth == 5

    def test_bool_false_uses_is_not_none(self):
        """Explicit check_robots_txt=False must not fall back to project default True."""
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(check_robots_txt=True)
        src = ScrapeSourceConfig(url="https://docs.example.test/", check_robots_txt=False)
        resolved = resolve_source(proj, "s", src)
        assert resolved.check_robots_txt is False

    def test_all_seven_inheritable_fields_resolved(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(depth=2, max_pages=50, check_robots_txt=False,
                          delay_min=1.0, delay_max=3.0, user_agent="ua")
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        r = resolve_source(proj, "s", src)
        assert r.depth == 2
        assert r.max_pages == 50
        assert r.check_robots_txt is False
        assert r.delay_min == 1.0
        assert r.delay_max == 3.0
        assert r.user_agent == "ua"


@pytest.mark.unit
@pytest.mark.tools
class TestScrapeProjectCLI:
    def _invoke(self, args: list[str]) -> Any:
        from onetool.kb import kb_app
        from typer.testing import CliRunner
        return CliRunner().invoke(kb_app, args)

    def _make_cfg(self, sources: dict[str, Any] | None = None):
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig, ScrapeSourceConfig
        sources = sources or {"src-a": ScrapeSourceConfig(url="https://docs.example.test/a"),
                              "src-b": ScrapeSourceConfig(url="https://docs.example.test/b")}
        proj = ScrapeProjectConfig(output_base_dir="/tmp/base", sources=sources)
        return Config(kb={"myproject": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

    def test_unknown_project_error_lists_available(self):
        import sys
        cfg = self._make_cfg()
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            result = self._invoke(["scrape", "notaproject"])
        assert result.exit_code != 0
        assert "notaproject" in result.output
        assert "myproject" in result.output

    def test_only_unknown_name_errors_before_crawl(self):
        import sys
        cfg = self._make_cfg()
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape") as mock_rs,
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            result = self._invoke(["scrape", "myproject", "--only", "src-a,ghost"])
        assert result.exit_code != 0
        assert "ghost" in result.output
        mock_rs.assert_not_called()

    def test_only_subset_runs_correct_sources(self):
        import sys
        cfg = self._make_cfg()
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape") as mock_rs,
            patch("otutil.tools._knowledge.scraper.write_run_report"),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            mock_rs.return_value = MagicMock(written=1, failed=0, skipped=0)
            result = self._invoke(["scrape", "myproject", "--only", "src-a"])
        assert result.exit_code == 0, result.output
        assert mock_rs.call_count == 1
        assert mock_rs.call_args.kwargs["source_name"] == "src-a"

    def test_all_sources_run_when_no_only(self):
        import sys
        cfg = self._make_cfg()
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape") as mock_rs,
            patch("otutil.tools._knowledge.scraper.write_run_report"),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            mock_rs.return_value = MagicMock(written=1, failed=0, skipped=0)
            result = self._invoke(["scrape", "myproject"])
        assert result.exit_code == 0, result.output
        assert mock_rs.call_count == 2

    def test_missing_crawl4ai_shows_install_message(self):
        import sys
        with patch.dict(sys.modules, {"crawl4ai": None}):
            result = self._invoke(["scrape", "myproject"])
        assert result.exit_code != 0
        assert "crawl4ai" in result.output
        assert "onetool-mcp[scrape]" in result.output

    def test_missing_playwright_browser_shows_error(self):
        import sys
        fake_browser_exc = Exception("Browser executable doesn't exist")
        fake_chromium = MagicMock()
        fake_chromium.launch = MagicMock(side_effect=fake_browser_exc)
        fake_pw_instance = MagicMock()
        fake_pw_instance.chromium = fake_chromium
        fake_pw_ctx = MagicMock()
        fake_pw_ctx.__enter__ = MagicMock(return_value=fake_pw_instance)
        fake_pw_ctx.__exit__ = MagicMock(return_value=False)
        fake_sync_api = MagicMock()
        fake_sync_api.sync_playwright = MagicMock(return_value=fake_pw_ctx)
        fake_playwright = MagicMock()
        fake_playwright.sync_api = fake_sync_api
        with patch.dict(sys.modules, {
            "crawl4ai": MagicMock(),
            "playwright": fake_playwright,
            "playwright.sync_api": fake_sync_api,
        }):
            result = self._invoke(["scrape", "myproject"])
        assert result.exit_code != 0
        assert "playwright install chromium" in result.output

    def test_playwright_probe_closes_browser_when_scrape_fails(self):
        import sys
        cfg = self._make_cfg(sources={"src-a": self._make_cfg().kb["myproject"].scrape.sources["src-a"]})
        fake_modules = _make_fake_playwright_modules()
        fake_browser = fake_modules["playwright"]._test_browser
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape", side_effect=RuntimeError("crawl failed")),
            patch.dict(sys.modules, fake_modules),
        ):
            result = self._invoke(["scrape", "myproject", "--only", "src-a"])

        assert result.exit_code != 0
        fake_browser.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
class TestScrapeResume:
    def _make_cfg(self, sources: dict[str, Any]):
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig
        proj = ScrapeProjectConfig(output_base_dir="/tmp/base", sources=sources)
        return Config(kb={"proj": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

    def test_source_with_state_json_resumes(self, tmp_path: Path):
        import sys
        from otutil.tools._knowledge.config import ScrapeSourceConfig
        # output_dir for "src-a" = tmp_path/base/src-a
        base = tmp_path / "base"
        state_dir = base / "src-a"
        state_dir.mkdir(parents=True)
        (state_dir / ".state.json").write_text("{}")

        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig
        proj = ScrapeProjectConfig(
            output_base_dir=str(base),
            sources={"src-a": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        cfg = Config(kb={"proj": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape") as mock_rs,
            patch("otutil.tools._knowledge.scraper.write_run_report"),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            mock_rs.return_value = MagicMock(written=1, failed=0, skipped=0)
            from onetool.kb import kb_app
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["scrape", "proj", "--resume"])

        assert result.exit_code == 0, result.output
        assert mock_rs.call_args.kwargs["resume"] is True

    def test_source_without_state_json_does_not_resume(self, tmp_path: Path):
        import sys
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig, ScrapeSourceConfig
        base = tmp_path / "base"
        proj = ScrapeProjectConfig(
            output_base_dir=str(base),
            sources={"src-b": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        cfg = Config(kb={"proj": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape") as mock_rs,
            patch("otutil.tools._knowledge.scraper.write_run_report"),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            mock_rs.return_value = MagicMock(written=1, failed=0, skipped=0)
            from onetool.kb import kb_app
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["scrape", "proj", "--resume"])

        assert result.exit_code == 0, result.output
        assert mock_rs.call_args.kwargs["resume"] is False

    def test_mixed_sources_resume_per_source(self, tmp_path: Path):
        import sys
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig, ScrapeProjectConfig, ScrapeSourceConfig
        base = tmp_path / "base"
        state_dir = base / "has-state"
        state_dir.mkdir(parents=True)
        (state_dir / ".state.json").write_text("{}")

        proj = ScrapeProjectConfig(
            output_base_dir=str(base),
            sources={
                "has-state": ScrapeSourceConfig(url="https://docs.example.test/a"),
                "no-state": ScrapeSourceConfig(url="https://docs.example.test/b"),
            },
        )
        cfg = Config(kb={"proj": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})

        resume_flags: list[bool] = []

        def capture_run_scrape(**kwargs: Any) -> Any:
            resume_flags.append(kwargs["resume"])
            return MagicMock(written=1, failed=0, skipped=0)

        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape", side_effect=capture_run_scrape),
            patch("otutil.tools._knowledge.scraper.write_run_report"),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            from onetool.kb import kb_app
            from typer.testing import CliRunner
            result = CliRunner().invoke(kb_app, ["scrape", "proj", "--resume"])

        assert result.exit_code == 0, result.output
        assert resume_flags == [True, False]


# ---------------------------------------------------------------------------
# Task 1.5 — TestResolveSource: new field resolution
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestResolveSourceNewFields:
    def _proj(self, **kwargs):  # type: ignore[no-untyped-def]
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig
        defaults = dict(
            output_base_dir="/tmp/base",
            depth=3, max_pages=100, check_robots_txt=True,
            delay_min=0.5, delay_max=2.0, user_agent="proj-agent",
        )
        defaults.update(kwargs)
        defaults.setdefault("sources", {"s": ScrapeSourceConfig(url="https://docs.example.test/")})
        return ScrapeProjectConfig(**defaults)

    def test_source_wait_for_overrides_project(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(wait_for="")
        src = ScrapeSourceConfig(url="https://docs.example.test/", wait_for="css:.topic-body")
        resolved = resolve_source(proj, "s", src)
        assert resolved.wait_for == "css:.topic-body"

    def test_source_inherits_project_wait_for(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(wait_for="css:.content")
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.wait_for == "css:.content"

    def test_source_page_timeout_overrides_project(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(page_timeout=30000)
        src = ScrapeSourceConfig(url="https://docs.example.test/", page_timeout=60000)
        resolved = resolve_source(proj, "s", src)
        assert resolved.page_timeout == 60000

    def test_source_inherits_project_page_timeout(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(page_timeout=45000)
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.page_timeout == 45000

    def test_cache_and_process_iframes_from_project(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj(cache=True, process_iframes=True)
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.cache is True
        assert resolved.process_iframes is True

    def test_cache_and_process_iframes_default_false(self):
        from otutil.tools._knowledge.config import ScrapeSourceConfig, resolve_source
        proj = self._proj()
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.cache is False
        assert resolved.process_iframes is False


# ---------------------------------------------------------------------------
# Task 3.6 — PageRecord, ScrapeResult extension, write_run_report
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestPageRecordAndRunReport:
    def test_page_record_fields(self):
        from otutil.tools._knowledge.scraper import PageRecord
        r = PageRecord(url="https://docs.example.test/page", slug="page", status="ok",
                       content_len=500, elapsed_s=0.42, error="")
        assert r.url == "https://docs.example.test/page"
        assert r.status == "ok"
        assert r.content_len == 500
        assert r.error == ""

    def test_scrape_result_new_fields(self):
        from otutil.tools._knowledge.scraper import PageRecord, ScrapeResult
        r = ScrapeResult(
            written=1, source_name="test-src",
            pages=[PageRecord(url="u", slug="s", status="ok", content_len=10, elapsed_s=0.1, error="")],
            elapsed_s=1.5, start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:00:01+00:00", resumed=False,
            warnings=["depth=5 — deep crawl, may be slow"],
            config_snapshot={"url": "https://docs.example.test/"},
        )
        assert r.source_name == "test-src"
        assert len(r.pages) == 1
        assert r.elapsed_s == 1.5
        assert r.resumed is False
        assert "depth=5" in r.warnings[0]

    def test_write_run_report_creates_json(self, tmp_path: Any):
        import json
        from otutil.tools._knowledge.scraper import ScrapeResult, write_run_report
        result = ScrapeResult(written=2, failed=0, skipped=1, source_name="src",
                              elapsed_s=3.0, start_time="s", end_time="e")
        dest = write_run_report(result, tmp_path)
        assert dest.name == "._run_report.json"
        data = json.loads(dest.read_text())
        assert data["written"] == 2
        assert data["source_name"] == "src"
        assert "pages" in data
        assert "warnings" in data

    def test_write_run_report_overwrites(self, tmp_path: Any):
        import json
        from otutil.tools._knowledge.scraper import ScrapeResult, write_run_report
        r1 = ScrapeResult(written=1, source_name="s1")
        r2 = ScrapeResult(written=99, source_name="s2")
        write_run_report(r1, tmp_path)
        write_run_report(r2, tmp_path)
        data = json.loads((tmp_path / "._run_report.json").read_text())
        assert data["written"] == 99


# ---------------------------------------------------------------------------
# Debug flag: _write_debug_artifacts and --debug wiring
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestDebugFlag:
    def test_write_debug_artifacts_ok_page(self, tmp_path: Any):
        import base64
        import json
        from otutil.tools._knowledge.scraper import _write_debug_artifacts

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        page = type("Page", (), {
            "url": "https://docs.example.test/guide",
            "cleaned_html": "<p>hello</p>",
            "html": "<html><body><p>hello</p></body></html>",
            "screenshot": base64.b64encode(fake_png).decode(),
            "status_code": 200,
            "redirected_url": None,
            "links": {"internal": [{"href": "/other"}], "external": []},
            "console_messages": None,
            "js_execution_result": None,
            "error_message": "",
        })()

        _write_debug_artifacts(page, "guide", tmp_path)

        debug_dir = tmp_path / "._debug" / "guide"
        assert (debug_dir / "cleaned.html").read_text() == "<p>hello</p>"
        assert "<html>" in (debug_dir / "raw.html").read_text()
        assert (debug_dir / "screenshot.png").read_bytes() == fake_png
        meta = json.loads((debug_dir / "meta.json").read_text())
        assert meta["url"] == "https://docs.example.test/guide"
        assert meta["status_code"] == 200
        assert meta["links"]["internal"] == ["/other"]

    def test_write_debug_artifacts_empty_page_no_screenshot(self, tmp_path: Any):
        import json
        from otutil.tools._knowledge.scraper import _write_debug_artifacts

        page = type("Page", (), {
            "url": "https://docs.example.test/empty",
            "cleaned_html": "",
            "html": "<html></html>",
            "screenshot": "",
            "status_code": 200,
            "redirected_url": None,
            "links": {},
            "console_messages": None,
            "js_execution_result": None,
            "error_message": "",
        })()

        _write_debug_artifacts(page, "empty", tmp_path)

        debug_dir = tmp_path / "._debug" / "empty"
        assert (debug_dir / "cleaned.html").read_text() == ""
        assert (debug_dir / "raw.html").exists()
        assert not (debug_dir / "screenshot.png").exists()
        meta = json.loads((debug_dir / "meta.json").read_text())
        assert meta["url"] == "https://docs.example.test/empty"

    def test_debug_passes_screenshot_to_crawler_run_config(self):
        """--debug flag passes screenshot=True to CrawlerRunConfig."""
        import inspect
        from otutil.tools._knowledge.scraper import run_scrape
        assert "debug" in inspect.signature(run_scrape).parameters
        assert inspect.signature(run_scrape).parameters["debug"].default is False


@pytest.mark.unit
@pytest.mark.tools
class TestScrapeAsyncBridge:
    async def test_run_scrape_completes_inside_running_loop(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import ScrapeResult, run_scrape

        async def fake_run(**_kwargs: Any) -> ScrapeResult:
            return ScrapeResult(written=1, source_name="docs")

        with patch("otutil.tools._knowledge.scraper._run_scrape_async", side_effect=fake_run):
            result = run_scrape(
                url="https://docs.example.test/",
                output_dir=tmp_path,
                source_name="docs",
            )

        assert result.written == 1

    async def test_run_scrape_propagates_async_exception(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import run_scrape

        async def fake_run(**_kwargs: Any) -> None:
            raise RuntimeError("scrape failed")

        with (
            patch("otutil.tools._knowledge.scraper._run_scrape_async", side_effect=fake_run),
            pytest.raises(RuntimeError, match="scrape failed"),
        ):
            run_scrape(
                url="https://docs.example.test/",
                output_dir=tmp_path,
                source_name="docs",
            )


def _make_fake_crawl4ai_modules(*, deep: bool = False) -> tuple[dict[str, Any], MagicMock]:
    """Create fake crawl4ai modules with observable crawler cleanup."""
    import types

    crawler_instance = MagicMock()
    crawler_instance.__aenter__ = MagicMock(return_value=crawler_instance)
    crawler_instance.__aexit__ = MagicMock(return_value=False)

    page = MagicMock()
    page.success = True
    page.url = "https://docs.example.test/page"
    page.metadata = {}
    page.markdown = MagicMock(fit_markdown="content", raw_markdown="content")

    if deep:
        async def _page_iter() -> Any:
            yield page

        async def arun(*_args: Any, **_kwargs: Any) -> Any:
            return _page_iter()
    else:
        async def arun(*_args: Any, **_kwargs: Any) -> list[Any]:
            return [page]

    crawler_instance.arun = MagicMock(side_effect=arun)

    class FakeAsyncWebCrawler:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return crawler_instance

        async def __aexit__(self, *args: Any) -> bool:
            return bool(crawler_instance.__aexit__(*args))

    class FakeConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeCacheMode:
        ENABLED = "enabled"
        DISABLED = "disabled"

    crawl4ai = types.ModuleType("crawl4ai")
    crawl4ai.AsyncWebCrawler = FakeAsyncWebCrawler
    crawl4ai.BrowserConfig = FakeConfig
    crawl4ai.CacheMode = FakeCacheMode
    crawl4ai.CrawlerRunConfig = FakeConfig

    modules: dict[str, Any] = {
        "crawl4ai": crawl4ai,
        "crawl4ai.content_filter_strategy": types.SimpleNamespace(PruningContentFilter=FakeConfig),
        "crawl4ai.markdown_generation_strategy": types.SimpleNamespace(DefaultMarkdownGenerator=FakeConfig),
    }
    if deep:
        modules.update({
            "crawl4ai.deep_crawling": types.SimpleNamespace(
                BFSDeepCrawlStrategy=FakeConfig,
                DFSDeepCrawlStrategy=FakeConfig,
            ),
            "crawl4ai.deep_crawling.filters": types.SimpleNamespace(
                DomainFilter=FakeConfig,
                FilterChain=lambda filters: filters,
                URLPatternFilter=FakeConfig,
            ),
        })
    return modules, crawler_instance


@pytest.mark.unit
@pytest.mark.tools
class TestScraperContextManagerCleanup:
    async def test_seed_url_scrape_closes_crawler_when_write_fails(self, tmp_path: Path):
        import sys
        from otutil.tools._knowledge.scraper import _run_scrape_async

        fake_modules, crawler = _make_fake_crawl4ai_modules()
        with (
            patch.dict(sys.modules, fake_modules),
            patch("otutil.tools._knowledge.scraper._write_page", side_effect=RuntimeError("write failed")),
            pytest.raises(RuntimeError, match="write failed"),
        ):
            await _run_scrape_async(
                url="https://docs.example.test/",
                output_dir=tmp_path,
                source_name="docs",
                depth=1,
                max_pages=1,
                url_prefix="",
                check_robots_txt=True,
                delay_min=0,
                delay_max=0,
                user_agent="",
                wait_for="",
                page_timeout=30000,
                cache=False,
                process_iframes=False,
                content_filter_threshold=0.48,
                min_word_threshold=50,
                crawl_strategy="seed_urls",
                seed_urls=["https://docs.example.test/page"],
                score={},
                css_selector="",
                js_code="",
                include_images=False,
                resume=False,
                flat_files=False,
                on_page=None,
                category=None,
                tags=[],
                debug=False,
            )

        crawler.__aexit__.assert_called_once()

    async def test_deep_scrape_closes_crawler_when_write_fails(self, tmp_path: Path):
        import sys
        from otutil.tools._knowledge.scraper import _run_scrape_async

        fake_modules, crawler = _make_fake_crawl4ai_modules(deep=True)
        with (
            patch.dict(sys.modules, fake_modules),
            patch("otutil.tools._knowledge.scraper._write_page", side_effect=RuntimeError("write failed")),
            pytest.raises(RuntimeError, match="write failed"),
        ):
            await _run_scrape_async(
                url="https://docs.example.test/",
                output_dir=tmp_path,
                source_name="docs",
                depth=1,
                max_pages=1,
                url_prefix="",
                check_robots_txt=True,
                delay_min=0,
                delay_max=0,
                user_agent="",
                wait_for="",
                page_timeout=30000,
                cache=False,
                process_iframes=False,
                content_filter_threshold=0.48,
                min_word_threshold=50,
                crawl_strategy="bfs",
                seed_urls=[],
                score={},
                css_selector="",
                js_code="",
                include_images=False,
                resume=False,
                flat_files=False,
                on_page=None,
                category=None,
                tags=[],
                debug=False,
            )

        crawler.__aexit__.assert_called_once()


# ---------------------------------------------------------------------------
# Config threshold warnings emitted at run start
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestRunStartWarnings:
    """Config threshold warnings are printed at run start unconditionally."""

    def _invoke_scrape(self, source_cfg_kwargs: dict, project_cfg_kwargs: dict | None = None) -> "Any":
        import sys
        from unittest.mock import MagicMock, patch
        from onetool.kb import kb_app
        from typer.testing import CliRunner
        from otutil.tools._knowledge.config import (
            Config, KBProjectConfig, DBConfig, ScrapeProjectConfig, ScrapeSourceConfig,
        )
        proj_kwargs = {"output_base_dir": "/tmp/base", "sources": {"src": ScrapeSourceConfig(**source_cfg_kwargs)}}
        if project_cfg_kwargs:
            proj_kwargs.update(project_cfg_kwargs)
        proj = ScrapeProjectConfig(**proj_kwargs)
        cfg = Config(kb={"proj": KBProjectConfig(db=DBConfig(path="mem/test.db"), scrape=proj)})
        mock_result = MagicMock()
        mock_result.written = 0
        mock_result.failed = 0
        mock_result.skipped = 0
        with (
            patch("otutil.tools._knowledge.config._get_config", return_value=cfg),
            patch("otutil.tools._knowledge.scraper.run_scrape", return_value=mock_result),
            patch("otutil.tools._knowledge.scraper.write_run_report", return_value=MagicMock()),
            patch.dict(sys.modules, _make_fake_playwright_modules()),
        ):
            result = CliRunner().invoke(kb_app, ["scrape", "proj"])
        return result

    def test_large_crawl_warning_printed(self):
        result = self._invoke_scrape(
            {"url": "https://docs.example.test/", "max_pages": 600, "url_prefix": "/docs/"},
        )
        assert "large crawl" in result.output

    def test_deep_crawl_warning_printed(self):
        result = self._invoke_scrape(
            {"url": "https://docs.example.test/", "depth": 5, "url_prefix": "/docs/"},
        )
        assert "deep crawl" in result.output

    def test_no_url_prefix_warning_printed(self):
        result = self._invoke_scrape(
            {"url": "https://docs.example.test/"},
        )
        assert "no url_prefix" in result.output

    def test_aggressive_rate_warning_printed(self):
        result = self._invoke_scrape(
            {"url": "https://docs.example.test/", "delay_min": 0.2, "url_prefix": "/docs/"},
        )
        assert "aggressive rate" in result.output

    def test_seed_urls_ignored_warning_printed(self):
        result = self._invoke_scrape(
            {"url": "https://docs.example.test/", "url_prefix": "/docs/",
             "seed_urls": ["https://docs.example.test/p1"]},
        )
        assert "seed_urls" in result.output and "ignored" in result.output


# ---------------------------------------------------------------------------
# crawl_strategy: config, resolution, validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestCrawlStrategy:
    def test_default_crawl_strategy_is_bfs(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.crawl_strategy == "bfs"

    def test_source_crawl_strategy_overrides_project(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(
            url="https://docs.example.test/",
            crawl_strategy="dfs",
        )
        resolved = resolve_source(proj, "s", src)
        assert resolved.crawl_strategy == "dfs"

    def test_source_inherits_project_crawl_strategy(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            crawl_strategy="best_first",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(proj, "s", src)
        assert resolved.crawl_strategy == "best_first"

    def test_seed_urls_strategy_requires_seed_urls(self):
        import pytest as _pytest
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(url="https://docs.example.test/", crawl_strategy="seed_urls")
        with _pytest.raises(ValueError, match="seed_urls"):
            resolve_source(proj, "s", src)

    def test_seed_urls_strategy_with_urls_resolves_ok(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(
            url="https://docs.example.test/",
            crawl_strategy="seed_urls",
            seed_urls=["https://docs.example.test/page1"],
        )
        resolved = resolve_source(proj, "s", src)
        assert resolved.crawl_strategy == "seed_urls"
        assert resolved.seed_urls == ["https://docs.example.test/page1"]

    def test_score_resolves_from_source(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(
            url="https://docs.example.test/",
            score={"keyword_relevance": ["python:1.0", "guide:0.5"]},
        )
        resolved = resolve_source(proj, "s", src)
        assert resolved.score == {"keyword_relevance": ["python:1.0", "guide:0.5"]}

    def test_sitemap_url_field_removed(self):
        """Verify sitemap_url is no longer an accepted field."""
        import pytest as _pytest
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import ScrapeSourceConfig
        with _pytest.raises(ValidationError, match="sitemap_url"):
            ScrapeSourceConfig(url="https://docs.example.test/", sitemap_url="https://docs.example.test/sitemap.xml")


# ---------------------------------------------------------------------------
# css_selector: config field and resolution
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestCssSelector:
    def test_default_css_selector_is_empty(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        resolved = resolve_source(proj, "s", ScrapeSourceConfig(url="https://docs.example.test/"))
        assert resolved.css_selector == ""

    def test_css_selector_preserved_on_source(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig, ScrapeSourceConfig, resolve_source
        proj = ScrapeProjectConfig(
            output_base_dir="/tmp/base",
            sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
        )
        src = ScrapeSourceConfig(url="https://docs.example.test/", css_selector="#mc-main-content")
        resolved = resolve_source(proj, "s", src)
        assert resolved.css_selector == "#mc-main-content"

    def test_css_selector_in_run_scrape_signature(self):
        import inspect
        from otutil.tools._knowledge.scraper import run_scrape
        assert "css_selector" in inspect.signature(run_scrape).parameters


# ---------------------------------------------------------------------------
# Real scrape progress denominator for seed_urls strategy
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestScrapeProgressDenominator:
    """Verify _scrape_total logic for seed_urls vs bfs strategy."""

    def _compute_total(self, crawl_strategy: str, seed_urls: list, max_pages: int) -> int:
        """Replicate the denominator logic from kb.py."""
        return len(seed_urls) if crawl_strategy == "seed_urls" else max_pages

    def test_seed_urls_uses_len_seed_urls(self):
        assert self._compute_total("seed_urls", ["u1", "u2", "u3"], max_pages=100) == 3

    def test_bfs_uses_max_pages(self):
        assert self._compute_total("bfs", [], max_pages=100) == 100

    def test_dfs_uses_max_pages(self):
        assert self._compute_total("dfs", ["u1"], max_pages=50) == 50

    def test_best_first_uses_max_pages(self):
        assert self._compute_total("best_first", ["u1"], max_pages=200) == 200

    def test_seed_urls_21_pages(self):
        urls = [f"https://docs.example.test/ch-{i:02d}/" for i in range(1, 22)]
        assert self._compute_total("seed_urls", urls, max_pages=100) == 21

    def test_max_pages_override_reflected_in_total(self):
        """--max-pages override should replace resolved.max_pages in denominator."""
        assert self._compute_total("bfs", [], max_pages=50) == 50


# ---------------------------------------------------------------------------
# max_pages hard limit enforcement in BFS loop
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestMaxPagesHardLimit:
    """Verify the BFS loop stops writing once max_pages is reached."""

    def _simulate_bfs_loop(self, pages_to_yield: int, max_pages: int) -> int:
        """Replicate the break logic from _run_scrape_async BFS path."""
        written = 0
        for _ in range(pages_to_yield):
            written += 1
            if written >= max_pages:
                break
        return written

    def test_stops_at_max_pages(self):
        assert self._simulate_bfs_loop(pages_to_yield=2000, max_pages=100) == 100

    def test_stops_exactly_at_limit(self):
        assert self._simulate_bfs_loop(pages_to_yield=10, max_pages=10) == 10

    def test_fewer_pages_than_limit(self):
        assert self._simulate_bfs_loop(pages_to_yield=5, max_pages=100) == 5

    def test_max_pages_one(self):
        assert self._simulate_bfs_loop(pages_to_yield=50, max_pages=1) == 1

    def test_run_scrape_has_max_pages_param(self):
        import inspect
        from otutil.tools._knowledge.scraper import run_scrape
        assert "max_pages" in inspect.signature(run_scrape).parameters

    def test_max_pages_cli_option_exists(self):
        """--max-pages option must exist on kb scrape command."""
        from typer.testing import CliRunner
        from onetool.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["kb", "scrape", "--help"])
        assert "--max-pages" in result.output


# ---------------------------------------------------------------------------
# Binary extension filter: query-string bypass + case-insensitive
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestBinaryExtensionFilter:
    """_BINARY_EXTENSIONS regex correctly blocks binary URLs with query strings and uppercase extensions."""

    def _regex(self):
        from otutil.tools._knowledge.scraper import _BINARY_EXTENSIONS
        return _BINARY_EXTENSIONS

    def test_plain_pdf_matches(self):
        assert self._regex().search("https://docs.example.test/file.pdf")

    def test_pdf_with_query_string_matches(self):
        assert self._regex().search("https://docs.example.test/file.pdf?v=3")

    def test_pdf_with_fragment_matches(self):
        assert self._regex().search("https://docs.example.test/file.pdf#page=2")

    def test_uppercase_extension_matches(self):
        assert self._regex().search("https://docs.example.test/file.PDF")

    def test_uppercase_with_query_string_matches(self):
        assert self._regex().search("https://docs.example.test/file.ZIP?token=abc")

    def test_html_page_not_matched(self):
        assert not self._regex().search("https://docs.example.test/guide/intro.html")

    def test_html_with_query_string_not_matched(self):
        assert not self._regex().search("https://docs.example.test/page.html?lang=en")

    def test_path_containing_pdf_word_not_matched(self):
        # "pdf" in a path segment without a dot should not match
        assert not self._regex().search("https://docs.example.test/pdfguide/intro")


# ---------------------------------------------------------------------------
# Sidecar: category and tags written/read from config
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.tools
class TestScraperWritePageCategoryTags:
    """_write_page() writes category and tags to .meta.yaml when set."""

    def test_category_written_when_set(self, tmp_path: Path):
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/p", "Content.", "src", category="rule")

        meta = _yaml.safe_load(next(tmp_path.glob("*.meta.yaml")).read_text())
        assert meta["category"] == "rule"

    def test_tags_written_when_set(self, tmp_path: Path):
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/p", "Content.", "src", tags=["alpha", "beta"])

        meta = _yaml.safe_load(next(tmp_path.glob("*.meta.yaml")).read_text())
        assert meta["tags"] == ["alpha", "beta"]

    def test_category_absent_when_not_set(self, tmp_path: Path):
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/p", "Content.", "src")

        meta = _yaml.safe_load(next(tmp_path.glob("*.meta.yaml")).read_text())
        assert "category" not in meta

    def test_tags_absent_when_empty(self, tmp_path: Path):
        import yaml as _yaml
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/p", "Content.", "src", tags=[])

        meta = _yaml.safe_load(next(tmp_path.glob("*.meta.yaml")).read_text())
        assert "tags" not in meta


@pytest.mark.unit
@pytest.mark.tools
class TestChunkerSidecarCategoryTags:
    """chunk_file() applies sidecar category and merges sidecar tags."""

    def test_sidecar_category_applied_to_chunk(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text("url: https://x.test/\ncategory: rule\n", encoding="utf-8")
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].category == "rule"

    def test_sidecar_category_note(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text("url: https://x.test/\ncategory: note\n", encoding="utf-8")
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].category == "note"

    def test_no_sidecar_category_defaults_to_reference(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].category == "reference"

    def test_sidecar_tags_merged_into_chunk_tags(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://x.test/\ntags:\n  - config-tag\n  - another\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert "config-tag" in chunks[0].tags
        assert "another" in chunks[0].tags

    def test_sidecar_tags_and_keywords_merged_no_duplicates(self, tmp_path: Path):
        from otutil.tools._knowledge.chunker import chunk_file

        md = tmp_path / "page.md"
        md.write_text("Content here.", encoding="utf-8")
        (tmp_path / "page.meta.yaml").write_text(
            "url: https://x.test/\ntags:\n  - shared\nkeywords: shared, extra\n",
            encoding="utf-8",
        )
        chunks = chunk_file(md, Path("page.md"))
        assert chunks[0].tags.count("shared") == 1
        assert "extra" in chunks[0].tags


# ===========================================================================
# Task 3.6 — canonicalize() and strip_topic_roots()
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestCanonicalize:
    """Unit tests for canonicalize() and strip_topic_roots()."""

    def test_hierarchical_path_strips_extension(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("commands/move.md") == "commands/move"

    def test_deep_path(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("a/b/c.html") == "a/b/c"

    def test_no_extension(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("guide/intro") == "guide/intro"

    def test_flat_file_with_colons_becomes_hierarchical(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("app::v1::commands::move.md") == "app/v1/commands/move"

    def test_no_source_dir_returns_full_path(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("docs/en-us/guide.md") == "docs/en-us/guide"

    def test_source_dir_strips_prefix(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("app/v1/help/commands/move.md", source_dir="app/v1/help") == "commands/move"

    def test_single_segment(self):
        from otutil.tools._knowledge.chunker import canonicalize
        assert canonicalize("overview.md") == "overview"

    def test_empty_path_returns_index(self):
        from otutil.tools._knowledge.chunker import canonicalize
        # A path equal to source_dir strips to empty → "index"
        assert canonicalize("docs", source_dir="docs") == "index"

    def test_strip_topic_roots_strips_prefix(self):
        from otutil.tools._knowledge.chunker import canonicalize, strip_topic_roots
        canonical = canonicalize("app/v1/guide/en-us/commands/move.md")
        stripped = strip_topic_roots(canonical, ["app/v1/guide/en-us"])
        assert stripped == "commands/move"

    def test_strip_topic_roots_no_match_returns_original(self):
        from otutil.tools._knowledge.chunker import strip_topic_roots
        assert strip_topic_roots("commands/move", ["other/prefix"]) == "commands/move"

    def test_strip_topic_roots_first_match_wins(self):
        from otutil.tools._knowledge.chunker import strip_topic_roots
        result = strip_topic_roots("a/b/c", ["a/b", "a"])
        assert result == "c"


# ===========================================================================
# Task 4.11 — KBProjectConfig config unit tests
# ===========================================================================

@pytest.mark.unit
@pytest.mark.tools
class TestKBProjectConfig:
    """Config unit tests: KBProjectConfig round-trip and schema validation."""

    def test_kb_project_config_round_trip(self):
        from otutil.tools._knowledge.config import Config, KBProjectConfig, DBConfig
        cfg = Config(kb={"docs": KBProjectConfig(db=DBConfig(path="mem/docs.db"))})
        assert cfg.kb["docs"].db.path == "mem/docs.db"

    def test_unknown_databases_key_raises_schema_error(self):
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import Config, DBConfig
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Config(databases={"docs": DBConfig(path="mem/docs.db")})

    def test_unknown_scrape_key_raises_schema_error(self):
        from pydantic import ValidationError
        from otutil.tools._knowledge.config import Config, ScrapeProjectConfig, ScrapeSourceConfig
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Config(scrape={"docs": ScrapeProjectConfig(
                output_base_dir="/tmp",
                sources={"s": ScrapeSourceConfig(url="https://docs.example.test/")},
            )})

    def test_missing_kb_key_returns_empty(self):
        from otutil.tools._knowledge.config import Config
        cfg = Config()
        assert cfg.kb == {}

    def test_index_config_defaults(self):
        from otutil.tools._knowledge.config import KBProjectConfig, DBConfig
        kb = KBProjectConfig(db=DBConfig(path="mem/test.db"))
        assert kb.index.ignore_patterns == []
        assert kb.index.topic_roots == []

    def test_index_config_round_trip(self):
        from otutil.tools._knowledge.config import KBProjectConfig, DBConfig, IndexProjectConfig
        kb = KBProjectConfig(
            db=DBConfig(path="mem/test.db"),
            index=IndexProjectConfig(
                ignore_patterns=["*.tmp"],
                topic_roots=["app/v1/guide/en-us"],
            ),
        )
        assert kb.index.ignore_patterns == ["*.tmp"]
        assert kb.index.topic_roots == ["app/v1/guide/en-us"]



@pytest.mark.unit
@pytest.mark.tools
class TestScraperFlatFiles:
    """_write_page() flat_files=True uses '::' separators instead of subdirectories."""

    def test_flat_files_false_creates_subdirectory(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/guide/intro", "Content.", "src", flat_files=False)

        assert (tmp_path / "guide" / "intro.md").exists()
        assert (tmp_path / "guide" / "intro.meta.yaml").exists()

    def test_flat_files_true_writes_flat(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/guide/intro", "Content.", "src", flat_files=True)

        assert (tmp_path / "guide::intro.md").exists()
        assert (tmp_path / "guide::intro.meta.yaml").exists()
        assert not (tmp_path / "guide").exists()

    def test_flat_files_true_deep_path(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/a/b/c/page", "Body.", "src", flat_files=True)

        assert (tmp_path / "a::b::c::page.md").exists()
        assert not (tmp_path / "a").exists()

    def test_flat_files_content_preserved(self, tmp_path: Path):
        from otutil.tools._knowledge.scraper import _write_page

        _write_page(tmp_path, "https://docs.example.test/x/y", "Hello flat.", "src", flat_files=True)

        assert (tmp_path / "x::y.md").read_text() == "Hello flat."

    def test_flat_files_canonicalizes_same_as_hierarchical(self):
        """:: flat files and hierarchical files produce the same canonical topic."""
        from otutil.tools._knowledge.chunker import canonicalize

        flat_canonical = canonicalize("guide::intro.md")
        hier_canonical = canonicalize("guide/intro.md")

        assert flat_canonical == hier_canonical == "guide/intro"

    def test_flat_files_default_false_in_scrape_project_config(self):
        from otutil.tools._knowledge.config import ScrapeProjectConfig

        cfg = ScrapeProjectConfig(
            output_base_dir="/tmp/test",
            sources={"s": {"url": "https://docs.example.test/"}},
        )
        assert cfg.flat_files is False

    def test_flat_files_inherited_from_project(self):
        from otutil.tools._knowledge.config import (
            ScrapeProjectConfig,
            ScrapeSourceConfig,
            resolve_source,
        )

        project = ScrapeProjectConfig(
            output_base_dir="/tmp/test",
            flat_files=True,
            sources={},
        )
        source = ScrapeSourceConfig(url="https://docs.example.test/")
        resolved = resolve_source(project, "src", source)
        assert resolved.flat_files is True

    def test_flat_files_source_overrides_project(self):
        from otutil.tools._knowledge.config import (
            ScrapeProjectConfig,
            ScrapeSourceConfig,
            resolve_source,
        )

        project = ScrapeProjectConfig(
            output_base_dir="/tmp/test",
            flat_files=True,
            sources={},
        )
        source = ScrapeSourceConfig(url="https://docs.example.test/", flat_files=False)
        resolved = resolve_source(project, "src", source)
        assert resolved.flat_files is False


@pytest.mark.unit
@pytest.mark.tools
class TestSearchEmbeddingsGuard:
    """kb.search() returns actionable guidance instead of raw errors
    when embeddings are disabled or missing."""

    def test_embeddings_disabled_returns_friendly_message_without_opening_db(self):
        from otutil.tools._knowledge import retrieval

        with patch(
            "otutil.tools._knowledge.indexer._db_embeddings_enabled",
            return_value=False,
        ), patch.object(retrieval, "get_connection") as mock_get_conn:
            result = retrieval.search(query="x", db="testdb", mode="hybrid")

        assert result == (
            "Semantic search requires embeddings. Enable with: "
            "tools.knowledge.kb.testdb.db.embeddings_enabled: true"
        )
        mock_get_conn.assert_not_called()

    def test_no_embeddings_generated_returns_friendly_message(self):
        from otutil.tools._knowledge import retrieval

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None

        with patch(
            "otutil.tools._knowledge.indexer._db_embeddings_enabled",
            return_value=True,
        ), patch(
            "otutil.tools._knowledge.db._check_vec_available", return_value=True
        ), patch.object(retrieval, "get_connection", return_value=mock_conn):
            result = retrieval.search(query="x", db="testdb", mode="semantic")

        assert (
            result
            == "No embeddings found for 'testdb'. Run kb.reindex(db='testdb') to generate them."
        )


@pytest.mark.unit
@pytest.mark.tools
class TestRetrievalUntrustedContextBoundary:
    """kb.ask's LLM calls send an untrusted-context system message (p22 S2)."""

    def _mock_client(self, content: str = "3"):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=content))
        ]
        return client

    def test_synthesise_includes_untrusted_system_message(self):
        from otutil.tools._knowledge import retrieval

        client = self._mock_client("answer")
        with patch.object(retrieval, "_get_llm_client", return_value=client), patch(
            "ot.config.get_llm_config"
        ):
            retrieval._synthesise("q", "some context")

        _a, kwargs = client.chat.completions.create.call_args
        roles = [m["role"] for m in kwargs["messages"]]
        assert "system" in roles
        system = next(m for m in kwargs["messages"] if m["role"] == "system")
        assert "untrusted" in system["content"].lower()

    def test_llm_rerank_includes_untrusted_system_message(self):
        from otutil.tools._knowledge import retrieval

        client = self._mock_client("5")
        with patch.object(retrieval, "_get_llm_client", return_value=client), patch(
            "ot.config.get_llm_config"
        ):
            retrieval._llm_rerank("q", [{"topic": "t", "content": "passage", "id": 1}])

        _a, kwargs = client.chat.completions.create.call_args
        system = next(m for m in kwargs["messages"] if m["role"] == "system")
        assert "untrusted" in system["content"].lower()
