"""Unit tests for db tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestDbPack:
    """Test db pack structure."""

    def test_pack_name(self):
        from otdev.tools import db

        assert db.pack == "db"

    def test_has_all_exports(self):
        from otdev.tools import db

        # DB should export query, tables, schema and other functions
        assert hasattr(db, "__all__")
        expected = {"query", "tables", "schema", "sample"}
        assert expected.issubset(set(db.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import db

        for name in db.__all__:
            func = getattr(db, name)
            assert callable(func), f"{name} should be callable"
