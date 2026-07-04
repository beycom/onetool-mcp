"""Integration tests for persistent memory tool pack.

Uses real SQLite database with mocked config and embeddings.
Tests the happy-path CRUD lifecycle and basic search.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def mem_db(tmp_path):
    """Provide a temporary memory database with mocked config and embeddings.

    Patches config to use tmp_path database and mocks embedding generation
    to return deterministic vectors.
    """
    import otutil.tools._mem as mem_module

    db_path = tmp_path / "test_mem.sqlite"

    mem_module._close_connection()

    mock_config = mem_module.Config(
        db_path=str(db_path),
        redaction_enabled=True,
        tags_whitelist=[],
        allowed_file_dirs=[str(tmp_path)],
    )

    call_count = [0]

    def mock_embedding(text: str) -> list[float]:
        call_count[0] += 1
        base = [0.0] * 1536
        base[0] = float(call_count[0]) / 100.0
        base[1] = float(hash(text) % 1000) / 1000.0
        return base

    import importlib

    import otutil.tools._mem.config as mem_config
    import otutil.tools._mem.content as mem_content
    import otutil.tools._mem.db as mem_db_mod
    import otutil.tools._mem.embedding as mem_embedding
    import otutil.tools._mem.lifecycle as mem_lifecycle

    mem_search = importlib.import_module("otutil.tools._mem.search")

    with (
        patch.object(mem_config, "_get_config", return_value=mock_config),
        patch.object(mem_db_mod, "_get_config", return_value=mock_config),
        patch.object(mem_embedding, "_get_config", return_value=mock_config),
        patch.object(mem_content, "_get_config", return_value=mock_config),
        patch.object(mem_lifecycle, "_get_config", return_value=mock_config),
        patch.object(mem_search, "_get_config", return_value=mock_config),
        patch.object(mem_embedding, "_generate_embedding", side_effect=mock_embedding),
    ):
        yield mem_module

    mem_module._close_connection()


@pytest.mark.integration
@pytest.mark.tools
class TestMemCRUDLifecycle:
    """Happy-path write/read/delete with real SQLite."""

    def test_write_and_read(self, mem_db):
        """Written content is retrievable."""
        mem_db.write(topic="test/lifecycle", content="hello world", category="note")
        result = mem_db.read(topic="test/lifecycle")
        assert "hello world" in result

    def test_write_dedup(self, mem_db):
        """Duplicate content to the same topic is rejected."""
        mem_db.write(topic="test/dedup", content="same content")
        result = mem_db.write(topic="test/dedup", content="same content")
        assert "Duplicate" in result

    def test_delete_by_id(self, mem_db):
        """delete() by ID removes the memory."""
        result = mem_db.write(topic="test/delete", content="to be deleted")
        memory_id = result.split("Stored memory ")[1].split(" ")[0]

        mem_db.delete(id=memory_id)

        result = mem_db.read(topic="test/delete")
        assert "No memory found" in result


@pytest.mark.integration
@pytest.mark.tools
class TestMemSearch:
    """Pattern search with real SQLite."""

    def test_pattern_search(self, mem_db):
        """search() finds memories matching a pattern."""
        mem_db.write(topic="search/py", content="Python is great for scripting")
        mem_db.write(topic="search/js", content="JavaScript runs in browsers")

        result = mem_db.search(query="Python", mode="keyword")

        assert "search/py" in result
        assert "search/js" not in result
