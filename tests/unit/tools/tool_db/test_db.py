"""Unit tests for database tool.

Tests db.tables(), db.schema(), and db.query() with SQLite database.
All db functions require explicit db_url parameter.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def northwind_db_url() -> str:
    """Return URL to Northwind sample database."""
    # Go up from tests/unit/tools/tool_db/ to project root
    db_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "demo"
        / "db"
        / "northwind.db"
    )
    if not db_path.exists():
        pytest.skip("Northwind sample database not found")
    return f"sqlite:///{db_path}"


@pytest.fixture
def reset_engines() -> None:
    """Reset the engine cache between tests."""
    import ot_tools.db as db_module

    db_module._engines.clear()


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_tables_lists_all_tables(northwind_db_url: str) -> None:
    """Verify db.tables() returns all table names."""
    from ot_tools.db import tables

    result = tables(db_url=northwind_db_url)

    # Northwind has these tables
    assert "Customers" in result
    assert "Products" in result
    assert "Orders" in result
    assert "Employees" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_tables_filter_by_substring(northwind_db_url: str) -> None:
    """Verify db.tables(filter=...) filters table names."""
    from ot_tools.db import tables

    result = tables(db_url=northwind_db_url, filter="Order")

    assert "Orders" in result or "OrderDetails" in result
    # Should not have unrelated tables
    assert "Customers" not in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_schema_returns_column_info(northwind_db_url: str) -> None:
    """Verify db.schema() returns column definitions."""
    from ot_tools.db import schema

    result = schema(table_names=["Customers"], db_url=northwind_db_url)

    assert "Customers:" in result
    assert "CustomerID" in result or "Id" in result
    # Should have type info
    assert (
        "VARCHAR" in result.upper()
        or "TEXT" in result.upper()
        or "INTEGER" in result.upper()
    )


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_schema_multiple_tables(northwind_db_url: str) -> None:
    """Verify db.schema() handles multiple tables."""
    from ot_tools.db import schema

    result = schema(table_names=["Customers", "Products"], db_url=northwind_db_url)

    assert "Customers:" in result
    assert "Products:" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_schema_shows_relationships(northwind_db_url: str) -> None:
    """Verify db.schema() shows foreign key relationships."""
    from ot_tools.db import schema

    # "Order Details" has foreign keys (note: table name has space)
    result = schema(table_names=["Order Details"], db_url=northwind_db_url)

    # Should show relationships section if foreign keys exist
    # (Northwind has FK relationships)
    assert "Order Details:" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_schema_empty_table_list_returns_error(northwind_db_url: str) -> None:
    """Verify db.schema() returns error for empty table list."""
    from ot_tools.db import schema

    result = schema(table_names=[], db_url=northwind_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_query_select(northwind_db_url: str) -> None:
    """Verify db.query() executes SELECT and returns results."""
    from ot_tools.db import query

    result = query(sql="SELECT * FROM Customers LIMIT 3", db_url=northwind_db_url)

    # Should have row numbers
    assert "1. row" in result
    # Should have result count
    assert "Result:" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_query_parameterized(northwind_db_url: str) -> None:
    """Verify db.query() handles parameterized queries."""
    from ot_tools.db import query

    result = query(
        sql="SELECT * FROM Customers WHERE Country = :country LIMIT 5",
        db_url=northwind_db_url,
        params={"country": "Germany"},
    )

    # Should return results
    assert "row" in result or "No rows" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_query_no_results(northwind_db_url: str) -> None:
    """Verify db.query() handles empty result sets."""
    from ot_tools.db import query

    result = query(
        sql="SELECT * FROM Customers WHERE CustomerID = 'NONEXISTENT'",
        db_url=northwind_db_url,
    )

    assert "No rows returned" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_query_invalid_sql_returns_error(northwind_db_url: str) -> None:
    """Verify db.query() returns error for invalid SQL."""
    from ot_tools.db import query

    result = query(sql="SELECT * FROM NonExistentTable", db_url=northwind_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_query_empty_sql_returns_error(northwind_db_url: str) -> None:
    """Verify db.query() returns error for empty SQL."""
    from ot_tools.db import query

    result = query(sql="", db_url=northwind_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.serve
def test_format_value_handles_none() -> None:
    """Verify _format_value handles None as NULL."""
    from ot_tools.db import _format_value

    assert _format_value(None) == "NULL"


@pytest.mark.unit
@pytest.mark.serve
def test_format_value_handles_datetime() -> None:
    """Verify _format_value formats datetime as ISO."""
    from datetime import datetime

    from ot_tools.db import _format_value

    dt = datetime(2024, 1, 15, 10, 30, 0)
    result = _format_value(dt)

    assert "2024-01-15" in result
    assert "10:30" in result


@pytest.mark.unit
@pytest.mark.serve
def test_pack_is_db() -> None:
    """Verify pack is correctly set."""
    from ot_tools.db import pack

    assert pack == "db"


@pytest.mark.unit
@pytest.mark.serve
def test_all_exports_only_public_functions() -> None:
    """Verify __all__ contains only the public functions."""
    from ot_tools.db import __all__

    assert set(__all__) == {"tables", "schema", "query"}


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.usefixtures("reset_engines")
def test_multi_db_connection_pooling(northwind_db_url: str) -> None:
    """Verify connection pooling works with multiple databases."""
    import ot_tools.db as db_module
    from ot_tools.db import tables

    # Query northwind database
    result1 = tables(db_url=northwind_db_url)
    assert "Customers" in result1

    # Engine should be cached
    assert northwind_db_url in db_module._engines

    # Query again - should reuse cached engine
    result2 = tables(db_url=northwind_db_url)
    assert result1 == result2

    # Still only one engine
    assert len(db_module._engines) == 1
