"""Tests for persistent memory tool pack.

Tests helpers, CRUD operations, safety features, and lifecycle functions
with mocked SQLite and OpenAI.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from otutil.tools._mem import VALID_CATEGORIES, Config
from otutil.tools._mem.content import (
    _build_toc,
    _content_hash,
    _decode_sections,
    _encode_sections,
    _parse_headings,
    _redact,
    _topic_filter,
    _validate_category,
    _validate_tags,
)
from otutil.tools._mem.db import _deserialize_meta, _has_column, _serialize_meta


@pytest.fixture()
def _mock_cwd(tmp_path: Path):
    """Mock CWD for path validation to use tmp_path."""
    with patch("otpack.pathsec.resolve_cwd_path") as mock_resolve_pack:

        def _resolve(path: str) -> Path:
            p = Path(path).expanduser()
            if p.is_absolute():
                return p.resolve()
            return (tmp_path / p).resolve()

        mock_resolve_pack.side_effect = _resolve
        yield


# ---------------------------------------------------------------------------
# Pure function tests (no mocking needed)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestContentHash:
    """Test _content_hash SHA-256 helper."""

    def test_returns_hex_string(self):
        result = _content_hash("hello world")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self):
        assert _content_hash("test") == _content_hash("test")

    def test_different_input_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")


@pytest.mark.unit
@pytest.mark.tools
class TestTopicFilter:
    """Test _topic_filter SQL builder."""

    def test_none_returns_empty(self):
        sql, params = _topic_filter(None)
        assert sql == ""
        assert params == []

    def test_exact_match(self):
        sql, params = _topic_filter("projects/onetool")
        assert "topic = ?" in sql
        assert params == ["projects/onetool"]

    def test_prefix_match_with_trailing_slash(self):
        sql, params = _topic_filter("projects/")
        assert "topic = ?" in sql
        assert "topic LIKE ?" in sql
        assert "projects" in params
        assert "projects/%" in params

    def test_wildcard_match(self):
        sql, params = _topic_filter("projects/*/rules")
        assert "topic LIKE ?" in sql
        assert "projects/%/rules" in params


@pytest.mark.unit
@pytest.mark.tools
def test_config_default_db_path_is_data_scoped() -> None:
    assert Config().db_path == "data/mem/default.db"


@pytest.mark.unit
@pytest.mark.tools
@patch("otutil.tools._mem.content._get_config", return_value=Config())
class TestRedact:
    """Test _redact secret/PII redaction."""

    def test_redacts_api_keys(self, _mock_config):
        result = _redact("key: sk-abc123def456ghi789jkl0123")
        assert "sk-" not in result
        assert "[REDACTED:api_key]" in result

    def test_redacts_github_tokens(self, _mock_config):
        result = _redact("token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789")
        assert "ghp_" not in result
        assert "[REDACTED:github_token]" in result

    def test_redacts_passwords(self, _mock_config):
        result = _redact("password = mysecretpass123")
        assert "mysecretpass123" not in result
        assert "[REDACTED:password]" in result

    def test_redacts_connection_strings(self, _mock_config):
        result = _redact("url: postgres://user:pass@host/db")
        assert "user:pass" not in result
        assert "[REDACTED:connection_string]" in result

    def test_skips_redaction_when_disabled(self, mock_config):
        mock_config.return_value = Config(redaction_enabled=False)
        content = "key: sk-abc123def456ghi789jkl0123"
        assert _redact(content) == content

    def test_invalid_custom_redaction_pattern_logs_context(self, mock_config):
        mock_config.return_value = Config(redaction_patterns=["["])

        with patch("otutil.tools._mem.content.logger.warning") as mock_warning:
            result = _redact("plain content")

        assert result == "plain content"
        entry = mock_warning.call_args.args[0]
        assert entry.fields["event"] == "mem.content.redaction_pattern_invalid"
        assert entry.fields["pattern"] == "["
        assert entry.fields["errorType"] in {"PatternError", "error"}


@pytest.mark.unit
@pytest.mark.tools
class TestValidateTags:
    """Test _validate_tags whitelist validation."""

    @patch("otutil.tools._mem.content._get_config", return_value=Config(tags_whitelist=[]))
    def test_empty_whitelist_allows_all(self, _mock_config):
        assert _validate_tags(["any", "tag"]) == ["any", "tag"]

    @patch("otutil.tools._mem.content._get_config", return_value=Config(tags_whitelist=["allowed"]))
    def test_whitelist_rejects_unknown(self, _mock_config):
        with pytest.raises(ValueError, match="not in whitelist"):
            _validate_tags(["forbidden"])

    @patch("otutil.tools._mem.content._get_config", return_value=Config(tags_whitelist=["project/*"]))
    def test_whitelist_wildcard_prefix(self, _mock_config):
        assert _validate_tags(["project/onetool"]) == ["project/onetool"]

    def test_none_returns_empty(self):
        assert _validate_tags(None) == []


@pytest.mark.unit
@pytest.mark.tools
class TestValidateCategory:
    """Test _validate_category helper."""

    def test_valid_categories(self):
        for cat in VALID_CATEGORIES:
            assert _validate_category(cat) == cat

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Invalid category"):
            _validate_category("invalid")


@pytest.mark.unit
@pytest.mark.tools
class TestMemDBIdentifiers:
    """Validate safe identifier handling in mem DB helpers."""

    def test_has_column_rejects_invalid_identifier(self):
        conn = MagicMock()
        with pytest.raises(ValueError, match="invalid table identifier"):
            _has_column(conn, 'memories"; DROP TABLE memories;--', "topic")


@pytest.mark.unit
@pytest.mark.tools
class TestCosineSimilarity:
    """Test the cosine_similarity UDF, including dimension mismatch handling."""

    def test_similarity_of_identical_vectors(self):
        import struct

        from otutil.tools._mem.db import _cosine_similarity

        blob = struct.pack("<3f", 1.0, 2.0, 3.0)
        assert _cosine_similarity(blob, blob) == pytest.approx(1.0)

    def test_none_inputs_return_none(self):
        from otutil.tools._mem.db import _cosine_similarity

        assert _cosine_similarity(None, b"\x00" * 4) is None
        assert _cosine_similarity(b"\x00" * 4, None) is None

    def test_dimension_mismatch_raises_clear_error(self):
        import struct

        from otutil.tools._mem.db import _cosine_similarity

        a = struct.pack("<3f", 1.0, 2.0, 3.0)
        b = struct.pack("<2f", 1.0, 2.0)
        with pytest.raises(ValueError, match="dimension mismatch.*3 vs 2.*reindex"):
            _cosine_similarity(a, b)


# ---------------------------------------------------------------------------
# CRUD operation tests with mocked SQLite
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestWrite:
    """Test mem.write() with mocked database and embeddings."""

    @patch("otutil.tools._mem.write._embed_now")
    @patch("otutil.tools._mem.write._use_connection")
    def test_stores_new_memory(self, mock_conn, mock_embed):
        from otutil.tools.mem import write

        mock_embed.return_value = None

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        # No duplicate found
        conn.execute.return_value.fetchone.return_value = None

        result = write(topic="test/topic", content="test content")

        assert "Stored memory" in result
        assert "test/topic" in result
        # Verify INSERT was called
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1

    @patch("otutil.tools._mem.write._use_connection")
    def test_rejects_duplicate(self, mock_conn):
        from otutil.tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)

        result = write(topic="test/topic", content="test content")

        assert "Duplicate" in result

    def test_rejects_invalid_category(self):
        from otutil.tools.mem import write

        result = write(topic="test", content="test", category="invalid")
        assert "Error" in result
        assert "Invalid category" in result

    def test_rejects_both_content_and_file(self, tmp_path):
        from otutil.tools.mem import write

        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")

        result = write(topic="test", content="inline", file=str(test_file))
        assert result == "Error: Provide content or file, not both"

    def test_rejects_neither_content_nor_file(self):
        from otutil.tools.mem import write

        result = write(topic="test")
        assert result == "Error: Provide content or file"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.write._embed_now")
    @patch("otutil.tools._mem.write._use_connection")
    def test_reads_from_file(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import write

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")

        result = write(topic="test", file=str(test_file))

        assert "Stored memory" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.write._use_connection")
    def test_file_not_found(self, mock_conn, tmp_path):
        from otutil.tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn

        result = write(topic="test", file=str(tmp_path / "nonexistent.txt"))

        assert "Error" in result
        assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
class TestRead:
    """Test mem.read() with mocked database."""

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_topic(self, mock_conn):
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "memory content", "note",
            '["tag1"]', 5, 3, datetime.now().isoformat(), datetime.now().isoformat(), '{}',
        )

        result = read(topic="test/topic")

        assert result == "memory content"

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_topic_with_meta(self, mock_conn):
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "memory content", "note",
            '["tag1"]', 5, 3, datetime.now().isoformat(), datetime.now().isoformat(), '{}',
        )

        result = read(topic="test/topic", meta=True)

        assert "Topic: test/topic" in result
        assert "Category: note" in result
        assert "Tags: tag1" in result
        assert "memory content" in result
        assert "id-123" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_id(self, mock_conn):
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "content", "rule",
            '[]', 7, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}',
        )

        result = read(topic="ignored", id="id-123")

        assert result == "content"

    @patch("otutil.tools._mem.read._use_connection")
    def test_not_found(self, mock_conn):
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = read(topic="nonexistent")

        assert "No memory found" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_wildcard_topic(self, mock_conn):
        """Wildcard topic routes through LIKE, not exact match."""
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-456", "projects/onetool/rules", "rule content", "rule",
            '[]', 8, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}',
        )

        result = read(topic="projects/*/rules")

        assert result == "rule content"
        sql_call = conn.execute.call_args_list[0][0][0]
        assert "LIKE" in sql_call

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_use_created_at_desc_ordering(self, mock_conn):
        """read() uses ORDER BY created_at DESC so latest row wins."""
        from otutil.tools.mem import read

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-789", "test/topic", "latest content", "note",
            '[]', 5, 0, datetime.now().isoformat(), datetime.now().isoformat(), '{}',
        )

        read(topic="test/topic")

        sql_call = conn.execute.call_args_list[0][0][0]
        assert "ORDER BY created_at DESC" in sql_call
        assert "LIMIT 1" in sql_call


@pytest.mark.unit
@pytest.mark.tools
class TestReadBatch:
    """Test mem.read_batch() with mocked database."""

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_topic_prefix(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", '["tag1"]', 5, 2, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
            ("id-2", "proj/b", "content b", "rule", '[]', 8, 0, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(topic="proj/")

        assert "Read 2 memories" in result
        assert "content a" in result
        assert "content b" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_by_ids(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", '[]', 5, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(ids=["id-1"])

        assert "Read 1 memory" in result
        assert "content a" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_reads_with_meta(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", '["tag1"]', 5, 3, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(topic="proj/", meta=True)

        assert "Topic: proj/a" in result
        assert "Category: note" in result
        assert "Tags: tag1" in result
        assert "content a" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_empty_result(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = read_batch(topic="nonexistent/")

        assert "No memories found" in result

    def test_requires_filter(self):
        from otutil.tools.mem import read_batch

        result = read_batch()

        assert "Error" in result
        assert "At least one filter" in result

    def test_ids_rejects_combined_with_topic(self):
        from otutil.tools.mem import read_batch

        result = read_batch(ids=["id-1"], topic="proj/")

        assert "Error" in result
        assert "ids cannot be combined" in result

    def test_ids_rejects_combined_with_category(self):
        from otutil.tools.mem import read_batch

        result = read_batch(ids=["id-1"], category="rule")

        assert "Error" in result
        assert "ids cannot be combined" in result

    def test_ids_rejects_combined_with_tags(self):
        from otutil.tools.mem import read_batch

        result = read_batch(ids=["id-1"], tags=["tag1"])

        assert "Error" in result
        assert "ids cannot be combined" in result

    @patch("otutil.tools._mem.read._use_connection")
    def test_filters_by_category(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "rule content", "rule", '[]', 5, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(category="rule")

        assert "Read 1 memory" in result
        assert "rule content" in result
        # Verify SQL includes category filter
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "category = ?" in sql_arg

    @patch("otutil.tools._mem.read._use_connection")
    def test_filters_by_tags(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "tagged content", "note", '["tag1"]', 5, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(tags=["tag1"])

        assert "Read 1 memory" in result
        assert "tagged content" in result
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "json_each" in sql_arg

    @patch("otutil.tools._mem.read._use_connection")
    def test_combined_topic_and_category(self, mock_conn):
        from otutil.tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "combined content", "rule", '[]', 5, 1, datetime.now().isoformat(), datetime.now().isoformat(), '{}'),
        ]

        result = read_batch(topic="proj/", category="rule")

        assert "Read 1 memory" in result
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "category = ?" in sql_arg
        assert "topic" in sql_arg


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test mem.search() with mocked database and embeddings."""

    @patch("otutil.tools._mem.search._check_vec_available", return_value=False)
    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.search._generate_query_embedding")
    @patch("otutil.tools._mem.search._get_connection")
    def test_semantic_search(self, mock_conn, mock_embed, _mock_config, _mock_vec):
        from otutil.tools.mem import search

        mock_embed.return_value = [0.1] * 1536

        conn = MagicMock()
        mock_conn.return_value = conn
        # First execute: has_embeddings check; second: actual search
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", '["tag"]', 5, 2, 0.95),
        ]

        result = search(query="test query")

        assert "Found 1 memories" in result
        assert "topic/one" in result
        assert "0.95" in result

    @patch("otutil.tools._mem.search._get_connection")
    def test_pattern_search(self, mock_conn):
        from otutil.tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "matching content", "note", '[]', 5, 1),
        ]

        result = search(query="matching", mode="keyword")

        assert "Found 1 memories" in result

    def test_invalid_mode(self):
        from otutil.tools.mem import search

        result = search(query="test", mode="invalid")
        assert "Error" in result
        assert "Invalid mode" in result

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.search._generate_query_embedding")
    @patch("otutil.tools._mem.search._get_connection")
    def test_no_results(self, mock_conn, mock_embed, _mock_config):
        from otutil.tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = []

        result = search(query="nothing")

        assert "No memories found" in result

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.search._generate_query_embedding")
    @patch("otutil.tools._mem.search._get_connection")
    def test_search_custom_extract(self, mock_conn, mock_embed, _mock_config):
        from otutil.tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", '[]', 5, 1, 0.9),
        ]

        result = search(query="test", extract=50)

        # Should truncate to 50 chars + "..."
        assert "a" * 50 in result
        assert "a" * 51 not in result
        assert "..." in result

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.search._generate_query_embedding")
    @patch("otutil.tools._mem.search._get_connection")
    def test_search_extract_zero_returns_full(self, mock_conn, mock_embed, _mock_config):
        from otutil.tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", '[]', 5, 1, 0.9),
        ]

        result = search(query="test", extract=0)

        assert "a" * 500 in result
        assert "..." not in result


# ---------------------------------------------------------------------------
# Optional embeddings tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestEmbedHelpers:
    """Test _embed_now/_enqueue_after_commit helpers with different config states."""

    @patch("otutil.tools._mem.embedding._get_config", return_value=Config(embeddings_enabled=False))
    def test_disabled_returns_none(self, _mock_config):
        from otutil.tools._mem.embedding import _embed_now

        result = _embed_now("some content")
        assert result is None

    @patch("otutil.tools._mem.embedding._generate_embedding", return_value=[0.1, 0.2, 0.3])
    @patch("otutil.tools._mem.embedding._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=False))
    def test_sync_returns_vector(self, _mock_config, _mock_embed):
        from otutil.tools._mem.embedding import _embed_now

        result = _embed_now("some content")
        assert result == [0.1, 0.2, 0.3]

    @patch("otutil.tools._mem.embedding._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=True))
    def test_async_returns_none_without_enqueue(self, _mock_config):
        from otutil.tools._mem.embedding import _embed_now

        result = _embed_now("some content")
        assert result is None

    @patch("otutil.tools._mem.embedding._enqueue_embedding")
    @patch("otutil.tools._mem.embedding._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=True))
    def test_enqueue_after_commit_async(self, _mock_config, mock_enqueue):
        from otutil.tools._mem.embedding import _enqueue_after_commit

        _enqueue_after_commit("mem-id")
        mock_enqueue.assert_called_once_with("mem-id")

    @patch("otutil.tools._mem.embedding._enqueue_embedding")
    @patch("otutil.tools._mem.embedding._get_config", return_value=Config(embeddings_enabled=False))
    def test_enqueue_after_commit_disabled_noop(self, _mock_config, mock_enqueue):
        from otutil.tools._mem.embedding import _enqueue_after_commit

        _enqueue_after_commit("mem-id")
        mock_enqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
class TestProcessEmbeddingJob:
    """Test the background worker job: embed outside the lock, guarded write-back."""

    @patch("otutil.tools._mem.embedding._generate_embedding", return_value=[0.1, 0.2])
    @patch("otutil.tools._mem.embedding._use_connection")
    def test_embeds_outside_lock_with_content_guard(self, mock_conn, mock_embed):
        from otutil.tools._mem.embedding import _process_embedding_job

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("stored content",)

        # Track lock state at embedding time: __enter__/__exit__ pair count
        lock_depth = {"current": 0, "at_embed": None}
        mock_conn.return_value.__enter__.side_effect = lambda *a: (
            lock_depth.__setitem__("current", lock_depth["current"] + 1) or conn
        )
        mock_conn.return_value.__exit__.side_effect = lambda *a: (
            lock_depth.__setitem__("current", lock_depth["current"] - 1) or False
        )
        mock_embed.side_effect = lambda _content: (
            lock_depth.__setitem__("at_embed", lock_depth["current"]) or [0.1, 0.2]
        )

        _process_embedding_job("mem-id")

        # Embedding generated while no connection lock held
        assert lock_depth["at_embed"] == 0
        # Write-back guarded on unchanged content
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_calls) == 1
        assert "AND content = ?" in update_calls[0][0][0]
        assert update_calls[0][0][1][2] == "stored content"

    @patch("otutil.tools._mem.embedding._generate_embedding")
    @patch("otutil.tools._mem.embedding._use_connection")
    def test_deleted_memory_skipped(self, mock_conn, mock_embed):
        from otutil.tools._mem.embedding import _process_embedding_job

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        _process_embedding_job("gone-id")

        mock_embed.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
class TestSearchEmbeddingsDisabled:
    """Test search returns helpful messages when embeddings disabled."""

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=False))
    def test_semantic_search_returns_message(self, _mock_config):
        from otutil.tools.mem import search

        result = search(query="test query")
        assert "embeddings_enabled" in result

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=False))
    def test_hybrid_search_returns_message(self, _mock_config):
        from otutil.tools.mem import search

        result = search(query="test query", mode="hybrid")
        assert "embeddings_enabled" in result

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=False))
    @patch("otutil.tools._mem.search._get_connection")
    def test_pattern_search_works_when_disabled(self, mock_conn, _mock_config):
        from otutil.tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "matching content", "note", '[]', 5, 1),
        ]

        result = search(query="matching", mode="keyword")
        assert "Found 1 memories" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSearchNoEmbeddings:
    """Test search returns guidance when enabled but no embeddings exist."""

    @patch("otutil.tools._mem.search._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.search._get_connection")
    def test_semantic_no_embeddings_returns_guidance(self, mock_conn, _mock_config):
        from otutil.tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No embeddings exist

        result = search(query="test query")
        assert "mem.reindex" in result


@pytest.mark.unit
@pytest.mark.tools
class TestWriteWithoutEmbeddings:
    """Test that write stores NULL embedding when disabled."""

    @patch("otutil.tools._mem.write._embed_now", return_value=None)
    @patch("otutil.tools._mem.write._use_connection")
    def test_write_stores_null_embedding(self, mock_conn, _mock_embed):
        from otutil.tools.mem import write

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No duplicate

        result = write(topic="test/topic", content="test content")

        assert "Stored memory" in result
        # Verify embedding parameter is None in INSERT (index 7, 0-based)
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        insert_params = insert_calls[0][0][1]
        assert insert_params[7] is None  # embedding is 8th parameter (index 7)


@pytest.mark.unit
@pytest.mark.tools
class TestReindex:
    """Test mem.reindex() backfill function."""

    @patch("otutil.tools._mem.lifecycle._get_config", return_value=Config(embeddings_enabled=False))
    def test_disabled_returns_message(self, _mock_config):
        from otutil.tools.mem import reindex

        result = reindex()
        assert "disabled" in result.lower()

    @patch("otutil.tools._mem.lifecycle._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_dry_run_shows_count(self, mock_conn, _mock_config):
        from otutil.tools.mem import reindex

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content one"),
            ("id-2", "content two"),
        ]

        result = reindex(dry_run=True)
        assert "2 memories" in result

    @patch("otutil.tools._mem.lifecycle._use_connection")
    @patch("otutil.tools._mem.lifecycle._generate_embedding", return_value=[0.1] * 1536)
    @patch("otutil.tools._mem.lifecycle._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_generates_embeddings(self, mock_conn, _mock_config, _mock_embed, mock_use):
        from otutil.tools.mem import reindex

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content one"),
        ]
        mock_use.return_value.__enter__.return_value = conn

        result = reindex(dry_run=False)
        assert "Generated embeddings for 1 memories" in result

    @patch("otutil.tools._mem.lifecycle._use_connection")
    @patch("otutil.tools._mem.lifecycle._generate_embedding")
    @patch("otutil.tools._mem.lifecycle._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_partial_failure_keeps_progress(self, mock_conn, _mock_config, mock_embed, mock_use):
        """One failed embedding must not lose progress: commit is per item."""
        from otutil.tools.mem import reindex

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content one"),
            ("id-2", "content two"),
            ("id-3", "content three"),
        ]
        write_conn = MagicMock()
        mock_use.return_value.__enter__.return_value = write_conn
        mock_embed.side_effect = [[0.1], RuntimeError("API down"), [0.3]]

        result = reindex(dry_run=False)

        assert "Generated embeddings for 2 memories" in result
        assert "1 failed" in result
        assert "API down" in result
        # One commit per successful item
        assert write_conn.commit.call_count == 2

    @patch("otutil.tools._mem.lifecycle._get_config", return_value=Config(embeddings_enabled=True))
    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_all_embedded_returns_message(self, mock_conn, _mock_config):
        from otutil.tools.mem import reindex

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = reindex()
        assert "already have embeddings" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFlush:
    """Test mem.flush() queue drain, timeout, and dead-worker detection."""

    @pytest.fixture()
    def _worker_state(self):
        """Isolate embedding worker module state (incl. queue) around a test."""
        import queue as queue_mod

        from otutil.tools._mem import embedding as emb

        saved = (emb._embedding_worker_started, emb._embedding_worker_thread, emb._embedding_queue)
        emb._embedding_queue = queue_mod.Queue(maxsize=10)
        yield emb
        (emb._embedding_worker_started, emb._embedding_worker_thread, emb._embedding_queue) = saved

    def test_no_worker_returns_immediately(self):
        from otutil.tools.mem import flush

        result = flush()
        assert "No background embeddings pending" in result

    def test_dead_worker_detected(self, _worker_state):
        from otutil.tools.mem import flush

        emb = _worker_state
        emb._embedding_worker_started = True
        emb._embedding_worker_thread = MagicMock(is_alive=MagicMock(return_value=False))
        emb._embedding_queue.put_nowait("mem-id")

        result = flush(timeout=1.0)

        assert "Error" in result
        assert "worker is not running" in result

    def test_timeout_with_stuck_queue(self, _worker_state):
        from otutil.tools.mem import flush

        emb = _worker_state
        emb._embedding_worker_started = True
        emb._embedding_worker_thread = MagicMock(is_alive=MagicMock(return_value=True))
        emb._embedding_queue.put_nowait("mem-id")

        result = flush(timeout=0.15)

        assert "Error" in result
        assert "timed out" in result


@pytest.mark.unit
@pytest.mark.tools
class TestListMemories:
    """Test mem.list() with mocked database."""

    @patch("otutil.tools._mem.listing._get_connection")
    def test_lists_memories(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/one", "note", '["tag1"]', 5, 2, datetime.now().isoformat(), 100, None),
            ("id-2efgh", "topic/two", "rule", '[]', 8, 0, datetime.now().isoformat(), 200, None),
        ]

        result = list()

        assert "Found 2 memories" in result
        assert "topic/one" in result
        assert "topic/two" in result
        assert "category=note" in result
        assert "category=rule" in result
        assert "id=id-1abcd" in result
        assert "[note]" not in result  # old format gone
        assert "rel=8" in result  # non-default relevance shown
        assert "rel=5" not in result  # default relevance hidden

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_with_tags(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/tagged", "note", '["a", "b"]', 5, 0, datetime.now().isoformat(), 50, None),
        ]

        result = list()

        assert "tags=a|b" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_no_tags(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/notags", "note", '[]', 5, 0, datetime.now().isoformat(), 50, None),
        ]

        result = list()

        assert "tags=" not in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_rel_default_hidden(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/default", "note", '[]', 5, 0, datetime.now().isoformat(), 50, None),
        ]

        result = list()

        assert "rel=" not in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_rel_non_default_shown(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/high", "note", '[]', 8, 0, datetime.now().isoformat(), 50, None),
        ]

        result = list()

        assert "rel=8" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_sec_shown(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/sections", "context", '[]', 5, 0, datetime.now().isoformat(), 500,
             '{"section_count": "3"}'),
        ]

        result = list()

        assert "sec=3" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_list_format_sec_absent(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1abcd", "topic/nosec", "note", '[]', 5, 0, datetime.now().isoformat(), 50, None),
        ]

        result = list()

        assert "sec=" not in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_empty_list(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = list()

        assert "No memories found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestCount:
    """Test mem.count() with mocked database."""

    @patch("otutil.tools._mem.listing._get_connection")
    def test_counts_all(self, mock_conn):
        from otutil.tools.mem import count

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (42,)

        result = count()

        assert result == "42"


@pytest.mark.unit
@pytest.mark.tools
class TestDelete:
    """Test mem.delete() with mocked database."""

    @patch("otutil.tools._mem.mutations._use_connection")
    def test_deletes_by_id(self, mock_conn):
        from otutil.tools.mem import delete

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("id-123",)

        result = delete(id="id-123")

        assert "Deleted memory id-123" in result

    @patch("otutil.tools._mem.mutations._use_connection")
    def test_requires_confirm_for_multi_delete(self, mock_conn):
        from otutil.tools.mem import delete

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (5,)

        result = delete(topic="projects/")

        assert "confirm=True" in result

    def test_requires_topic_or_id(self):
        from otutil.tools.mem import delete

        result = delete()
        assert "Error" in result
        assert "Must specify" in result


@pytest.mark.unit
@pytest.mark.tools
class TestUpdate:
    """Test mem.update() with mocked database and embeddings."""

    @patch("otutil.tools._mem.mutations._embed_now")
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_updates_single_match(self, mock_conn, mock_embed):
        from otutil.tools.mem import update

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content", _content_hash("old content"), '{}'),
        ]

        result = update(topic="test/topic", content="new content")

        assert "Updated memory" in result

    @patch("otutil.tools._mem.mutations._use_connection")
    def test_rejects_multiple_matches(self, mock_conn):
        from otutil.tools.mem import update

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content 1", _content_hash("content 1"), '{}'),
            ("id-2", "content 2", _content_hash("content 2"), '{}'),
        ]

        result = update(topic="ambiguous/topic", content="new")

        assert "Multiple memories" in result

    @patch("otutil.tools._mem.mutations._use_connection")
    def test_not_found(self, mock_conn):
        from otutil.tools.mem import update

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = update(topic="nonexistent", content="new")

        assert "No memory found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestUpdateEmbeddingHandling:
    """Updates must not destroy stored embeddings when embeddings are disabled."""

    @patch("otutil.tools._mem.mutations._get_config", return_value=Config(embeddings_enabled=False))
    @patch("otutil.tools._mem.mutations._embed_now", return_value=None)
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_update_preserves_embedding_when_disabled(self, mock_conn, _mock_embed, _mock_config):
        from otutil.tools.mem import update

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content", _content_hash("old content"), '{}'),
        ]

        result = update(topic="test/topic", content="new content")

        assert "Updated memory" in result
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        assert len(update_calls) == 1
        # The embedding column must not be touched
        assert "embedding" not in update_calls[0][0][0]

    @patch("otutil.tools._mem.mutations._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=False))
    @patch("otutil.tools._mem.mutations._embed_now", return_value=[0.5, 0.5])
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_update_writes_embedding_when_enabled(self, mock_conn, _mock_embed, _mock_config):
        from otutil.tools._mem.db import _serialize_embedding
        from otutil.tools.mem import update

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content", _content_hash("old content"), '{}'),
        ]

        result = update(topic="test/topic", content="new content")

        assert "Updated memory" in result
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        assert len(update_calls) == 1
        assert "embedding" in update_calls[0][0][0]
        assert update_calls[0][0][1][2] == _serialize_embedding([0.5, 0.5])

    @patch("otutil.tools._mem.mutations._get_config", return_value=Config(embeddings_enabled=False))
    @patch("otutil.tools._mem.mutations._embed_now", return_value=None)
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_append_preserves_embedding_when_disabled(self, mock_conn, _mock_embed, _mock_config):
        from otutil.tools.mem import append

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "original content", _content_hash("original content"), '{}'),
        ]

        result = append(topic="test/topic", content="more")

        assert "Appended to memory" in result
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        assert len(update_calls) == 1
        assert "embedding" not in update_calls[0][0][0]


@pytest.mark.unit
@pytest.mark.tools
class TestAppend:
    """Test mem.append() with mocked database and embeddings."""

    @patch("otutil.tools._mem.mutations._embed_now")
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_appends_content(self, mock_conn, mock_embed):
        from otutil.tools.mem import append

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn

        # Mock for single match via fetchall (id, content, content_hash, meta)
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "original content", _content_hash("original content"), '{}'),
        ]

        result = append(topic="test/topic", content="appended text")

        assert "Appended to memory" in result


# ---------------------------------------------------------------------------
# Phase 2 tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestContext:
    """Test mem.context() hot cache loading."""

    @patch("otutil.tools._mem.maintenance._use_connection")
    def test_loads_top_accessed(self, mock_conn):
        from otutil.tools.mem import context

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "hot/topic", "frequently accessed content", "rule", ["tag"], 8, 100),
        ]

        result = context()

        assert "1 memories loaded" in result
        assert "hot/topic" in result
        assert "frequently accessed content" in result

    @patch("otutil.tools._mem.maintenance._use_connection")
    def test_empty_context(self, mock_conn):
        from otutil.tools.mem import context

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = context()

        assert "No memories found" in result


# ---------------------------------------------------------------------------
# Phase 3 tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestUpdateBatch:
    """Test mem.update_batch() search-and-replace."""

    @patch("otutil.tools._mem.maintenance._use_connection")
    def test_dry_run_preview(self, mock_conn):
        from otutil.tools.mem import update_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "old_name is used here", "{}"),
            ("id-2", "topic/two", "old_name appears twice: old_name", "{}"),
        ]

        result = update_batch(search_text="old_name", replace_text="new_name")

        assert "Dry run" in result
        assert "2 memories" in result

    @patch("otutil.tools._mem.maintenance._use_connection")
    def test_no_matches(self, mock_conn):
        from otutil.tools.mem import update_batch

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = update_batch(search_text="nonexistent", replace_text="new")

        assert "No memories contain" in result


@pytest.mark.unit
@pytest.mark.tools
class TestDecay:
    """Test mem.decay() importance decay."""

    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_decay_dry_run(self, mock_conn):
        from otutil.tools.mem import decay

        conn = MagicMock()
        mock_conn.return_value = conn
        # Memory created 60 days ago, accessed 0 times, relevance 10
        old_time = datetime(2025, 12, 1, tzinfo=UTC).isoformat()
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "old/topic", 10, 0, old_time),
        ]

        result = decay(dry_run=True)

        assert "Decay preview" in result

    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_empty_decay(self, mock_conn):
        from otutil.tools.mem import decay

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = decay()

        assert "No memories to decay" in result


@pytest.mark.unit
@pytest.mark.tools
class TestStats:
    """Test mem.stats() statistics."""

    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_shows_statistics(self, mock_conn):
        from otutil.tools.mem import stats

        conn = MagicMock()
        mock_conn.return_value = conn

        # Mock different queries in sequence
        conn.execute.return_value.fetchone.side_effect = [
            (10,),           # total count
            (5000, 500, 2000),  # size stats
            (3,),            # history count
            (2,),            # without embeddings count
            (7,),            # memories_vec row count (vec index status)
        ]
        conn.execute.return_value.fetchall.side_effect = [
            [("note", 5), ("rule", 3), ("decision", 2)],  # categories
            [("projects", 7), ("learnings", 3)],           # topics
        ]

        result = stats()

        assert "10" in result
        assert "Memory Statistics" in result
        assert "Embeddings:" in result
        assert "Search indexes:" in result

    @patch("otutil.tools._mem.lifecycle._get_connection")
    def test_empty_stats(self, mock_conn):
        from otutil.tools.mem import stats

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (0,)

        result = stats()

        assert "No memories stored" in result


@pytest.mark.unit
@pytest.mark.tools
class TestDump:
    """Test mem.dump() YAML output."""

    @patch("otutil.tools._mem.io._get_connection")
    def test_dump_yaml(self, mock_conn):
        from otutil.tools.mem import dump

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", '["tag1"]', 5, 2, datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        result = dump()

        assert "memories:" in result
        assert "topic/one" in result
        assert "content one" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._get_connection")
    def test_dump_to_file(self, mock_conn, tmp_path):
        from otutil.tools.mem import dump

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content", "note", '[]', 5, 0, datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_file = tmp_path / "export.yaml"
        result = dump(output=str(out_file))

        assert "Dumped 1 memories" in result
        assert out_file.exists()

    @patch("otutil.tools._mem.io._get_connection")
    def test_empty_dump(self, mock_conn):
        from otutil.tools.mem import dump

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = dump()

        assert "No memories to dump" in result


@pytest.mark.unit
@pytest.mark.tools
class TestLoad:
    """Test mem.load() YAML import."""

    @pytest.mark.usefixtures("_mock_cwd")
    def test_file_not_found(self, tmp_path):
        from otutil.tools.mem import load

        result = load(file=str(tmp_path / "nonexistent.yaml"))
        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._embed_now")
    @patch("otutil.tools._mem.io._use_connection")
    def test_imports_from_yaml(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import load

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No existing

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - topic: "test/topic"\n'
            '    content: "imported content"\n'
            '    category: "note"\n'
            '    tags: ["imported"]\n'
            '    relevance: 7\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 1 memories" in result


@pytest.mark.unit
@pytest.mark.tools
class TestLoadInvariants:
    """load() must apply the same redaction/validation as mem.write()."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._embed_now", return_value=None)
    @patch("otutil.tools._mem.io._use_connection")
    def test_load_redacts_content(self, mock_conn, _mock_embed, tmp_path):
        from otutil.tools.mem import load

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - topic: "test/leaky"\n'
            '    content: "key: sk-abc123def456ghi789jkl0123"\n'
            '    category: "note"\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 1 memories" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        content_param = insert_calls[0][0][1][2]
        assert "sk-" not in content_param
        assert "[REDACTED:api_key]" in content_param

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._embed_now", return_value=None)
    @patch("otutil.tools._mem.io._use_connection")
    def test_load_rejects_invalid_category(self, mock_conn, _mock_embed, tmp_path):
        from otutil.tools.mem import load

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - topic: "test/bad"\n'
            '    content: "content"\n'
            '    category: "not-a-category"\n'
            '  - topic: "test/good"\n'
            '    content: "content"\n'
            '    category: "note"\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 1 memories" in result
        assert "1 malformed" in result
        assert "Invalid category" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1][1] == "test/good"


@pytest.mark.unit
@pytest.mark.tools
class TestLoadDump:
    """Test mem.load() dump surface."""

    def test_load_is_exported(self) -> None:
        from otutil.tools import mem

        assert "load" in mem.__all__
        assert callable(mem.load)

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._embed_now")
    @patch("otutil.tools._mem.io._use_connection")
    def test_load_imports_export_yaml_and_restores_meta(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import load

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - id: "mem-1"\n'
            '    topic: "test/topic"\n'
            '    content: |-\n'
            '      imported content\n'
            '    category: "note"\n'
            '    tags: ["imported"]\n'
            '    relevance: 7\n'
            '    access_count: 2\n'
            '    created_at: "2026-05-13 00:00:00"\n'
            '    updated_at: "2026-05-13 00:00:00"\n'
            '    meta: \'{"sections": "Intro:1-2"}\'\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 1 memories" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        params = insert_calls[0][0][1]
        assert params[0] == "mem-1"
        assert params[1] == "test/topic"
        assert params[4] == "note"
        assert params[5] == '["imported"]'
        assert params[6] == 7
        assert params[8] == '{"sections": "Intro:1-2"}'

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.io._embed_now")
    @patch("otutil.tools._mem.io._use_connection")
    def test_load_skips_duplicates(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import load

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - topic: "test/topic"\n'
            '    content: "imported content"\n'
            '    category: "note"\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 0 memories, skipped 1 duplicates" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert insert_calls == []


@pytest.mark.unit
@pytest.mark.tools
class TestSnapshot:
    """Test mem.snapshot() file-based snapshot."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_creates_files_and_index(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "docs/readme", "# README content", "note", '["tag1"]', 5, 2,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "backup"
        result = snapshot(output=str(out_dir))

        assert "Snapshot 1 memories" in result
        assert (out_dir / "docs/readme").exists()
        assert (out_dir / "docs/readme").read_text() == "# README content"
        assert (out_dir / "index.yaml").exists()
        index_text = (out_dir / "index.yaml").read_text()
        assert "docs/readme" in index_text

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_with_topic_filter(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "consult/ask", "ask content", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
            ("id-2", "consult/mem-tool", "mem content", "discovery", '[]', 7, 1,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "snap"
        result = snapshot(output=str(out_dir), topic="consult/")

        assert "Snapshot 2 memories" in result
        # Topic prefix stripped: "consult/ask" -> "ask"
        assert (out_dir / "ask").exists()
        assert (out_dir / "mem-tool").exists()

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_skip_existing(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "notes/a", "content a", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "snap"
        out_dir.mkdir()
        (out_dir / "notes").mkdir()
        (out_dir / "notes/a").write_text("existing")

        result = snapshot(output=str(out_dir), on_conflict="skip")

        assert "1 skipped" in result
        assert (out_dir / "notes/a").read_text() == "existing"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_overwrite_existing(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "notes/a", "new content", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "snap"
        out_dir.mkdir()
        (out_dir / "notes").mkdir()
        (out_dir / "notes/a").write_text("old content")

        result = snapshot(output=str(out_dir), on_conflict="overwrite")

        assert "1 written" in result
        assert (out_dir / "notes/a").read_text() == "new content"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_nested_topics(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "consult/sub/deep", "deep content", "rule", '["important"]', 9, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "snap"
        result = snapshot(output=str(out_dir), topic="consult/")

        assert "Snapshot 1 memories" in result
        assert (out_dir / "sub/deep").exists()
        assert (out_dir / "sub/deep").read_text() == "deep content"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_meta_special_chars_round_trips(self, mock_conn, tmp_path):
        """meta with pipes, colons, and quotes must survive YAML round-trip."""
        import yaml

        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        meta_json = '{"sections": "Attack Summary:277-290|What It Doesn\'t Do:291-302|Recs:303"}'
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "tmp/security", "content", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), meta_json),
        ]

        out_dir = tmp_path / "snap"
        result = snapshot(output=str(out_dir))

        assert "Snapshot 1 memories" in result
        # Verify index.yaml parses cleanly
        index_data = yaml.safe_load((out_dir / "index.yaml").read_text())
        assert index_data is not None
        mem = index_data["memories"][0]
        assert "sections" in mem["meta"]
        assert "|" in mem["meta"]["sections"]
        assert ":" in mem["meta"]["sections"]


@pytest.mark.unit
@pytest.mark.tools
class TestRestore:
    """Test mem.restore() from snapshot directory."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._embed_now")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_from_snapshot(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No existing

        # Create snapshot directory
        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "ask.md").write_text("ask content")
        (snap_dir / "index.yaml").write_text(
            'snapshot:\n'
            '  topic_filter: "consult/"\n'
            '  count: 1\n'
            'memories:\n'
            '  - topic: "consult/ask"\n'
            '    file: "ask.md"\n'
            '    category: "note"\n'
            '    tags: ["research"]\n'
            '    relevance: 7\n'
        )

        result = restore(input=str(snap_dir))

        assert "Restored 1 memories" in result
        # Verify INSERT was called with correct topic and metadata
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        insert_params = insert_calls[0][0][1]
        assert insert_params[1] == "consult/ask"  # topic
        assert insert_params[4] == "note"  # category
        assert insert_params[5] == '["research"]'  # tags (JSON)
        assert insert_params[6] == 7  # relevance

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._embed_now")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_skips_duplicates(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)  # Already exists

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "a.md").write_text("content")
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "a.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "skipped 1" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._embed_now")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_overwrite(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "a.md").write_text("new content")
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "a.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir), overwrite=True)

        assert "Restored 1 memories" in result
        # Should have DELETE + INSERT
        delete_calls = [c for c in conn.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) >= 1
        # Overwrite must also remove the replaced memory's history rows
        history_deletes = [c for c in delete_calls if "memory_history" in str(c)]
        assert len(history_deletes) == 1
        assert history_deletes[0][0][1] == ["existing-id"]

    @pytest.mark.usefixtures("_mock_cwd")
    def test_restore_missing_index(self, tmp_path):
        from otutil.tools.mem import restore

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()

        result = restore(input=str(snap_dir))

        assert "Error" in result
        assert "index.yaml" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_missing_file(self, mock_conn, tmp_path):
        from otutil.tools.mem import restore

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "missing.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "1 errors" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._embed_now")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_topic_override(self, mock_conn, mock_embed, tmp_path):
        from otutil.tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "ask.md").write_text("content")
        (snap_dir / "index.yaml").write_text(
            'snapshot:\n'
            '  topic_filter: "consult/"\n'
            'memories:\n'
            '  - topic: "consult/ask"\n'
            '    file: "ask.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir), topic="new-base")

        assert "Restored 1 memories" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        insert_params = insert_calls[0][0][1]
        assert insert_params[1] == "new-base/ask"  # remapped topic


@pytest.mark.unit
@pytest.mark.tools
class TestSnapshotRestorePathSafety:
    """Snapshot/restore must confine topic-derived paths to the target directory."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_rejects_traversal_topic(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "../evil", "escape attempt", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
            ("id-2", "safe/topic", "safe content", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        out_dir = tmp_path / "backup"
        result = snapshot(output=str(out_dir))

        assert "1 errors" in result
        assert "unsafe path" in result
        assert not (tmp_path / "evil").exists()
        assert (out_dir / "safe/topic").exists()

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._get_connection")
    def test_snapshot_rejects_absolute_topic(self, mock_conn, tmp_path):
        from otutil.tools.mem import snapshot

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "/etc/passwd-clone", "escape attempt", "note", '[]', 5, 0,
             datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        result = snapshot(output=str(tmp_path / "backup"))

        assert "1 errors" in result
        assert "unsafe path" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_rejects_traversal_file(self, mock_conn, tmp_path):
        from otutil.tools.mem import restore

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        # A secret file outside the snapshot dir that must not be readable
        (tmp_path / "secret.txt").write_text("secret data")
        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "../secret.txt"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "1 errors" in result
        assert "unsafe path" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert insert_calls == []


@pytest.mark.unit
@pytest.mark.tools
class TestRestoreInvariants:
    """Restore must apply the same redaction/validation as mem.write()."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.snapshots._use_connection")
    def test_restore_redacts_and_validates_category(self, mock_conn, tmp_path):
        from otutil.tools.mem import restore

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "leaky.md").write_text("key: sk-abc123def456ghi789jkl0123")
        (snap_dir / "bad.md").write_text("content")
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/leaky"\n'
            '    file: "leaky.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
            '  - topic: "test/bad"\n'
            '    file: "bad.md"\n'
            '    category: "not-a-category"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "Restored 1 memories" in result
        assert "1 errors" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        content_param = insert_calls[0][0][1][2]
        assert "sk-" not in content_param
        assert "[REDACTED:api_key]" in content_param


# ---------------------------------------------------------------------------
# OpenAI client tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetEmbeddingClient:
    """Test _get_embedding_client adapter."""

    def _reset(self):
        import otutil.tools._mem.embedding as emb_mod
        emb_mod._client = None
        emb_mod._client_key = None

    @patch("otutil.tools._mem.embedding.get_secret")
    def test_raises_without_api_key(self, mock_secret):
        from otutil.tools._mem.embedding import _get_embedding_client

        mock_secret.return_value = ""
        self._reset()

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _get_embedding_client()

    @patch("otutil.tools._mem.embedding.get_llm_config")
    @patch("otutil.tools._mem.embedding._get_config")
    @patch("otutil.tools._mem.embedding.get_secret")
    def test_builds_client_with_mem_prefix(self, mock_secret, mock_cfg, mock_llm):
        from otutil.tools._mem.embedding import _get_embedding_client

        mock_secret.return_value = "sk-test"
        mock_cfg.return_value.model = "text-embedding-3-small"
        mock_cfg.return_value.base_url = ""
        mock_cfg.return_value.max_embedding_tokens = 8191
        mock_llm.return_value.base_url = ""
        self._reset()

        client = _get_embedding_client()

        assert client._log_prefix == "mem"
        assert client.model == "text-embedding-3-small"
        self._reset()


@pytest.mark.unit
@pytest.mark.tools
class TestChunkTextByTokens:
    """Token-aware splitting (shared otpack implementation)."""

    def test_short_text_single_chunk(self):
        from otpack import chunk_text_by_tokens as _chunk_text_by_tokens

        chunks = _chunk_text_by_tokens("hello world", 8191, "text-embedding-3-small")
        assert chunks == ["hello world"]

    def test_long_text_splits_into_chunks(self):
        from otpack import chunk_text_by_tokens as _chunk_text_by_tokens

        text = "word " * 20000  # ~20000 tokens
        chunks = _chunk_text_by_tokens(text, 100, "text-embedding-3-small")
        assert len(chunks) > 1
        # Each chunk should decode back to valid text
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0

    def test_exact_limit_single_chunk(self):
        import tiktoken

        from otpack import chunk_text_by_tokens as _chunk_text_by_tokens

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        text = "hello world this is a test"
        token_count = len(encoding.encode(text))
        chunks = _chunk_text_by_tokens(text, token_count, "text-embedding-3-small")
        assert chunks == [text]

    def test_unknown_model_falls_back(self):
        from otpack import chunk_text_by_tokens as _chunk_text_by_tokens

        chunks = _chunk_text_by_tokens("hello world", 8191, "unknown-model-xyz")
        assert chunks == ["hello world"]

    def test_chunks_cover_all_content(self):
        import tiktoken

        from otpack import chunk_text_by_tokens as _chunk_text_by_tokens

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        text = "word " * 500  # moderate text
        chunks = _chunk_text_by_tokens(text, 100, "text-embedding-3-small")
        # Rejoin all chunk tokens — should equal original tokens
        original_tokens = encoding.encode(text)
        chunk_tokens = []
        for chunk in chunks:
            chunk_tokens.extend(encoding.encode(chunk))
        assert len(chunk_tokens) == len(original_tokens)


@pytest.mark.unit
@pytest.mark.tools
class TestGenerateEmbedding:
    """_generate_embedding via the shared otpack client (mean strategy)."""

    def _make_client(self, **kwargs):
        from otpack import EmbeddingClient

        defaults = {"api_key": "sk-test", "model": "text-embedding-3-small", "log_prefix": "mem"}
        defaults.update(kwargs)
        client = EmbeddingClient(**defaults)
        mock_openai = MagicMock()
        client._client = mock_openai
        return client, mock_openai.embeddings.create

    @staticmethod
    def _resp(vecs):
        data = []
        for i, vec in enumerate(vecs):
            item = MagicMock()
            item.index = i
            item.embedding = vec
            data.append(item)
        resp = MagicMock()
        resp.data = data
        return resp

    def test_generates_embedding_short_text(self):
        from otutil.tools._mem.embedding import _generate_embedding

        client, create = self._make_client()
        create.return_value = self._resp([[0.1, 0.2, 0.3]])
        with patch("otutil.tools._mem.embedding._get_embedding_client", return_value=client):
            result = _generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        create.assert_called_once()

    def test_averages_multi_window_embeddings(self):
        """Long text is window-embedded in one batch and element-wise averaged."""
        from otutil.tools._mem.embedding import _generate_embedding

        client, create = self._make_client(max_tokens=110)  # effective limit 10
        create.side_effect = lambda **kw: self._resp(
            [[float(i), 1.0] for i in range(len(kw["input"]))]
        )
        long_text = "word " * 25  # > 10 tokens → multiple windows
        with patch("otutil.tools._mem.embedding._get_embedding_client", return_value=client):
            result = _generate_embedding(long_text)

        sent = create.call_args.kwargs["input"]
        n = len(sent)
        assert n > 1  # all windows in one batched call
        assert result[0] == pytest.approx(sum(range(n)) / n)  # element-wise mean
        assert result[1] == pytest.approx(1.0)

    def test_sync_path_retries_transient_429(self):
        """The sync embed path retries HTTP 429 (converged retry policy)."""
        from otutil.tools._mem.embedding import _generate_embedding

        client, create = self._make_client()
        err = type("APIStatusError", (Exception,), {"status_code": 429})("rate limited")
        create.side_effect = [err, self._resp([[0.7]])]
        with (
            patch("otutil.tools._mem.embedding._get_embedding_client", return_value=client),
            patch("otpack.embedding.time"),
        ):
            result = _generate_embedding("test text")

        assert result == [0.7]
        assert create.call_count == 2

    def test_repeated_query_embedding_hits_cache(self):
        """_generate_query_embedding serves repeats from the LRU cache."""
        from otutil.tools._mem.embedding import _generate_query_embedding

        client, create = self._make_client()
        create.return_value = self._resp([[0.9]])
        with patch("otutil.tools._mem.embedding._get_embedding_client", return_value=client):
            _generate_query_embedding("same query")
            _generate_query_embedding("same query")

        assert create.call_count == 1


# ---------------------------------------------------------------------------
# Path security tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("_mock_cwd")
class TestFilePathSecurity:
    """Test that file operations reject paths outside allowed directories."""

    def test_write_rejects_absolute_path_outside_cwd(self):
        from otutil.tools.mem import write

        result = write(topic="test", file="/etc/passwd")

        assert "Error" in result
        assert "outside allowed directories" in result

    def test_write_rejects_path_traversal(self, tmp_path):
        from otutil.tools.mem import write

        result = write(topic="test", file="../../../etc/passwd")

        assert "Error" in result
        # Rejected by path validation (either "not found" or "outside allowed")
        assert "not found" in result.lower() or "outside allowed" in result

    def test_write_rejects_home_dir_file(self):
        from otutil.tools.mem import write

        result = write(topic="test", file="~/.ssh/id_rsa")

        assert "Error" in result
        assert "not found" in result.lower() or "outside allowed" in result

    @patch("otutil.tools._mem.io._get_connection")
    def test_dump_rejects_path_outside_cwd(self, mock_conn):
        from otutil.tools.mem import dump

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content", "note", '[]', 5, 0, datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        result = dump(output="/tmp/evil_export.yaml")

        assert "Error" in result
        assert "outside allowed directories" in result

    def test_load_rejects_path_outside_cwd(self):
        from otutil.tools.mem import load

        result = load(file="/etc/shadow")

        assert "Error" in result
        assert "not found" in result.lower() or "outside allowed" in result

    def test_write_rejects_excluded_pattern(self, tmp_path):
        from otutil.tools.mem import write

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text("secret")

        result = write(topic="test", file=str(config))

        assert "Error" in result
        assert "exclude pattern" in result


# ---------------------------------------------------------------------------
# Validation and safety fix tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestWriteValidation:
    """Test write() input validation for relevance and file size."""

    def test_rejects_relevance_below_range(self):
        from otutil.tools.mem import write

        result = write(topic="test", content="x", relevance=0)
        assert "Error" in result
        assert "relevance" in result

    def test_rejects_relevance_above_range(self):
        from otutil.tools.mem import write

        result = write(topic="test", content="x", relevance=11)
        assert "Error" in result
        assert "relevance" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("otutil.tools._mem.write._use_connection")
    def test_rejects_large_file(self, mock_conn, tmp_path):
        from otutil.tools.mem import write

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn

        big_file = tmp_path / "big.txt"
        big_file.write_bytes(b"x" * 1_100_000)

        result = write(topic="test", file=str(big_file))

        assert "Error" in result
        assert "too large" in result.lower()

    def test_empty_string_content_accepted(self):
        """Empty string content is explicitly provided, should not be confused with None."""
        from otutil.tools.mem import write

        # Empty content should hit category/relevance validation or DB, not "Provide content or file"
        result = write(topic="test", content="", relevance=0)
        assert "relevance" in result  # hits relevance check, not "Provide content"


@pytest.mark.unit
@pytest.mark.tools
class TestDumpYaml:
    """Test _export_yaml output and round-trip safety."""

    def test_multiline_content_uses_block_scalar(self):
        from otutil.tools._mem.io import _export_yaml

        rows = [
            ("id-1", "topic/one", "line one\nline two\nline three", "note", '["tag"]', 5, 2, datetime.now().isoformat(), datetime.now().isoformat(), "{}"),
        ]

        result = _export_yaml(rows)

        assert "content: |-" in result
        assert "line one" in result
        assert "line two" in result
        # Should NOT have broken YAML double-quoted strings
        assert 'content: "' not in result

    def test_quotes_round_trip(self):
        """Quotes in topic/content/tags must survive dump -> load parsing."""
        import yaml

        from otutil.tools._mem.io import _export_yaml

        content = 'He said "hello" and \'bye\'\nsecond "quoted" line'
        topic = 'topic/with "quotes"'
        rows = [
            ("id-1", topic, content, "note", '["ta\\"g"]', 5, 0,
             "2026-01-01 00:00:00", "2026-01-01 00:00:00", '{"key": "va\\"lue"}'),
        ]

        result = _export_yaml(rows)
        data = yaml.safe_load(result)

        mem = data["memories"][0]
        assert mem["topic"] == topic
        assert mem["content"] == content
        assert mem["tags"] == ['ta"g']
        assert mem["meta"] == {"key": 'va"lue'}
        assert mem["created_at"] == "2026-01-01 00:00:00"


# ---------------------------------------------------------------------------
# Navigation tests: heading parser, encoder, toc, slice
# ---------------------------------------------------------------------------

SAMPLE_MD = """\
# Introduction

Some intro text.

## Requirements

### Requirement: Search

Search details here.

## Configuration

Config details here.
"""


@pytest.mark.unit
@pytest.mark.tools
class TestParseHeadings:
    """Test _parse_headings markdown heading parser."""

    def test_parses_h1_h2_h3(self):
        headings = _parse_headings(SAMPLE_MD)
        names = [h["heading"] for h in headings]
        assert names == ["Introduction", "Requirements", "Requirement: Search", "Configuration"]

    def test_respects_max_depth(self):
        headings = _parse_headings(SAMPLE_MD, max_depth=2)
        names = [h["heading"] for h in headings]
        assert "Requirement: Search" not in names
        assert "Introduction" in names
        assert "Requirements" in names

    def test_line_ranges(self):
        headings = _parse_headings(SAMPLE_MD)
        # First section starts at line 1
        assert headings[0]["start"] == 1
        # Each section ends before the next starts
        for i in range(len(headings) - 1):
            assert headings[i]["end"] == headings[i + 1]["start"] - 1
        # Last section ends at total lines
        total_lines = len(SAMPLE_MD.split("\n"))
        assert headings[-1]["end"] == total_lines

    def test_empty_content(self):
        assert _parse_headings("") == []

    def test_no_headings(self):
        assert _parse_headings("just plain text\nno headings here") == []


@pytest.mark.unit
@pytest.mark.tools
class TestSectionEncoder:
    """Test _encode_sections / _decode_sections round-trip."""

    def test_round_trip(self):
        headings = _parse_headings(SAMPLE_MD)
        encoded = _encode_sections(headings)
        decoded = _decode_sections(encoded)
        assert len(decoded) == len(headings)
        for orig, dec in zip(headings, decoded):
            assert dec["heading"] == orig["heading"]
            assert dec["start"] == orig["start"]
            assert dec["end"] == orig["end"]

    def test_empty_encode(self):
        assert _encode_sections([]) == ""

    def test_empty_decode(self):
        assert _decode_sections("") == []

    def test_heading_with_colon(self):
        """Headings containing colons should round-trip correctly."""
        headings = [{"heading": "Requirement: Search", "start": 1, "end": 10}]
        encoded = _encode_sections(headings)
        decoded = _decode_sections(encoded)
        assert decoded[0]["heading"] == "Requirement: Search"
        assert decoded[0]["start"] == 1
        assert decoded[0]["end"] == 10

    def test_heading_with_pipe(self):
        """Headings containing pipes should round-trip correctly."""
        headings = [
            {"heading": "A | B", "start": 1, "end": 5},
            {"heading": "Normal", "start": 6, "end": 10},
        ]
        encoded = _encode_sections(headings)
        decoded = _decode_sections(encoded)
        assert len(decoded) == 2
        assert decoded[0]["heading"] == "A | B"
        assert decoded[1]["heading"] == "Normal"


@pytest.mark.unit
@pytest.mark.tools
class TestBuildToc:
    """Test _build_toc formatting."""

    def test_formats_numbered_sections(self):
        sections = _decode_sections("Intro:1-5|Details:6-20")
        toc = _build_toc(sections, "x\n" * 20)
        assert "1. Intro (lines 1-5)" in toc
        assert "2. Details (lines 6-20)" in toc
        assert "2 sections" in toc

    def test_empty_sections(self):
        assert "No sections found" in _build_toc([], "content")


@pytest.mark.unit
@pytest.mark.tools
class TestTocFunction:
    """Test mem.toc() with mocked database."""

    @patch("otutil.tools._mem.slicing._use_connection")
    def test_returns_toc(self, mock_conn):
        from otutil.tools.mem import toc

        sections_str = _encode_sections(_parse_headings(SAMPLE_MD))
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "spec", SAMPLE_MD, "note", '[]', 5, 0,
            datetime.now().isoformat(), datetime.now().isoformat(),
            _serialize_meta({"sections": sections_str, "section_count": "4"}),
        )

        result = toc(topic="spec")
        assert "Introduction" in result
        assert "Requirements" in result
        assert "4 sections" in result

    @patch("otutil.tools._mem.slicing._use_connection")
    def test_not_found(self, mock_conn):
        from otutil.tools.mem import toc

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = toc(topic="nonexistent")
        assert "No memory found" in result

    @patch("otutil.tools._mem.slicing._use_connection")
    def test_staleness_warning(self, mock_conn, tmp_path):
        from otutil.tools.mem import toc

        source_file = tmp_path / "spec.md"
        source_file.write_text(SAMPLE_MD)
        old_mtime = str(source_file.stat().st_mtime - 100)  # pretend stored mtime is older

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "spec", SAMPLE_MD, "note", '[]', 5, 0,
            datetime.now().isoformat(), datetime.now().isoformat(),
            _serialize_meta({"sections": "Intro:1-3", "source": str(source_file), "source_mtime": old_mtime}),
        )

        result = toc(topic="spec")
        assert "modified since" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSliceFunction:
    """Test mem.slice() with mocked database."""

    @pytest.fixture()
    def _mock_slice_conn(self):
        """Set up a mock connection returning SAMPLE_MD with sections."""
        sections_str = _encode_sections(_parse_headings(SAMPLE_MD))
        row = (
            "id-1", "spec", SAMPLE_MD, "note", '[]', 5, 0,
            datetime.now().isoformat(), datetime.now().isoformat(),
            _serialize_meta({"sections": sections_str, "section_count": "4"}),
        )
        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchone.return_value = row
            yield

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_by_section_number(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select=1)
        assert "Introduction" in result
        assert "Some intro text" in result

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_by_heading(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select="Configuration")
        assert "Config details" in result

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_by_heading_case_insensitive(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select="configuration")
        assert "Config details" in result

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_by_line_range(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select=":3")
        lines = result.split("\n")
        assert len(lines) == 3

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_mixed_list(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select=[1, "Configuration"])
        assert "Introduction" in result
        assert "Config details" in result

    @pytest.mark.usefixtures("_mock_slice_conn")
    def test_slice_no_match(self):
        from otutil.tools.mem import slice

        result = slice(topic="spec", select="nonexistent heading")
        assert "No matching content" in result

    @patch("otutil.tools._mem.slicing._use_connection")
    def test_slice_not_found(self, mock_conn):
        from otutil.tools.mem import slice

        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = slice(topic="nonexistent", select=1)
        assert "No memory found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestReadMode:
    """Test that mem.read() raises ValueError for removed mode parameter."""

    def test_mode_toc_raises_with_redirect(self):
        from otutil.tools.mem import read

        with pytest.raises(ValueError, match="mem.toc"):
            read(topic="spec", mode="toc")

    def test_mode_meta_raises_with_redirect(self):
        from otutil.tools.mem import read

        with pytest.raises(ValueError, match="mem.inspect"):
            read(topic="spec", mode="meta")

    def test_mode_all_raises_with_redirect(self):
        from otutil.tools.mem import read

        with pytest.raises(ValueError, match="meta=True"):
            read(topic="spec", mode="all")

    def test_mode_unknown_raises(self):
        from otutil.tools.mem import read

        with pytest.raises(ValueError, match="no longer accepts mode="):
            read(topic="spec", mode="invalid")


@pytest.mark.unit
@pytest.mark.tools
class TestInspect:
    """Test mem.inspect() structured metadata."""

    @patch("otutil.tools._mem.inspect._get_connection")
    def test_returns_metadata_dict(self, mock_conn):
        from otutil.tools.mem import inspect

        sections_str = _encode_sections(_parse_headings(SAMPLE_MD))
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "spec", "rule", '["tag1"]', 7, 3,
            datetime.now().isoformat(), datetime.now().isoformat(),
            _serialize_meta({"sections": sections_str, "section_count": "4"}),
        )

        result = inspect(topic="spec")

        assert result["id"] == "id-1"
        assert result["topic"] == "spec"
        assert result["category"] == "rule"
        assert result["tags"] == ["tag1"]
        assert result["relevance"] == 7
        assert result["access_count"] == 3
        assert result["toc_entry_count"] == 4

    @patch("otutil.tools._mem.inspect._get_connection")
    def test_not_found_returns_error(self, mock_conn):
        from otutil.tools.mem import inspect

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = inspect(topic="missing/topic")
        assert "error" in result

    @patch("otutil.tools._mem.inspect._get_connection")
    def test_no_toc_returns_zero_count(self, mock_conn):
        from otutil.tools.mem import inspect

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "plain", "note", '[]', 5, 0,
            datetime.now().isoformat(), datetime.now().isoformat(),
            _serialize_meta({}),
        )

        result = inspect(topic="plain")
        assert result["toc_entry_count"] == 0


@pytest.mark.unit
@pytest.mark.tools
class TestAsk:
    """Test mem.ask() LLM synthesis."""

    @patch("otutil.tools._mem.ask._get_connection")
    def test_not_found_returns_error(self, mock_conn):
        from otutil.tools.mem import ask

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = ask(topic="missing/topic", q="What is this?")
        assert "error" in result

    @patch("otutil.tools._mem.ask._get_connection")
    def test_ot_llm_not_installed_returns_error(self, mock_conn):
        import sys

        from otutil.tools.mem import ask

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "docs/api", "API documentation content",
        )

        with patch.dict(sys.modules, {"ottools.ot_llm": None}):
            result = ask(topic="docs/api", q="What endpoints exist?")
        assert "error" in result
        assert "ot_llm" in result["error"]

    @patch("otutil.tools._mem.ask._get_connection")
    def test_single_question_returns_answer(self, mock_conn):
        import types

        from otutil.tools.mem import ask

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "docs/api", "The main endpoint is /health.",
        )

        fake_llm_mod = types.ModuleType("ottools.ot_llm")
        fake_llm_mod.transform = MagicMock(return_value="The /health endpoint.")  # type: ignore[attr-defined]
        with patch.dict("sys.modules", {"ottools": MagicMock(), "ottools.ot_llm": fake_llm_mod}):
            result = ask(topic="docs/api", q="What is the main endpoint?")

        assert "result" in result
        assert result["result"][0]["question"] == "What is the main endpoint?"
        assert result["result"][0]["answer"] == "The /health endpoint."


@pytest.mark.unit
@pytest.mark.tools
class TestQuery:
    """Test mem.query() JMESPath queries."""

    @patch("otutil.tools._mem.query._get_connection")
    def test_not_found_returns_error(self, mock_conn):
        from otutil.tools.mem import query

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = query(topic="missing/topic", expr="name")
        assert "error" in result

    @patch("otutil.tools._mem.query._get_connection")
    def test_json_content_query(self, mock_conn):
        import json

        from otutil.tools.mem import query

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "config/servers",
            json.dumps({"servers": [{"host": "alpha"}, {"host": "beta"}]}),
        )

        result = query(topic="config/servers", expr="servers[0].host")
        assert result.get("result") == "alpha"

    @patch("otutil.tools._mem.query._get_connection")
    def test_non_json_returns_error(self, mock_conn):
        from otutil.tools.mem import query

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "plain/text",
            "This is just plain text content.",
        )

        result = query(topic="plain/text", expr="name")
        assert "error" in result
        assert "JSON or YAML" in result["error"]

    @patch("otutil.tools._mem.query._get_connection")
    def test_no_match_returns_error(self, mock_conn):
        import json

        from otutil.tools.mem import query

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-1", "config/data", json.dumps({"name": "onetool"}),
        )

        result = query(topic="config/data", expr="nonexistent.path")
        assert "error" in result
        assert result["error"] == "No match"


@pytest.mark.unit
@pytest.mark.tools
class TestWriteWithToc:
    """Test mem.write() with toc=True."""

    @patch("otutil.tools._mem.write._embed_now")
    @patch("otutil.tools._mem.write._use_connection")
    def test_stores_sections_in_meta(self, mock_conn, mock_embed):
        from otutil.tools.mem import write

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No duplicate

        result = write(topic="spec", content=SAMPLE_MD, toc=True)

        assert "Stored memory" in result
        assert "toc:" in result
        assert "4 sections" in result
        # Verify meta was passed in INSERT (serialised as JSON)
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        insert_params = insert_calls[0][0][1]
        meta = _deserialize_meta(insert_params[8])  # meta is 9th parameter (JSON string)
        assert "sections" in meta
        assert "section_count" in meta
        assert meta["section_count"] == "4"

    @patch("otutil.tools._mem.write._embed_now")
    @patch("otutil.tools._mem.write._use_connection")
    def test_without_toc_has_empty_meta(self, mock_conn, mock_embed):
        from otutil.tools.mem import write

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        write(topic="simple", content="no headings", toc=False)

        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        insert_params = insert_calls[0][0][1]
        meta = _deserialize_meta(insert_params[8])
        assert meta == {}


@pytest.mark.unit
@pytest.mark.tools
class TestUpdateRecomputesToc:
    """Test that update() recomputes toc when sections exist in meta."""

    @patch("otutil.tools._mem.mutations._embed_now")
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_recomputes_sections(self, mock_conn, mock_embed):
        from otutil.tools.mem import update

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn

        old_sections = _encode_sections([{"heading": "Old", "start": 1, "end": 5}])
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content", _content_hash("old content"), _serialize_meta({"sections": old_sections, "section_count": "1"})),
        ]

        new_content = "# New Heading\n\nNew content\n\n## Second\n\nMore"
        result = update(topic="test/topic", content=new_content)

        assert "Updated memory" in result
        # Verify UPDATE was called with recomputed meta (serialised as JSON).
        # Embeddings are disabled by default, so the UPDATE omits the
        # embedding column: params include content, hash, meta, and CAS fields.
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        assert len(update_calls) >= 1
        update_params = update_calls[0][0][1]
        meta = _deserialize_meta(update_params[2])
        assert "sections" in meta
        assert meta["section_count"] == "2"

    @patch("otutil.tools._mem.mutations._embed_now")
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_no_recompute_without_sections(self, mock_conn, mock_embed):
        from otutil.tools.mem import update

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content", _content_hash("old content"), '{}'),
        ]

        result = update(topic="test/topic", content="# New\n\nContent")

        assert "Updated memory" in result
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        update_params = update_calls[0][0][1]
        meta = _deserialize_meta(update_params[2])
        assert "sections" not in meta


@pytest.mark.unit
@pytest.mark.tools
class TestAppendRecomputesToc:
    """Test that append() recomputes toc when sections exist in meta."""

    @patch("otutil.tools._mem.mutations._embed_now")
    @patch("otutil.tools._mem.mutations._use_connection")
    def test_recomputes_sections_on_append(self, mock_conn, mock_embed):
        from otutil.tools.mem import append

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn

        old_sections = _encode_sections([{"heading": "Old", "start": 1, "end": 3}])
        conn.execute.return_value.rowcount = 1
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "# Old\n\nOld content", _content_hash("# Old\n\nOld content"), _serialize_meta({"sections": old_sections, "section_count": "1"})),
        ]

        result = append(topic="test/topic", content="# New Section\n\nAppended")

        assert "Appended to memory" in result
        # Embeddings disabled by default: params include CAS predecessor fields.
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE memories" in str(c)]
        assert len(update_calls) >= 1
        update_params = update_calls[0][0][1]
        meta = _deserialize_meta(update_params[2])
        assert "sections" in meta
        assert meta["section_count"] == "2"


@pytest.mark.unit
@pytest.mark.tools
class TestResolveLineRange:
    """Test _resolve_line_range helper."""

    def test_first_n_lines(self):
        from otutil.tools._mem.slicing import _resolve_line_range

        lines = ["a", "b", "c", "d", "e"]
        assert _resolve_line_range(":3", lines, 5) == "a\nb\nc"

    def test_from_line_to_end(self):
        from otutil.tools._mem.slicing import _resolve_line_range

        lines = ["a", "b", "c", "d", "e"]
        assert _resolve_line_range("4:", lines, 5) == "d\ne"

    def test_range(self):
        from otutil.tools._mem.slicing import _resolve_line_range

        lines = ["a", "b", "c", "d", "e"]
        assert _resolve_line_range("2:4", lines, 5) == "b\nc\nd"

    def test_negative_start(self):
        from otutil.tools._mem.slicing import _resolve_line_range

        lines = ["a", "b", "c", "d", "e"]
        result = _resolve_line_range("-2:", lines, 5)
        assert result == "d\ne"

    def test_empty_spec(self):
        from otutil.tools._mem.slicing import _resolve_line_range

        lines = ["a", "b"]
        assert _resolve_line_range(":", lines, 2) is None


# ---------------------------------------------------------------------------
# _check_staleness helper tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestCheckStaleness:
    """Test _check_staleness helper."""

    def test_skipped_no_source(self):
        from otutil.tools._mem.content import _check_staleness

        assert _check_staleness({}) == "skipped"
        assert _check_staleness({"source": "/tmp/f.md"}) == "skipped"
        assert _check_staleness({"source_mtime": "123"}) == "skipped"

    def test_missing_source(self, tmp_path):
        from otutil.tools._mem.content import _check_staleness

        meta = {"source": str(tmp_path / "gone.md"), "source_mtime": "123"}
        assert _check_staleness(meta) == "missing"

    def test_fresh_source(self, tmp_path):
        from otutil.tools._mem.content import _check_staleness

        f = tmp_path / "fresh.md"
        f.write_text("content")
        mtime = str(f.stat().st_mtime)
        meta = {"source": str(f), "source_mtime": mtime}
        assert _check_staleness(meta) == "fresh"

    def test_stale_source(self, tmp_path):
        from otutil.tools._mem.content import _check_staleness

        f = tmp_path / "stale.md"
        f.write_text("old content")
        old_mtime = str(f.stat().st_mtime - 100)
        meta = {"source": str(f), "source_mtime": old_mtime}
        assert _check_staleness(meta) == "stale"


# ---------------------------------------------------------------------------
# Helper: mock _use_connection context manager
# ---------------------------------------------------------------------------


@contextmanager
def _mock_use_conn(rows, *, conn=None):
    """Patch ``_use_connection`` so it yields *conn* (or a fresh MagicMock)
    whose first ``execute().fetchall()`` returns *rows*.

    Usage::

        with _mock_use_conn(rows) as ctx:
            result = stale()          # ctx is the MagicMock connection

        # Or, to inspect calls afterwards:
        conn = MagicMock()
        with _mock_use_conn(rows, conn=conn):
            result = refresh(dry_run=False)
        assert any("UPDATE" in str(c) for c in conn.execute.call_args_list)
    """
    ctx = conn or MagicMock()
    ctx.execute.return_value.rowcount = 1
    ctx.execute.return_value.fetchall.return_value = rows
    with (
        patch("otutil.tools._mem.formatting._use_connection") as mock_fmt,
        patch("otutil.tools._mem.refresh._use_connection") as mock_ref,
    ):
        for mock_conn in (mock_fmt, mock_ref):
            mock_conn.return_value.__enter__ = MagicMock(return_value=ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        yield ctx


# ---------------------------------------------------------------------------
# stale() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStale:
    """Test mem.stale() bulk staleness check."""

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_no_memories(self, _mock_config):
        from otutil.tools.mem import stale

        with _mock_use_conn([]):
            result = stale()
        assert "No memories found" in result

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_no_file_backed(self, _mock_config):
        from otutil.tools.mem import stale

        rows = [("topic/a", "{}"), ("topic/b", "{}")]
        with _mock_use_conn(rows):
            result = stale()
        assert "No file-backed memories found" in result

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_mixed_staleness(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import stale

        # Fresh file
        fresh_file = tmp_path / "fresh.md"
        fresh_file.write_text("fresh content")
        fresh_meta = json.dumps({"source": str(fresh_file), "source_mtime": str(fresh_file.stat().st_mtime)})

        # Stale file
        stale_file = tmp_path / "stale.md"
        stale_file.write_text("new content")
        stale_meta = json.dumps({"source": str(stale_file), "source_mtime": str(stale_file.stat().st_mtime - 100)})

        # Missing file
        missing_meta = json.dumps({"source": str(tmp_path / "gone.md"), "source_mtime": "100"})

        rows = [
            ("docs/fresh.md", fresh_meta),
            ("docs/stale.md", stale_meta),
            ("docs/gone.md", missing_meta),
        ]
        with _mock_use_conn(rows):
            result = stale(topic="docs/")

        assert "1 fresh" in result
        assert "1 stale" in result
        assert "1 missing" in result
        assert "docs/stale.md" in result
        assert "docs/gone.md" in result
        assert "source file deleted" in result


# ---------------------------------------------------------------------------
# list(format="tree") tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestListTreeFormat:
    """Test mem.list(format='tree') topic hierarchy view."""

    @patch("otutil.tools._mem.listing._get_connection")
    def test_empty(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []
        result = list(format="tree")
        assert "No memories found" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_flat_topics(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-a", "a", "note", "[]", 5, 0, datetime.now().isoformat(), 100, None),
            ("id-b", "b", "note", "[]", 5, 0, datetime.now().isoformat(), 200, None),
            ("id-c", "c", "note", "[]", 5, 0, datetime.now().isoformat(), 300, None),
        ]
        result = list(format="tree")

        assert "(all)  (mem_count=3)" in result
        assert "── a  (id=id-a" in result
        assert "── b  (id=id-b" in result
        assert "category=note" in result
        # Tree connectors present
        assert "├──" in result or "└──" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_nested_topics_with_counts(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/docs/arch/index.md", "context", "[]", 5, 0, datetime.now().isoformat(), 1534, None),
            ("id-2", "proj/docs/arch/core.md", "context", "[]", 5, 0, datetime.now().isoformat(), 2202, None),
            ("id-3", "proj/docs/code/testing.md", "context", "[]", 5, 0, datetime.now().isoformat(), 2761, None),
        ]
        result = list(format="tree", topic="proj/docs/")

        assert "proj/docs/  (mem_count=3)" in result
        assert "── arch/  (mem_count=2)" in result
        assert "── code/  (mem_count=1)" in result
        assert "── index.md  (id=id-1" in result
        assert "── core.md  (id=id-2" in result
        assert "── testing.md  (id=id-3" in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_depth_limit(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/docs/arch/index.md", "context", "[]", 5, 0, datetime.now().isoformat(), 1534, None),
            ("id-2", "proj/docs/arch/core.md", "context", "[]", 5, 0, datetime.now().isoformat(), 2202, None),
            ("id-3", "proj/docs/code/testing.md", "context", "[]", 5, 0, datetime.now().isoformat(), 2761, None),
        ]
        result = list(format="tree", topic="proj/docs/", depth=1)

        assert "── arch/  (mem_count=2)" in result
        assert "── code/  (mem_count=1)" in result
        # Should NOT show children at depth=1
        assert "index.md" not in result
        assert "testing.md" not in result

    @patch("otutil.tools._mem.listing._get_connection")
    def test_tree_leaf_with_tags(self, mock_conn):
        from otutil.tools.mem import list

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "tagged", "note", '["a", "b"]', 5, 0, datetime.now().isoformat(), 50, None),
        ]
        result = list(format="tree")

        assert "tags=a|b" in result


# ---------------------------------------------------------------------------
# refresh() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestRefresh:
    """Test mem.refresh() source file re-read."""

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_dry_run_reports_without_modifying(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import refresh

        stale_file = tmp_path / "stale.md"
        stale_file.write_text("new content here")
        meta = json.dumps({"source": str(stale_file), "source_mtime": str(stale_file.stat().st_mtime - 100)})

        rows = [("mem-1", "docs/stale.md", "old content", _content_hash("old content"), meta)]
        ctx = MagicMock()
        with _mock_use_conn(rows, conn=ctx):
            result = refresh(topic="docs/")

        assert "dry run" in result
        assert "1 stale" in result
        assert "would update" in result
        # DB should NOT have been written to (no INSERT/UPDATE calls beyond the SELECT)
        update_calls = [c for c in ctx.execute.call_args_list if "UPDATE" in str(c) or "INSERT" in str(c)]
        assert len(update_calls) == 0

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_apply_updates_content(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import refresh

        stale_file = tmp_path / "stale.md"
        stale_file.write_text("updated content")
        meta = json.dumps({"source": str(stale_file), "source_mtime": str(stale_file.stat().st_mtime - 100)})

        rows = [("mem-1", "docs/stale.md", "old content", _content_hash("old content"), meta)]

        conn_mock = MagicMock()
        with (
            _mock_use_conn(rows, conn=conn_mock),
            patch("otutil.tools._mem.refresh._embed_now", return_value=None),
        ):
            result = refresh(topic="docs/", dry_run=False)

        assert "apply" in result
        assert "1 stale" in result
        assert "updated" in result
        # Should have INSERT (history) and UPDATE (memory) calls
        all_sql = [str(c) for c in conn_mock.execute.call_args_list]
        assert any("INSERT" in s for s in all_sql)
        assert any("UPDATE" in s for s in all_sql)

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_missing_source_skipped(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import refresh

        meta = json.dumps({"source": str(tmp_path / "gone.md"), "source_mtime": "100"})
        rows = [("mem-1", "docs/gone.md", "content", _content_hash("content"), meta)]

        with _mock_use_conn(rows):
            result = refresh(topic="docs/", dry_run=False)

        assert "1 missing" in result
        assert "docs/gone.md" in result

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_fresh_untouched(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import refresh

        fresh_file = tmp_path / "fresh.md"
        fresh_file.write_text("content")
        meta = json.dumps({"source": str(fresh_file), "source_mtime": str(fresh_file.stat().st_mtime)})

        rows = [("mem-1", "docs/fresh.md", "content", _content_hash("content"), meta)]
        with _mock_use_conn(rows):
            result = refresh(topic="docs/")

        assert "1 fresh" in result
        assert "stale" not in result.lower() or "0 stale" in result.lower()

    @patch("otutil.tools._mem.content._get_config", return_value=Config())
    def test_toc_recomputed_on_refresh(self, _mock_config, tmp_path):
        import json

        from otutil.tools.mem import refresh

        stale_file = tmp_path / "stale.md"
        stale_file.write_text("# New Heading\n\nNew content\n")
        meta = json.dumps({
            "source": str(stale_file),
            "source_mtime": str(stale_file.stat().st_mtime - 100),
            "sections": "Old Heading:1-3",
            "section_count": "1",
        })

        rows = [("mem-1", "docs/stale.md", "# Old Heading\n\nOld content\n", _content_hash("# Old Heading\n\nOld content\n"), meta)]

        conn_mock = MagicMock()
        with (
            _mock_use_conn(rows, conn=conn_mock),
            patch("otutil.tools._mem.refresh._embed_now", return_value=None),
        ):
            result = refresh(topic="docs/", dry_run=False)

        assert "1 stale" in result
        # Verify the meta was updated with new sections by checking the UPDATE call
        update_calls = [c for c in conn_mock.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_calls) > 0
        # Embeddings disabled by default: params include CAS predecessor fields.
        update_args = update_calls[0]
        meta_arg = update_args[0][1][2]
        assert "New Heading" in meta_arg


# ---------------------------------------------------------------------------
# slice_batch() tests
# ---------------------------------------------------------------------------


def _make_read_row(
    *,
    id: str = "id-1",
    topic: str = "t/a",
    content: str = "# H1\n\nParagraph\n\n# H2\n\nMore text",
    category: str = "note",
    tags: str = "[]",
    relevance: int = 5,
    access_count: int = 0,
    created_at: str = "2025-01-01",
    updated_at: str = "2025-01-01",
    meta: str = '{"sections": "H1:1-3|H2:5-7", "section_count": "2"}',
) -> tuple:
    """Build a fake row matching _READ_COLUMNS order."""
    return (id, topic, content, category, tags, relevance, access_count, created_at, updated_at, meta)


@pytest.mark.unit
@pytest.mark.tools
class TestSliceBatch:
    """Test mem.slice_batch() batch section extraction."""

    def test_multiple_topics(self):
        from otutil.tools.mem import slice_batch

        row_a = _make_read_row(id="1", topic="docs/a.md", content="# Intro\n\nHello\n\n# Details\n\nWorld",
                               meta='{"sections": "Intro:1-3|Details:5-7", "section_count": "2"}')
        row_b = _make_read_row(id="2", topic="docs/b.md", content="# Setup\n\nStep 1\n\n# Run\n\nStep 2",
                               meta='{"sections": "Setup:1-3|Run:5-7", "section_count": "2"}')
        rows = [row_a, row_b]

        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchall.return_value = rows
            result = slice_batch(items=[
                {"topic": "docs/a.md", "select": "Intro"},
                {"topic": "docs/b.md", "select": "Run"},
            ])

        assert "Sliced 2 memories" in result
        assert "docs/a.md [Intro]" in result
        assert "docs/b.md [Run]" in result

    def test_mixed_selectors(self):
        from otutil.tools.mem import slice_batch

        row = _make_read_row(id="1", topic="docs/a.md", content="# H1\n\nLine2\n\n# H2\n\nLine6\nLine7")
        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchall.return_value = [row]
            result = slice_batch(items=[
                {"topic": "docs/a.md", "select": 1},
                {"topic": "docs/a.md", "select": "H2"},
                {"topic": "docs/a.md", "select": ":3"},
            ])

        assert "Sliced 3 memories" in result
        assert "[Section 1]" in result
        assert "[H2]" in result
        assert "[:3]" in result

    def test_missing_topic(self):
        from otutil.tools.mem import slice_batch

        row = _make_read_row(id="1", topic="docs/a.md")
        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchall.return_value = [row]
            result = slice_batch(items=[
                {"topic": "docs/a.md", "select": "H1"},
                {"topic": "docs/missing.md", "select": "Intro"},
            ])

        assert "docs/a.md" in result
        assert "No memory found" in result
        assert "docs/missing.md" in result

    def test_no_match_selector(self):
        from otutil.tools.mem import slice_batch

        row = _make_read_row(id="1", topic="docs/a.md")
        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchall.return_value = [row]
            result = slice_batch(items=[
                {"topic": "docs/a.md", "select": "NonExistentHeading"},
            ])

        assert "No matching content" in result

    def test_empty_items(self):
        from otutil.tools.mem import slice_batch

        result = slice_batch(items=[])
        assert "Error" in result
        assert "non-empty" in result

    def test_max_items_exceeded(self):
        from otutil.tools.mem import slice_batch

        items = [{"topic": f"t/{i}", "select": 1} for i in range(21)]
        result = slice_batch(items=items)
        assert "Error" in result
        assert "20" in result

    def test_invalid_item_missing_select(self):
        from otutil.tools.mem import slice_batch

        row = _make_read_row(id="1", topic="docs/a.md")
        with patch("otutil.tools._mem.slicing._use_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchall.return_value = [row]
            result = slice_batch(items=[
                {"topic": "docs/a.md"},
                {"topic": "docs/a.md", "select": "H1"},
            ])

        assert "'select' is required" in result
        assert "docs/a.md [H1]" in result


# ---------------------------------------------------------------------------
# FTS5 keyword index, vec0 KNN index, history/rollback (mem-search-and-history)
# ---------------------------------------------------------------------------

import hashlib as _hashlib
import sqlite3 as _sqlite3
import struct as _struct


def _real_mem_conn(dims: int = 4) -> _sqlite3.Connection:
    """Real in-memory connection with the full mem setup (FTS + vec + triggers)."""
    from otutil.tools._mem import db as mem_db

    conn = _sqlite3.connect(":memory:", check_same_thread=False)
    with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=dims)):
        mem_db._mem_setup(conn)
    conn.commit()
    return conn


def _insert_memory(
    conn: _sqlite3.Connection,
    memory_id: str,
    topic: str,
    content: str,
    *,
    category: str = "note",
    tags: str = "[]",
    embedding: bytes | None = None,
    meta: str = "{}",
) -> None:
    conn.execute(
        "INSERT INTO memories (id, topic, content, content_hash, category, tags, embedding, meta) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [memory_id, topic, content, _hashlib.sha256(content.encode()).hexdigest(),
         category, tags, embedding, meta],
    )
    conn.commit()


def _pack_vec(vec: list[float]) -> bytes:
    return _struct.pack(f"<{len(vec)}f", *vec)


@pytest.mark.unit
@pytest.mark.tools
class TestMemKeywordFTS:
    """BM25 keyword search over memories_fts (spec: BM25-ranked keyword search)."""

    def test_bm25_ranks_strong_match_above_weak(self):
        from otutil.tools._mem.search import _search_keyword

        conn = _real_mem_conn()
        _insert_memory(conn, "weak", "a/weak", "authentication mentioned once among many other words " + "filler " * 50)
        _insert_memory(conn, "strong", "a/strong", "authentication guide: authentication flows and authentication tokens")

        results = _search_keyword(conn, "authentication", None, None, None, 10)

        assert [r["id"] for r in results[:2]] == ["strong", "weak"]
        assert all(r["score"] != 1.0 for r in results)

    def test_operator_laden_query_does_not_error(self):
        from otutil.tools._mem.search import _search_keyword

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "some searchable content")

        results = _search_keyword(conn, 'what is "content:(-x)^*"?', None, None, None, 10)
        assert isinstance(results, list)

    def test_prefix_fallback_finds_partial_terms(self):
        from otutil.tools._mem.search import _search_keyword

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "authentication patterns for services")

        results = _search_keyword(conn, "authent", None, None, None, 10)
        assert [r["id"] for r in results] == ["m1"]

    def test_filters_apply(self):
        from otutil.tools._mem.search import _search_keyword

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "projects/a", "shared token content", category="rule", tags='["x"]')
        _insert_memory(conn, "m2", "notes/b", "shared token content two", category="note", tags='["y"]')

        by_topic = _search_keyword(conn, "shared token", "projects/", None, None, 10)
        assert [r["id"] for r in by_topic] == ["m1"]
        by_cat = _search_keyword(conn, "shared token", None, "note", None, 10)
        assert [r["id"] for r in by_cat] == ["m2"]
        by_tag = _search_keyword(conn, "shared token", None, None, ["x"], 10)
        assert [r["id"] for r in by_tag] == ["m1"]

    def test_like_fallback_when_fts_unavailable(self):
        import importlib

        mem_search = importlib.import_module("otutil.tools._mem.search")

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "fallback searchable content")

        with patch("otutil.tools._mem.search._check_fts_available", return_value=False), \
             patch.object(mem_search, "_like_fallback_warned", False), \
             patch("otutil.tools._mem.search.logger") as mock_logger:
            results = mem_search._search_keyword(conn, "fallback", None, None, None, 10)

        assert [r["id"] for r in results] == ["m1"]
        assert results[0]["score"] == 1.0
        mock_logger.warning.assert_called_once()

    def test_migration_rebuilds_fts_for_preexisting_rows(self):
        from otutil.tools._mem import db as mem_db

        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        # Simulate a pre-FTS database: memories table + rows, no memories_fts
        conn.execute(
            "CREATE TABLE memories (id TEXT PRIMARY KEY, topic TEXT NOT NULL, "
            "content TEXT NOT NULL, content_hash TEXT NOT NULL, category TEXT DEFAULT 'note', "
            "tags TEXT DEFAULT '[]', relevance INTEGER DEFAULT 5, access_count INTEGER DEFAULT 0, "
            "created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')), "
            "last_accessed TEXT DEFAULT (datetime('now')), embedding BLOB, meta TEXT DEFAULT '{}')"
        )
        conn.execute(
            "INSERT INTO memories (id, topic, content, content_hash) VALUES ('m1', 'a/one', 'legacy searchable row', 'h')"
        )
        conn.commit()

        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            mem_db._mem_setup(conn)

        count = conn.execute(
            "SELECT COUNT(*) FROM memories_fts WHERE memories_fts MATCH 'legacy'"
        ).fetchone()[0]
        assert count == 1


@pytest.mark.unit
@pytest.mark.tools
class TestMemVecIndex:
    """vec0 KNN index: sync, normalisation, parity, lifecycle, migration."""

    def _vec_norm(self, conn: _sqlite3.Connection, memory_id: str) -> float:
        blob = conn.execute(
            "SELECT embedding FROM memories_vec WHERE memory_id = ?", [memory_id]
        ).fetchone()[0]
        vec = _struct.unpack(f"<{len(blob) // 4}f", blob)
        return sum(x * x for x in vec) ** 0.5

    def test_sync_writes_normalised_rows(self):
        from otutil.tools._mem.db import _sync_vec_index

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "content", embedding=_pack_vec([3.0, 0.0, 4.0, 0.0]))
        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            _sync_vec_index(conn, "m1", [3.0, 0.0, 4.0, 0.0])
        conn.commit()

        assert abs(self._vec_norm(conn, "m1") - 1.0) < 1e-6

    def test_knn_matches_scan_scores(self):
        from otutil.tools._mem.search import _search_semantic_knn, _search_semantic_scan
        from otutil.tools._mem.db import _sync_vec_index

        conn = _real_mem_conn()
        vectors = {"m1": [1.0, 0.0, 0.0, 0.0], "m2": [0.6, 0.8, 0.0, 0.0], "m3": [0.0, 0.0, 1.0, 0.0]}
        for mid, vec in vectors.items():
            _insert_memory(conn, mid, f"t/{mid}", f"content {mid}", embedding=_pack_vec(vec))
            with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
                _sync_vec_index(conn, mid, vec)
        conn.commit()

        query_vec = [1.0, 0.0, 0.0, 0.0]
        with patch("otutil.tools._mem.search._generate_query_embedding", return_value=query_vec):
            knn = _search_semantic_knn(conn, "q", None, None, None, 3)
            scan = _search_semantic_scan(conn, "q", None, None, None, 3)

        assert [r["id"] for r in knn] == [r["id"] for r in scan]
        for k, sc in zip(knn, scan, strict=True):
            assert abs(k["score"] - sc["score"]) < 1e-3

    def test_filtered_knn_overfetches_and_respects_limit(self):
        from otutil.tools._mem.search import _search_semantic_knn
        from otutil.tools._mem.db import _sync_vec_index

        conn = _real_mem_conn()
        for i in range(6):
            vec = [1.0, float(i) * 0.1, 0.0, 0.0]
            topic = f"projects/p{i}" if i < 3 else f"notes/n{i}"
            _insert_memory(conn, f"m{i}", topic, f"content {i}", embedding=_pack_vec(vec))
            with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
                _sync_vec_index(conn, f"m{i}", vec)
        conn.commit()

        with patch("otutil.tools._mem.search._generate_query_embedding", return_value=[1.0, 0.0, 0.0, 0.0]):
            results = _search_semantic_knn(conn, "q", "projects/", None, None, 2)

        assert len(results) == 2
        assert all(r["topic"].startswith("projects/") for r in results)

    def test_delete_trigger_removes_vec_row(self):
        from otutil.tools._mem.db import _sync_vec_index

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "content", embedding=_pack_vec([1.0, 0.0, 0.0, 0.0]))
        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            _sync_vec_index(conn, "m1", [1.0, 0.0, 0.0, 0.0])
        conn.execute("DELETE FROM memories WHERE id = 'm1'")
        conn.commit()

        assert conn.execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0] == 0

    def test_update_replaces_vec_row_and_disabled_preserves(self):
        from otutil.tools._mem.db import _sync_vec_index
        from otutil.tools._mem.mutations import _apply_memory_update

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "content", embedding=_pack_vec([1.0, 0.0, 0.0, 0.0]))
        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            _sync_vec_index(conn, "m1", [1.0, 0.0, 0.0, 0.0])
            _sync_vec_index(conn, "m1", [0.0, 1.0, 0.0, 0.0])
        conn.commit()
        blob = conn.execute("SELECT embedding FROM memories_vec WHERE memory_id='m1'").fetchone()[0]
        assert _struct.unpack("<4f", blob)[1] == pytest.approx(1.0)

        # Embeddings-disabled update path preserves BLOB and vec row untouched
        with patch("otutil.tools._mem.mutations._get_config", return_value=Config(embeddings_enabled=False)):
            _apply_memory_update(
                conn, memory_id="m1", old_content="content", old_content_hash=_content_hash("content"), new_content="new content",
                meta={}, embedding=None,
            )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM memories_vec WHERE memory_id='m1'").fetchone()[0] == 1
        assert conn.execute("SELECT embedding FROM memories WHERE id='m1'").fetchone()[0] is not None

    def test_dim_mismatch_skips_vec_upsert(self):
        from otutil.tools._mem.db import _sync_vec_index

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "content")
        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            _sync_vec_index(conn, "m1", [1.0, 0.0])
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0] == 0

    def test_migration_backfills_and_skips_mismatched_dims(self):
        from otutil.tools._mem import db as mem_db

        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute(
            "CREATE TABLE memories (id TEXT PRIMARY KEY, topic TEXT NOT NULL, "
            "content TEXT NOT NULL, content_hash TEXT NOT NULL, category TEXT DEFAULT 'note', "
            "tags TEXT DEFAULT '[]', relevance INTEGER DEFAULT 5, access_count INTEGER DEFAULT 0, "
            "created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')), "
            "last_accessed TEXT DEFAULT (datetime('now')), embedding BLOB, meta TEXT DEFAULT '{}')"
        )
        conn.execute(
            "INSERT INTO memories (id, topic, content, content_hash, embedding) VALUES "
            "('good', 't/a', 'c', 'h1', ?)", [_pack_vec([1.0, 2.0, 2.0, 0.0])]
        )
        conn.execute(
            "INSERT INTO memories (id, topic, content, content_hash, embedding) VALUES "
            "('bad', 't/b', 'c', 'h2', ?)", [_pack_vec([1.0, 2.0])]
        )
        conn.commit()

        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            mem_db._mem_setup(conn)

        ids = [r[0] for r in conn.execute("SELECT memory_id FROM memories_vec").fetchall()]
        assert ids == ["good"]

    def test_dimension_change_recreates_vec_table(self):
        from otutil.tools._mem import db as mem_db

        conn = _real_mem_conn(dims=4)
        _insert_memory(conn, "m1", "a/one", "content", embedding=_pack_vec([1.0, 0.0, 0.0, 0.0]))
        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=4)):
            mem_db._sync_vec_index(conn, "m1", [1.0, 0.0, 0.0, 0.0])
        conn.commit()

        with patch("otutil.tools._mem.db._get_config", return_value=Config(dimensions=8)):
            mem_db._ensure_tables(conn)

        assert mem_db._vec_table_dims(conn) == 8
        # Old 4-dim BLOB is skipped by the dims guard during backfill
        assert conn.execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0] == 0

    def test_vec_fallback_uses_scan(self):
        import importlib

        mem_search = importlib.import_module("otutil.tools._mem.search")

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "content", embedding=_pack_vec([1.0, 0.0, 0.0, 0.0]))
        conn.commit()

        with patch("otutil.tools._mem.search._check_vec_available", return_value=False), \
             patch("otutil.tools._mem.search._generate_query_embedding", return_value=[1.0, 0.0, 0.0, 0.0]):
            results = mem_search._search_semantic(conn, "q", None, None, None, 5)

        assert [r["id"] for r in results] == ["m1"]
        assert results[0]["score"] == pytest.approx(1.0)


@contextmanager
def _history_env(conn: _sqlite3.Connection):
    """Patch history/mutations modules onto a real connection with embeddings off."""
    from contextlib import nullcontext

    with (
        patch("otutil.tools._mem.history._use_connection", side_effect=lambda: nullcontext(conn)),
        patch("otutil.tools._mem.history._embed_now", return_value=None),
        patch("otutil.tools._mem.history._enqueue_after_commit"),
        patch("otutil.tools._mem.mutations._use_connection", side_effect=lambda: nullcontext(conn)),
        patch("otutil.tools._mem.mutations._embed_now", return_value=None),
        patch("otutil.tools._mem.mutations._enqueue_after_commit"),
        patch("otutil.tools._mem.mutations._get_config", return_value=Config(embeddings_enabled=False)),
    ):
        yield


@pytest.mark.unit
@pytest.mark.tools
class TestMemHistory:
    """mem.history() listing (spec: version history)."""

    def test_lists_versions_newest_first(self):
        from otutil.tools._mem.history import history
        from otutil.tools._mem.mutations import update

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "version zero")
        with _history_env(conn):
            update(topic="a/one", content="version one")
            update(topic="a/one", content="version two")
            out = history(topic="a/one")

        assert "current: 11 chars" in out
        lines = out.splitlines()
        assert "v1 [" in lines[2] and "version one" in lines[2]
        assert "v2 [" in lines[3] and "version zero" in lines[3]

    def test_no_history_message(self):
        from otutil.tools._mem.history import history

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "never updated")
        with _history_env(conn):
            out = history(topic="a/one")
        assert "No history" in out

    def test_zero_and_multi_match_errors(self):
        from otutil.tools._mem.history import history

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "dup/topic", "one")
        _insert_memory(conn, "m2", "dup/topic", "two")
        with _history_env(conn):
            assert "No memory found" in history(topic="missing/topic")
            assert "Multiple memories" in history(topic="dup/topic")


@pytest.mark.unit
@pytest.mark.tools
class TestMemRollback:
    """mem.rollback() restore semantics (spec: rollback)."""

    def test_rollback_restores_and_is_undoable(self):
        from otutil.tools._mem.history import rollback
        from otutil.tools._mem.mutations import update

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "original")
        with _history_env(conn):
            update(topic="a/one", content="changed")
            out = rollback(topic="a/one")
            assert "Rolled back" in out
            assert conn.execute("SELECT content FROM memories WHERE id='m1'").fetchone()[0] == "original"
            # Rollback of the rollback returns the pre-rollback content
            rollback(topic="a/one")
            assert conn.execute("SELECT content FROM memories WHERE id='m1'").fetchone()[0] == "changed"

    def test_version_out_of_range_names_valid_range(self):
        from otutil.tools._mem.history import rollback
        from otutil.tools._mem.mutations import update

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "original")
        with _history_env(conn):
            update(topic="a/one", content="changed")
            out = rollback(topic="a/one", version=2)
        assert "out of range" in out
        assert "v1..v1" in out

    def test_history_id_prefix_selection_and_ambiguity(self):
        from otutil.tools._mem.history import rollback

        conn = _real_mem_conn()
        _insert_memory(conn, "m1", "a/one", "current")
        conn.execute(
            "INSERT INTO memory_history (id, memory_id, content, updated_at) VALUES "
            "('aa111111-0000-0000-0000-000000000000', 'm1', 'older', '2020-01-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO memory_history (id, memory_id, content, updated_at) VALUES "
            "('aa222222-0000-0000-0000-000000000000', 'm1', 'newer', '2021-01-01 00:00:00')"
        )
        conn.commit()

        with _history_env(conn):
            assert "ambiguous" in rollback(topic="a/one", history_id="aa")
            assert "No history entry matches" in rollback(topic="a/one", history_id="zz")
            out = rollback(topic="a/one", history_id="aa111")
        assert "Rolled back" in out
        assert conn.execute("SELECT content FROM memories WHERE id='m1'").fetchone()[0] == "older"

    def test_rollback_recomputes_toc_sections(self):
        from otutil.tools._mem.history import rollback

        conn = _real_mem_conn()
        _insert_memory(
            conn, "m1", "a/one", "# New\n\ncurrent body",
            meta='{"sections": "New:1", "section_count": "1"}',
        )
        conn.execute(
            "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
            ["bb111111-0000-0000-0000-000000000000", "m1", "# Old A\n\nx\n\n# Old B\n\ny"],
        )
        conn.commit()

        with _history_env(conn):
            rollback(topic="a/one")

        meta = _deserialize_meta(conn.execute("SELECT meta FROM memories WHERE id='m1'").fetchone()[0])
        assert meta["section_count"] == "2"


@pytest.mark.unit
@pytest.mark.tools
class TestMemStatsIndexes:
    """stats() search-index status lines (spec: observability)."""

    def _run_stats(self, fts: bool, vec: bool) -> str:
        from otutil.tools._mem.lifecycle import stats

        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [
            (10,), (5000, 500, 2000), (3,), (2,), (7,),
        ]
        conn.execute.return_value.fetchall.side_effect = [
            [("note", 5)], [("projects", 7)],
        ]
        with (
            patch("otutil.tools._mem.lifecycle._get_connection", return_value=conn),
            patch("otutil.tools._mem.lifecycle._check_fts_available", return_value=fts),
            patch("otutil.tools._mem.lifecycle._check_vec_available", return_value=vec),
        ):
            return stats()

    def test_available_modes(self):
        out = self._run_stats(fts=True, vec=True)
        assert "Keyword: fts5" in out
        assert "Vector: sqlite-vec (7 rows)" in out

    def test_fallback_modes(self):
        out = self._run_stats(fts=False, vec=False)
        assert "Keyword: like-fallback" in out
        assert "Vector: scan-fallback" in out
