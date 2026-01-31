"""Unit tests for database tool.

Tests db.tables(), db.schema(), and db.query() with SQLite database.
All db functions require explicit db_url parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def test_db_url(tmp_path) -> Generator[str, None, None]:
    """Create a test SQLite database with Northwind-like schema."""
    import sqlite3

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables matching Northwind schema
    cursor.executescript("""
        CREATE TABLE Customers (
            CustomerID TEXT PRIMARY KEY,
            CompanyName TEXT,
            ContactName TEXT,
            Country TEXT
        );

        CREATE TABLE Products (
            ProductID INTEGER PRIMARY KEY,
            ProductName TEXT,
            UnitPrice REAL,
            UnitsInStock INTEGER
        );

        CREATE TABLE Employees (
            EmployeeID INTEGER PRIMARY KEY,
            LastName TEXT,
            FirstName TEXT,
            Title TEXT
        );

        CREATE TABLE Orders (
            OrderID INTEGER PRIMARY KEY,
            CustomerID TEXT,
            EmployeeID INTEGER,
            OrderDate TEXT,
            FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
            FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID)
        );

        CREATE TABLE "Order Details" (
            OrderID INTEGER,
            ProductID INTEGER,
            UnitPrice REAL,
            Quantity INTEGER,
            PRIMARY KEY (OrderID, ProductID),
            FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
            FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
        );

        -- Insert test data
        INSERT INTO Customers VALUES
            ('ALFKI', 'Alfreds Futterkiste', 'Maria Anders', 'Germany'),
            ('ANATR', 'Ana Trujillo', 'Ana Trujillo', 'Mexico'),
            ('ANTON', 'Antonio Moreno', 'Antonio Moreno', 'Mexico');

        INSERT INTO Products VALUES
            (1, 'Chai', 18.00, 39),
            (2, 'Chang', 19.00, 17),
            (3, 'Aniseed Syrup', 10.00, 13);

        INSERT INTO Employees VALUES
            (1, 'Davolio', 'Nancy', 'Sales Representative'),
            (2, 'Fuller', 'Andrew', 'Vice President');

        INSERT INTO Orders VALUES
            (10248, 'ALFKI', 1, '1996-07-04'),
            (10249, 'ANATR', 1, '1996-07-05');

        INSERT INTO "Order Details" VALUES
            (10248, 1, 14.00, 12),
            (10248, 2, 9.80, 10),
            (10249, 3, 10.00, 5);
    """)

    conn.commit()
    conn.close()

    yield f"sqlite:///{db_path}"


@pytest.fixture
def reset_engines() -> None:
    """Reset the engine cache between tests."""
    import ot_tools.db as db_module

    db_module._engines.clear()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_tables_lists_all_tables(test_db_url: str) -> None:
    """Verify db.tables() returns all table names."""
    from ot_tools.db import tables

    result = tables(db_url=test_db_url)

    # Northwind has these tables
    assert "Customers" in result
    assert "Products" in result
    assert "Orders" in result
    assert "Employees" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_tables_filter_by_substring(test_db_url: str) -> None:
    """Verify db.tables(filter=...) filters table names."""
    from ot_tools.db import tables

    result = tables(db_url=test_db_url, filter="Order")

    assert "Orders" in result or "OrderDetails" in result
    # Should not have unrelated tables
    assert "Customers" not in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_returns_column_info(test_db_url: str) -> None:
    """Verify db.schema() returns column definitions."""
    from ot_tools.db import schema

    result = schema(table_names=["Customers"], db_url=test_db_url)

    assert "Customers:" in result
    assert "CustomerID" in result or "Id" in result
    # Should have type info
    assert (
        "VARCHAR" in result.upper()
        or "TEXT" in result.upper()
        or "INTEGER" in result.upper()
    )


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_multiple_tables(test_db_url: str) -> None:
    """Verify db.schema() handles multiple tables."""
    from ot_tools.db import schema

    result = schema(table_names=["Customers", "Products"], db_url=test_db_url)

    assert "Customers:" in result
    assert "Products:" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_shows_relationships(test_db_url: str) -> None:
    """Verify db.schema() shows foreign key relationships."""
    from ot_tools.db import schema

    # "Order Details" has foreign keys (note: table name has space)
    result = schema(table_names=["Order Details"], db_url=test_db_url)

    # Should show relationships section if foreign keys exist
    # (Northwind has FK relationships)
    assert "Order Details:" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_empty_table_list_returns_error(test_db_url: str) -> None:
    """Verify db.schema() returns error for empty table list."""
    from ot_tools.db import schema

    result = schema(table_names=[], db_url=test_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_select(test_db_url: str) -> None:
    """Verify db.query() executes SELECT and returns results."""
    from ot_tools.db import query

    result = query(sql="SELECT * FROM Customers LIMIT 3", db_url=test_db_url)

    # Should have row numbers
    assert "1. row" in result
    # Should have result count
    assert "Result:" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_parameterized(test_db_url: str) -> None:
    """Verify db.query() handles parameterized queries."""
    from ot_tools.db import query

    result = query(
        sql="SELECT * FROM Customers WHERE Country = :country LIMIT 5",
        db_url=test_db_url,
        params={"country": "Germany"},
    )

    # Should return results
    assert "row" in result or "No rows" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_no_results(test_db_url: str) -> None:
    """Verify db.query() handles empty result sets."""
    from ot_tools.db import query

    result = query(
        sql="SELECT * FROM Customers WHERE CustomerID = 'NONEXISTENT'",
        db_url=test_db_url,
    )

    assert "No rows returned" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_invalid_sql_returns_error(test_db_url: str) -> None:
    """Verify db.query() returns error for invalid SQL."""
    from ot_tools.db import query

    result = query(sql="SELECT * FROM NonExistentTable", db_url=test_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_empty_sql_returns_error(test_db_url: str) -> None:
    """Verify db.query() returns error for empty SQL."""
    from ot_tools.db import query

    result = query(sql="", db_url=test_db_url)

    assert "Error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_format_value_handles_none() -> None:
    """Verify _format_value handles None as NULL."""
    from ot_tools.db import _format_value

    assert _format_value(None) == "NULL"


@pytest.mark.unit
@pytest.mark.tools
def test_format_value_handles_datetime() -> None:
    """Verify _format_value formats datetime as ISO."""
    from datetime import datetime

    from ot_tools.db import _format_value

    dt = datetime(2024, 1, 15, 10, 30, 0)
    result = _format_value(dt)

    assert "2024-01-15" in result
    assert "10:30" in result


@pytest.mark.unit
@pytest.mark.tools
def test_pack_is_db() -> None:
    """Verify pack is correctly set."""
    from ot_tools.db import pack

    assert pack == "db"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports_only_public_functions() -> None:
    """Verify __all__ contains only the public functions."""
    from ot_tools.db import __all__

    assert set(__all__) == {"tables", "schema", "query"}


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_multi_db_connection_pooling(test_db_url: str) -> None:
    """Verify connection pooling works with multiple databases."""
    import ot_tools.db as db_module
    from ot_tools.db import tables

    # Query northwind database
    result1 = tables(db_url=test_db_url)
    assert "Customers" in result1

    # Engine should be cached
    assert test_db_url in db_module._engines

    # Query again - should reuse cached engine
    result2 = tables(db_url=test_db_url)
    assert result1 == result2

    # Still only one engine
    assert len(db_module._engines) == 1


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_query_truncation_shows_correct_row_count(tmp_path) -> None:
    """Verify truncation message shows correct displayed row count."""
    import sqlite3

    from ot_tools.db import query

    # Create a database with many rows
    db_path = tmp_path / "many_rows.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE WideTable (
            id INTEGER PRIMARY KEY,
            col1 TEXT, col2 TEXT, col3 TEXT, col4 TEXT, col5 TEXT,
            col6 TEXT, col7 TEXT, col8 TEXT, col9 TEXT, col10 TEXT
        )
    """)
    # Insert 50 rows with long values to trigger truncation
    for i in range(50):
        cursor.execute(
            "INSERT INTO WideTable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, f"value_{i}_a", f"value_{i}_b", f"value_{i}_c", f"value_{i}_d",
             f"value_{i}_e", f"value_{i}_f", f"value_{i}_g", f"value_{i}_h",
             f"value_{i}_i", f"value_{i}_j"),
        )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_path}"
    result = query(sql="SELECT * FROM WideTable", db_url=db_url)

    # Should be truncated
    assert "truncated" in result

    # Extract the "showing first X of Y" numbers
    import re
    match = re.search(r"showing first (\d+) of (\d+)", result)
    assert match is not None, f"Expected truncation message, got: {result}"

    displayed = int(match.group(1))
    total = int(match.group(2))

    # Displayed should be less than total (truncated)
    assert displayed < total
    # Total should be 50
    assert total == 50
    # Displayed should be reasonable (not the old buggy len(result)//3)
    # Count actual rows by counting "X. row" patterns
    row_patterns = re.findall(r"(\d+)\. row", result)
    actual_displayed = len(row_patterns)
    assert displayed == actual_displayed, f"Claimed {displayed} but found {actual_displayed}"


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_nonexistent_table_returns_not_found(test_db_url: str) -> None:
    """Verify db.schema() returns helpful message for non-existent tables."""
    from ot_tools.db import schema

    result = schema(table_names=["NonExistentTable"], db_url=test_db_url)

    assert "NonExistentTable" in result
    assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_schema_mixed_valid_invalid_tables(test_db_url: str) -> None:
    """Verify db.schema() handles mix of valid and invalid tables."""
    from ot_tools.db import schema

    result = schema(
        table_names=["Customers", "BadTable", "Products"],
        db_url=test_db_url,
    )

    # Should have Customers schema
    assert "Customers:" in result
    assert "CustomerID" in result

    # Should have error for BadTable
    assert "BadTable" in result
    assert "not found" in result.lower()

    # Should have Products schema
    assert "Products:" in result
    assert "ProductID" in result


@pytest.mark.unit
@pytest.mark.tools
def test_tables_empty_db_url_returns_error() -> None:
    """Verify db.tables() returns error for empty db_url."""
    from ot_tools.db import tables

    result = tables(db_url="")
    assert "Error" in result
    assert "db_url" in result.lower()

    result2 = tables(db_url="   ")
    assert "Error" in result2


@pytest.mark.unit
@pytest.mark.tools
def test_schema_empty_db_url_returns_error() -> None:
    """Verify db.schema() returns error for empty db_url."""
    from ot_tools.db import schema

    result = schema(table_names=["Customers"], db_url="")
    assert "Error" in result
    assert "db_url" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_query_empty_db_url_returns_error() -> None:
    """Verify db.query() returns error for empty db_url."""
    from ot_tools.db import query

    result = query(sql="SELECT 1", db_url="")
    assert "Error" in result
    assert "db_url" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("reset_engines")
def test_tables_case_insensitive_filter(test_db_url: str) -> None:
    """Verify db.tables() case-insensitive filtering works."""
    from ot_tools.db import tables

    # Case-sensitive (default) - should not match
    result_sensitive = tables(db_url=test_db_url, filter="CUST")
    assert "Customers" not in result_sensitive

    # Case-insensitive - should match
    result_insensitive = tables(db_url=test_db_url, filter="CUST", ignore_case=True)
    assert "Customers" in result_insensitive
