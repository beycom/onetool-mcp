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
    _format_result,
    _get_db_path,
    search,
    status,
)


# -----------------------------------------------------------------------------
# Pure Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetDbPath:
    """Test _get_db_path path resolution function."""

    @patch("ot_tools.code_search.get_effective_cwd")
    def test_uses_effective_cwd_by_default(self, mock_cwd):
        mock_cwd.return_value = Path("/project")

        db_path, project_root = _get_db_path(None)

        assert project_root == Path("/project")
        assert db_path == Path("/project/.chunkhound/db/chunks.db")

    def test_resolves_explicit_path(self):
        db_path, project_root = _get_db_path("/explicit/path")

        assert project_root == Path("/explicit/path")
        assert db_path == Path("/explicit/path/.chunkhound/db/chunks.db")

    def test_expands_tilde(self):
        db_path, project_root = _get_db_path("~/myproject")

        # Should expand ~ to home directory
        assert "~" not in str(project_root)
        assert project_root.is_absolute()


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


# -----------------------------------------------------------------------------
# Search Tests with DuckDB Mocks
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked DuckDB."""

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_not_indexed(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        mock_db_path.return_value = (mock_path, Path("/project"))

        result = search(query="authentication")

        assert "Error" in result
        assert "not indexed" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_config")
    def test_successful_search(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed
    ):
        mock_config.return_value.tools.code_search.limit = 10

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        # Mock tables check
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],  # SHOW TABLES
            [  # Search results
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
            ],
        ]

        result = search(query="authentication logic")

        assert "authenticate" in result
        assert "src/auth.py" in result

    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_config")
    def test_returns_error_missing_chunks_table(
        self, mock_config, mock_db_path, mock_duckdb
    ):
        mock_config.return_value.tools.code_search.limit = 10

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        # No chunks table
        mock_conn.execute.return_value.fetchall.return_value = [("files",)]

        result = search(query="test")

        assert "Error" in result
        assert "chunks" in result

    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_config")
    def test_returns_error_missing_embeddings_table(
        self, mock_config, mock_db_path, mock_duckdb
    ):
        mock_config.return_value.tools.code_search.limit = 10

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        # Has chunks but no embeddings
        mock_conn.execute.return_value.fetchall.return_value = [("chunks",), ("files",)]

        result = search(query="test")

        assert "Error" in result
        assert "embeddings" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_config")
    def test_no_results_message(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed
    ):
        mock_config.return_value.tools.code_search.limit = 10

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],  # SHOW TABLES
            [],  # Empty search results
        ]

        result = search(query="nonexistent concept")

        assert "No results found" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_config")
    def test_language_filter(self, mock_config, mock_db_path, mock_duckdb, mock_embed):
        mock_config.return_value.tools.code_search.limit = 10

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],
            [],
        ]

        search(query="test", language="python")

        # Check that the SQL included language filter
        call_args = mock_conn.execute.call_args_list
        # Calls are: LOAD vss (0), SHOW TABLES (1), search query (2)
        sql = call_args[2][0][0]
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

    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    def test_returns_statistics(self, mock_db_path, mock_duckdb):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

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

    @patch("ot_tools.code_search.duckdb")
    @patch("ot_tools.code_search._get_db_path")
    def test_handles_db_error(self, mock_db_path, mock_duckdb):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_duckdb.connect.side_effect = Exception("Database locked")

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

    @patch("ot_tools.code_search.OpenAI")
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
