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
    _generate_embeddings_batch,
    _get_db_path,
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
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        db_path, project_root = _get_db_path(None)

        assert project_root == Path("/project")
        assert db_path == Path("/project/.chunkhound/db/chunks.db")
        config_module._current_config.clear()

    def test_resolves_explicit_path(self):
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/somewhere/else"})

        db_path, project_root = _get_db_path("/explicit/path")

        assert project_root == Path("/explicit/path")
        assert db_path == Path("/explicit/path/.chunkhound/db/chunks.db")
        config_module._current_config.clear()

    def test_expands_tilde(self):
        import ot_sdk.config as config_module

        config_module._current_config.clear()
        config_module._current_config.update({"_project_path": "/project"})

        _db_path, project_root = _get_db_path("~/myproject")

        # Should expand ~ to home directory
        assert "~" not in str(project_root)
        assert project_root.is_absolute()
        config_module._current_config.clear()


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
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_successful_search(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        # _import_duckdb returns a module, so mock_duckdb.return_value is the module
        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

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

    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_returns_error_missing_chunks_table(
        self, mock_config, mock_db_path, mock_duckdb
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        # No chunks table
        mock_conn.execute.return_value.fetchall.return_value = [("files",)]

        result = search(query="test")

        assert "Error" in result
        assert "chunks" in result

    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_returns_error_missing_embeddings_table(
        self, mock_config, mock_db_path, mock_duckdb
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        # Has chunks but no embeddings
        mock_conn.execute.return_value.fetchall.return_value = [("chunks",), ("files",)]

        result = search(query="test")

        assert "Error" in result
        assert "embeddings" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_no_results_message(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],  # SHOW TABLES
            [],  # Empty search results
        ]

        result = search(query="nonexistent concept")

        assert "No results found" in result

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_language_filter(self, mock_config, mock_db_path, mock_duckdb, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

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

    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    def test_returns_statistics(self, mock_db_path, mock_duckdb):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

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

    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    def test_handles_db_error(self, mock_db_path, mock_duckdb):
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_module.connect.side_effect = Exception("Database locked")

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
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_chunk_type_filter(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],
            [],
        ]

        search(query="test", chunk_type="function")

        # Check that SQL included chunk_type filter
        call_args = mock_conn.execute.call_args_list
        sql = call_args[2][0][0]
        assert "chunk_type" in sql.lower()

    @patch("ot_tools.code_search._generate_embedding")
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_exclude_filter(self, mock_config, mock_db_path, mock_duckdb, mock_embed):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed.return_value = [0.1] * 1536

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],
            [],
        ]

        search(query="test", exclude="test|mock")

        # Check that SQL included exclude patterns
        call_args = mock_conn.execute.call_args_list
        sql = call_args[2][0][0]
        assert "NOT LIKE" in sql


# -----------------------------------------------------------------------------
# Search Batch Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatch:
    """Test search_batch function."""

    @patch("ot_tools.code_search._get_db_path")
    def test_returns_error_when_not_indexed(self, mock_db_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_db_path.return_value = (mock_path, Path("/project"))

        result = search_batch(queries="auth|login")

        assert "Error" in result
        assert "not indexed" in result

    def test_returns_error_for_empty_queries(self):
        result = search_batch(queries="")
        assert "Error" in result
        assert "No valid queries" in result

    @patch("ot_tools.code_search._generate_embeddings_batch")
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_successful_batch_search(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed_batch
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        # Mock table check and two query results
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],  # SHOW TABLES
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
    @patch("ot_tools.code_search._import_duckdb")
    @patch("ot_tools.code_search._get_db_path")
    @patch("ot_tools.code_search.get_tool_config")
    def test_deduplicates_results(
        self, mock_config, mock_db_path, mock_duckdb, mock_embed_batch
    ):
        from ot_tools.code_search import Config

        mock_config.return_value = Config(limit=10)

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = (mock_path, Path("/project"))

        mock_embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        mock_module = MagicMock()
        mock_duckdb.return_value = mock_module
        mock_conn = MagicMock()
        mock_module.connect.return_value = mock_conn

        # Both queries return the same file:lines - should keep higher score
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("chunks",), ("embeddings_1536",), ("files",)],
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
