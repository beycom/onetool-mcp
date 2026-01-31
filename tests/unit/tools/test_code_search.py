"""Tests for semantic code search tools.

Tests path helpers and main functions with DuckDB mocks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if dependencies are not available
pytest.importorskip("duckdb")

from ot_tools.code_search import (
    _build_search_sql,
    _clear_connection_cache,
    _format_result,
    _generate_embeddings_batch,
    _get_db_path,
    _row_to_result,
    _validate_and_connect,
    autodoc,
    research,
    search,
    search_batch,
    status,
)

# -----------------------------------------------------------------------------
# Pure Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetDbPath:
    """Test _get_db_path path resolution function."""

    def test_uses_effective_cwd_by_default(self):
        with patch("ot.paths.get_effective_cwd", return_value=Path("/project")):
            db_path, project_root = _get_db_path(None)

        assert project_root == Path("/project")
        assert db_path == Path("/project/.chunkhound/chunks.db")

    def test_resolves_explicit_path(self):
        # Explicit path doesn't need mocking - it uses the provided path
        db_path, project_root = _get_db_path("/explicit/path")

        assert project_root == Path("/explicit/path")
        assert db_path == Path("/explicit/path/.chunkhound/chunks.db")

    def test_expands_tilde(self):
        _db_path, project_root = _get_db_path("~/myproject")

        # Should expand ~ to home directory
        assert "~" not in str(project_root)
        assert project_root.is_absolute()


@pytest.mark.unit
@pytest.mark.tools
class TestBuildSearchSql:
    """Test _build_search_sql helper function."""

    def test_builds_basic_sql(self):
        sql, params = _build_search_sql(
            embeddings_table="embeddings_1536",
            dimensions=1536,
            provider="openai",
            model="text-embedding-3-small",
        )

        assert "embeddings_1536" in sql
        assert "1536" in sql
        assert "provider" in sql.lower()
        assert params == ["openai", "text-embedding-3-small"]

    def test_adds_language_filter(self):
        sql, params = _build_search_sql(
            embeddings_table="embeddings_1536",
            dimensions=1536,
            provider="openai",
            model="text-embedding-3-small",
            language="python",
        )

        assert "language" in sql.lower()
        assert "python" in params

    def test_adds_chunk_type_filter(self):
        sql, params = _build_search_sql(
            embeddings_table="embeddings_1536",
            dimensions=1536,
            provider="openai",
            model="text-embedding-3-small",
            chunk_type="function",
        )

        assert "chunk_type" in sql.lower()
        assert "function" in params

    def test_adds_exclude_patterns(self):
        sql, params = _build_search_sql(
            embeddings_table="embeddings_1536",
            dimensions=1536,
            provider="openai",
            model="text-embedding-3-small",
            exclude="test|mock",
        )

        assert "NOT LIKE" in sql
        assert "%test%" in params
        assert "%mock%" in params


@pytest.mark.unit
@pytest.mark.tools
class TestRowToResult:
    """Test _row_to_result helper function."""

    def test_converts_row_to_dict(self):
        row = (1, "func_name", "code content", "function", 10, 20, "path/file.py", "python", 0.95)
        result = _row_to_result(row)

        assert result["chunk_id"] == 1
        assert result["symbol"] == "func_name"
        assert result["content"] == "code content"
        assert result["chunk_type"] == "function"
        assert result["start_line"] == 10
        assert result["end_line"] == 20
        assert result["file_path"] == "path/file.py"
        assert result["language"] == "python"
        assert result["similarity"] == 0.95
        assert "matched_query" not in result

    def test_includes_matched_query(self):
        row = (1, "func", "code", "function", 10, 20, "file.py", "python", 0.9)
        result = _row_to_result(row, matched_query="test query")

        assert result["matched_query"] == "test query"


@pytest.mark.unit
@pytest.mark.tools
class TestValidateAndConnect:
    """Test _validate_and_connect helper function."""

    @patch("ot_tools.code_search._get_cached_connection")
    def test_raises_when_db_not_exists(self, mock_cached_conn):
        from ot_tools.code_search import Config

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with pytest.raises(ValueError, match="not indexed"):
            _validate_and_connect(mock_path, Path("/project"), Config())

    @patch("ot_tools.code_search._get_cached_connection")
    def test_raises_when_chunks_table_missing(self, mock_cached_conn):
        from ot_tools.code_search import Config

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_conn = MagicMock()
        mock_cached_conn.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [("files",)]

        with pytest.raises(ValueError, match="chunks"):
            _validate_and_connect(mock_path, Path("/project"), Config())

    @patch("ot_tools.code_search._get_cached_connection")
    def test_raises_when_embeddings_table_missing(self, mock_cached_conn):
        from ot_tools.code_search import Config

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_conn = MagicMock()
        mock_cached_conn.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [("chunks",), ("files",)]

        with pytest.raises(ValueError, match="embeddings"):
            _validate_and_connect(mock_path, Path("/project"), Config())

    @patch("ot_tools.code_search._get_cached_connection")
    def test_returns_connection_and_table_name(self, mock_cached_conn):
        from ot_tools.code_search import Config

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_conn = MagicMock()
        mock_cached_conn.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [
            ("chunks",), ("files",), ("embeddings_1536",)
        ]

        conn, table = _validate_and_connect(mock_path, Path("/project"), Config())

        assert conn == mock_conn
        assert table == "embeddings_1536"


@pytest.mark.unit
@pytest.mark.tools
class TestConnectionCache:
    """Test connection caching functions."""

    def test_clear_connection_cache(self):
        # Just verify it doesn't raise
        _clear_connection_cache()

    @patch("ot_tools.code_search._import_duckdb")
    def test_vss_extension_error_message(self, mock_import):
        """Test that VSS extension errors provide helpful message."""
        from ot_tools.code_search import _get_cached_connection

        # Clear cache to ensure fresh connection attempt
        _clear_connection_cache()

        mock_duckdb = MagicMock()
        mock_import.return_value = mock_duckdb

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("Extension 'vss' not found")

        with pytest.raises(RuntimeError) as exc_info:
            _get_cached_connection("/fake/path.db")

        assert "VSS extension not available" in str(exc_info.value)
        assert "pip install duckdb" in str(exc_info.value)
        mock_conn.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
class TestFormatResult:
    """Test _format_result formatting function."""

    def test_formats_basic_result(self):
        result = {
            "file_path": "src/main.py",
            "symbol": "authenticate",
            "chunk_type": "function",
            "language": "python",
            "start_line": 10,
            "end_line": 25,
            "similarity": 0.95123,
            "content": "def authenticate(user, password):\n    pass",
        }

        formatted = _format_result(result)

        assert formatted["file"] == "src/main.py"
        assert formatted["name"] == "authenticate"
        assert formatted["type"] == "function"
        assert formatted["language"] == "python"
        assert formatted["lines"] == "10-25"
        assert formatted["score"] == 0.9512  # Rounded to 4 decimal places

    def test_truncates_long_content(self):
        result = {
            "file_path": "test.py",
            "symbol": "long_function",
            "chunk_type": "function",
            "language": "python",
            "start_line": 1,
            "end_line": 100,
            "similarity": 0.8,
            "content": "x" * 1000,  # Long content
        }

        formatted = _format_result(result)

        assert len(formatted["content"]) <= 500

    def test_handles_missing_fields(self):
        result = {
            "content": "some code",
        }

        formatted = _format_result(result)

        assert formatted["file"] == "unknown"
        assert formatted["name"] == ""
        assert formatted["type"] == ""

    @patch("ot_tools.code_search.get_tool_config")
    def test_uses_configurable_content_limit(self, mock_config):
        """Test that content truncation uses config values."""
        from ot_tools.code_search import Config

        # Set custom content limit (must respect validation: ge=100, le=10000)
        mock_config.return_value = Config(content_limit=200, content_limit_expanded=600)

        result = {
            "file_path": "test.py",
            "symbol": "func",
            "chunk_type": "function",
            "language": "python",
            "start_line": 1,
            "end_line": 10,
            "similarity": 0.9,
            "content": "x" * 1000,
        }

        # Without expand - should use content_limit (200)
        formatted = _format_result(result)
        assert len(formatted["content"]) == 200

    @patch("ot_tools.code_search.get_tool_config")
    def test_uses_configurable_content_limit_expanded(self, mock_config, tmp_path):
        """Test that expanded content uses content_limit_expanded config."""
        from ot_tools.code_search import Config

        # Must respect validation: content_limit_expanded ge=500, le=20000
        mock_config.return_value = Config(content_limit=200, content_limit_expanded=600)

        # Create a test file with lots of lines
        test_file = tmp_path / "test.py"
        test_file.write_text("\n".join(["x" * 100] * 50))  # 50 lines of 100 chars

        result = {
            "file_path": "test.py",
            "symbol": "func",
            "chunk_type": "function",
            "language": "python",
            "start_line": 20,
            "end_line": 30,
            "similarity": 0.9,
            "content": "x" * 1000,
        }

        # With expand - should use content_limit_expanded (600)
        formatted = _format_result(result, project_root=tmp_path, expand=5)
        assert len(formatted["content"]) == 600


# -----------------------------------------------------------------------------
# Search Tests with DuckDB Mocks
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked DuckDB."""

    @patch("ot_tools.code_search._validate_and_connect")
    def test_returns_error_when_not_indexed(self, mock_validate):
        mock_validate.side_effect = ValueError(
            "Project not indexed. Run: chunkhound index /project\n"
            "Expected database at: /project/.chunkhound/chunks.db"
        )

        result = search(query="authentication")

        assert "Error" in result
        assert "not indexed" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_successful_search(self, mock_config, mock_validate, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")

        # Mock search results
        mock_conn.execute.return_value.fetchall.return_value = [
            (
                1,  # chunk_id
                "authenticate",  # symbol
                "def authenticate(): pass",  # content
                "function",  # chunk_type
                10,  # start_line
                25,  # end_line
                "src/auth.py",  # file_path
                "python",  # language
                0.95,  # similarity
            )
        ]

        result = search(query="authentication logic")

        assert "authenticate" in result
        assert "src/auth.py" in result

    @patch("ot_tools.code_search._validate_and_connect")
    def test_returns_error_missing_chunks_table(self, mock_validate):
        mock_validate.side_effect = ValueError(
            "Database missing 'chunks' table. Re-index with: chunkhound index /project"
        )

        result = search(query="test")

        assert "Error" in result
        assert "chunks" in result

    @patch("ot_tools.code_search._validate_and_connect")
    def test_returns_error_missing_embeddings_table(self, mock_validate):
        mock_validate.side_effect = ValueError(
            "Database missing 'embeddings_1536' table. Re-index with: chunkhound index /project"
        )

        result = search(query="test")

        assert "Error" in result
        assert "embeddings" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_no_results_message(self, mock_config, mock_validate, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")

        # Empty search results
        mock_conn.execute.return_value.fetchall.return_value = []

        result = search(query="nonexistent concept")

        assert "No results found" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_language_filter(self, mock_config, mock_validate, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")
        mock_conn.execute.return_value.fetchall.return_value = []

        search(query="test", language="python")

        # Check that the SQL included language filter
        call_args = mock_conn.execute.call_args_list
        sql = call_args[0][0][0]
        assert "language" in sql.lower()


# -----------------------------------------------------------------------------
# Status Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStatus:
    """Test status function."""

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_not_indexed_message(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        mock_db_path.return_value = (mock_path, Path("/project"))

        result = status()

        assert "not indexed" in result
        assert "chunkhound index" in result

    @patch("ot_tools.code_search._get_cached_connection")
    @patch("ot_tools.code_search._get_db_path")
    def test_returns_statistics(self, mock_db_path, mock_cached_conn):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_conn = MagicMock()
        mock_cached_conn.return_value = mock_conn

        # Mock different queries
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("files",), ("embeddings_1536",)],  # SHOW TABLES
        ]
        mock_conn.execute.return_value.fetchone.side_effect = [
            (100,),  # chunk count
            (25,),  # file count
            (100,),  # embedding count
        ]

        result = status()

        assert "indexed" in result.lower()
        assert "/project" in result

    @patch("ot_tools.code_search._get_cached_connection")
    @patch("ot_tools.code_search._get_db_path")
    def test_handles_db_error(self, mock_db_path, mock_cached_conn):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_cached_conn.side_effect = Exception("Database locked")

        result = status()

        assert "Error" in result
        assert "Database locked" in result


# -----------------------------------------------------------------------------
# OpenAI Client Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetOpenAIClient:
    """Test _get_openai_client function."""

    @patch("ot_tools.code_search.get_secret")
    def test_raises_without_api_key(self, mock_secret):
        from ot_tools.code_search import _get_openai_client

        mock_secret.return_value = ""

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _get_openai_client()

    @patch("openai.OpenAI")
    @patch("ot_tools.code_search.get_secret")
    def test_creates_client_with_key(self, mock_secret, mock_openai):
        from ot_tools.code_search import _get_openai_client

        mock_secret.side_effect = lambda k: {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "",
        }.get(k, "")

        _get_openai_client()

        mock_openai.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
class TestGenerateEmbedding:
    """Test _generate_embedding function."""

    @patch("ot_tools.code_search._get_openai_client")
    def test_generates_embedding(self, mock_client):
        from ot_tools.code_search import _generate_embedding

        mock_openai = MagicMock()
        mock_client.return_value = mock_openai

        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_openai.embeddings.create.return_value = mock_response

        result = _generate_embedding("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_openai.embeddings.create.assert_called_once()


# -----------------------------------------------------------------------------
# Batch Embedding Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGenerateEmbeddingsBatch:
    """Test _generate_embeddings_batch function."""

    @patch("ot_tools.code_search._get_openai_client")
    def test_generates_batch_embeddings(self, mock_client):
        mock_openai = MagicMock()
        mock_client.return_value = mock_openai

        mock_response = MagicMock()
        mock_response.data = [MagicMock(), MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.data[1].embedding = [0.4, 0.5, 0.6]
        mock_openai.embeddings.create.return_value = mock_response

        result = _generate_embeddings_batch(["query1", "query2"])

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_openai.embeddings.create.assert_called_once()
        # Verify batch input was passed
        call_args = mock_openai.embeddings.create.call_args
        assert call_args[1]["input"] == ["query1", "query2"]


# -----------------------------------------------------------------------------
# Format Result with Expand Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFormatResultExpand:
    """Test _format_result with expand parameter."""

    def test_expand_returns_more_content(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "line1\nline2\nline3\ndef foo():\n    pass\nline6\nline7\nline8"
        )

        result = {
            "file_path": "test.py",
            "symbol": "foo",
            "chunk_type": "function",
            "language": "python",
            "start_line": 4,
            "end_line": 5,
            "similarity": 0.9,
            "content": "def foo():\n    pass",
        }

        # Without expand
        formatted = _format_result(result)
        assert formatted["lines"] == "4-5"

        # With expand
        formatted_exp = _format_result(result, project_root=tmp_path, expand=2)
        assert "line2" in formatted_exp["content"]
        assert "line7" in formatted_exp["content"]


# -----------------------------------------------------------------------------
# Search with New Parameters Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearchNewParams:
    """Test search function with new parameters."""

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_chunk_type_filter(self, mock_config, mock_validate, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")
        mock_conn.execute.return_value.fetchall.return_value = []

        search(query="test", chunk_type="function")

        # Check that SQL included chunk_type filter
        call_args = mock_conn.execute.call_args_list
        sql = call_args[0][0][0]
        assert "chunk_type" in sql.lower()

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_exclude_filter(self, mock_config, mock_validate, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")
        mock_conn.execute.return_value.fetchall.return_value = []

        search(query="test", exclude="test|mock")

        # Check that SQL included exclude patterns
        call_args = mock_conn.execute.call_args_list
        sql = call_args[0][0][0]
        assert "NOT LIKE" in sql


# -----------------------------------------------------------------------------
# Search Batch Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatch:
    """Test search_batch function."""

    @patch("ot_tools.code_search._validate_and_connect")
    def test_returns_error_when_not_indexed(self, mock_validate):
        mock_validate.side_effect = ValueError(
            "Project not indexed. Run: chunkhound index /project\n"
            "Expected database at: /project/.chunkhound/chunks.db"
        )

        result = search_batch(queries="auth|login")

        assert "Error" in result
        assert "not indexed" in result

    def test_returns_error_for_empty_queries(self):
        result = search_batch(queries="")
        assert "Error" in result
        assert "No valid queries" in result

    @patch("ot_tools.code_search._generate_embeddings_batch")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_successful_batch_search(self, mock_config, mock_validate, mock_embed_batch):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")

        # Mock two query results
        mock_conn.execute.return_value.fetchall.side_effect = [
            [  # First query results
                (1, "auth_func", "def auth(): pass", "function", 10, 15, "auth.py", "python", 0.95)
            ],
            [  # Second query results
                (2, "login_func", "def login(): pass", "function", 20, 25, "login.py", "python", 0.90)
            ],
        ]

        result = search_batch(queries="auth|login")

        assert "auth_func" in result
        assert "login_func" in result
        assert "2 queries" in result

    @patch("ot_tools.code_search._generate_embeddings_batch")
    @patch("ot_tools.code_search._validate_and_connect")
    @patch("ot_tools.code_search.get_tool_config")
    def test_deduplicates_results(self, mock_config, mock_validate, mock_embed_batch):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)
        mock_embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        mock_conn = MagicMock()
        mock_validate.return_value = (mock_conn, "embeddings_1536")

        # Both queries return the same file:lines - should keep higher score
        mock_conn.execute.return_value.fetchall.side_effect = [
            [(1, "auth", "code", "function", 10, 15, "auth.py", "python", 0.85)],
            [(1, "auth", "code", "function", 10, 15, "auth.py", "python", 0.95)],
        ]

        result = search_batch(queries="auth|login")

        # Should only have 1 result (deduplicated)
        assert "Found 1 results" in result
        assert "0.95" in result  # Higher score kept


# -----------------------------------------------------------------------------
# Research and Autodoc Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestResearch:
    """Test research function."""

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_not_indexed(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_db_path.return_value = (mock_path, Path("/project"))

        result = research(query="how does auth work")

        assert "Error" in result
        assert "not indexed" in result

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_chunkhound_missing(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        # chunkhound not installed, will raise ImportError
        result = research(query="how does auth work")

        assert "Error" in result
        assert "chunkhound" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
class TestAutodoc:
    """Test autodoc function."""

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_not_indexed(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_db_path.return_value = (mock_path, Path("/project"))

        result = autodoc(scope="src/")

        assert "Error" in result
        assert "not indexed" in result

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_chunkhound_missing(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        result = autodoc(scope="src/")

        assert "Error" in result
        assert "chunkhound" in result.lower()
