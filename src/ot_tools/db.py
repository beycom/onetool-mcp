# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "pydantic>=2.0.0", "pyyaml>=6.0.0", "sqlalchemy>=2.0.0"]
# ///
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""Database introspection and query execution tool.

Provides SQL database access via SQLAlchemy. Supports any SQLAlchemy-compatible
database (PostgreSQL, MySQL, SQLite, Oracle, MS SQL Server, etc.).

Based on mcp-alchemy by Rui Machado (MPL 2.0).
https://github.com/runekaagaard/mcp-alchemy

Requires explicit db_url parameter for all operations.

Examples:
    # Get db_url from project config
    db.tables(db_url=proj.attr("myproject", "db_url"))

    # Or use literal URL
    db.tables(db_url="sqlite:///path/to/database.db")
    db.query("SELECT 1", db_url="postgresql://user:pass@localhost/dbname")
"""

from __future__ import annotations

# Pack for dot notation: db.tables(), db.schema(), db.query()
pack = "db"

__all__ = ["query", "schema", "tables"]

import contextlib
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Engine, create_engine, inspect, text

from ot_sdk import get_config, log, resolve_cwd_path, worker_main


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    max_chars: int = Field(
        default=4000,
        ge=100,
        le=100000,
        description="Maximum characters in query result output",
    )

# Connection pool keyed by URL - persists across calls in worker
_engines: dict[str, Engine] = {}


def _resolve_sqlite_url(db_url: str) -> str:
    """Resolve relative paths in SQLite URLs.

    SQLite URLs use the format sqlite:///path/to/db.
    If the path is relative, resolve it against the project working directory.

    Args:
        db_url: Database URL string

    Returns:
        URL with resolved path if SQLite with relative path, otherwise unchanged
    """
    if not db_url.startswith("sqlite:///"):
        return db_url

    # Extract path from sqlite:///path
    path = db_url[10:]  # len("sqlite:///") == 10

    # Skip in-memory databases and absolute paths
    if not path or path == ":memory:" or path.startswith("/"):
        return db_url

    # Resolve relative path against project directory
    resolved = resolve_cwd_path(path)
    return f"sqlite:///{resolved}"


def _create_engine(db_url: str) -> Engine:
    """Create SQLAlchemy engine with MCP-optimized settings."""
    # MCP-optimized defaults
    options: dict[str, Any] = {
        "isolation_level": "AUTOCOMMIT",
        "pool_pre_ping": True,  # Test connections before use
        "pool_size": 1,  # Single connection for MCP patterns
        "max_overflow": 2,  # Allow temporary burst capacity
        "pool_recycle": 3600,  # Refresh connections older than 1hr
    }

    return create_engine(db_url, **options)


def _get_engine(db_url: str) -> Engine:
    """Get or create engine for given URL with retry logic."""
    global _engines

    # Resolve relative paths in SQLite URLs
    resolved_url = _resolve_sqlite_url(db_url)

    if resolved_url in _engines:
        return _engines[resolved_url]

    with log("db.connect", db_url=resolved_url) as span:
        try:
            _engines[resolved_url] = _create_engine(resolved_url)
            span.add(cached=False)
            return _engines[resolved_url]

        except Exception:
            # Database might have restarted - try fresh
            if resolved_url in _engines:
                with contextlib.suppress(Exception):
                    _engines[resolved_url].dispose()
                del _engines[resolved_url]

            # One retry with fresh engine
            span.add(retry=True)
            _engines[resolved_url] = _create_engine(resolved_url)
            return _engines[resolved_url]


def _format_value(val: Any) -> str:
    """Format a value for display."""
    if val is None:
        return "NULL"
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val)


def tables(*, db_url: str, filter: str | None = None) -> str:
    """List table names in the database.

    Args:
        db_url: Database URL (required)
        filter: Optional substring to filter table names

    Returns:
        Comma-separated list of table names

    Example:
        # List all tables
        db.tables(db_url=proj.attr("myproject", "db_url"))

        # Filter tables containing "user"
        db.tables(db_url="sqlite:///data.db", filter="user")
    """
    with log("db.tables", db_url=db_url, filter=filter) as s:
        try:
            engine = _get_engine(db_url)
            with engine.connect() as conn:
                inspector = inspect(conn)
                all_tables = inspector.get_table_names()

                if filter:
                    all_tables = [t for t in all_tables if filter in t]

                s.add(resultCount=len(all_tables))
                return ", ".join(all_tables) if all_tables else "No tables found"

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def schema(*, table_names: list[str], db_url: str) -> str:
    """Get schema definitions for specified tables.

    Returns column names, types, primary keys, and foreign key relationships.

    Args:
        table_names: List of table names to inspect
        db_url: Database URL (required)

    Returns:
        Formatted schema definitions

    Example:
        # Single table
        db.schema(table_names=["users"], db_url=ot.project("myproject", attr="db_url"))

        # Multiple tables
        db.schema(table_names=["users", "orders"], db_url="sqlite:///data.db")
    """
    with log("db.schema", tables=table_names, db_url=db_url) as s:
        if not table_names:
            s.add(error="no_tables")
            return "Error: table_names parameter is required"

        try:
            engine = _get_engine(db_url)
            with engine.connect() as conn:
                inspector = inspect(conn)
                results: list[str] = []

                for table_name in table_names:
                    results.append(_format_table_schema(inspector, table_name))

                s.add(resultCount=len(table_names))
                return "\n".join(results)

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def _format_table_schema(inspector: Any, table_name: str) -> str:
    """Format schema for a single table."""
    columns = inspector.get_columns(table_name)
    foreign_keys = inspector.get_foreign_keys(table_name)
    pk_constraint = inspector.get_pk_constraint(table_name)
    primary_keys = set(pk_constraint.get("constrained_columns", []))

    result = [f"{table_name}:"]

    # Process columns
    show_key_only = {"nullable", "autoincrement"}
    for column in columns:
        if "comment" in column:
            del column["comment"]
        name = column.pop("name")
        col_type = str(column.pop("type"))

        parts = []
        if name in primary_keys:
            parts.append("primary key")
        parts.append(col_type)

        for k, v in column.items():
            if v:
                if k in show_key_only:
                    parts.append(k)
                else:
                    parts.append(f"{k}={v}")

        result.append(f"    {name}: " + ", ".join(parts))

    # Process relationships
    if foreign_keys:
        result.extend(["", "    Relationships:"])
        for fk in foreign_keys:
            constrained = ", ".join(fk["constrained_columns"])
            referred_table = fk["referred_table"]
            referred_cols = ", ".join(fk["referred_columns"])
            result.append(f"      {constrained} -> {referred_table}.{referred_cols}")

    return "\n".join(result)


def query(*, sql: str, db_url: str, params: dict[str, Any] | None = None) -> str:
    """Execute a SQL query and return formatted results.

    IMPORTANT: Always use the params parameter for variable substitution
    (e.g., 'WHERE id = :id' with params={'id': 123}) to prevent SQL injection.

    Args:
        sql: SQL query to execute
        db_url: Database URL (required)
        params: Query parameters for safe substitution

    Returns:
        Formatted query results or error message

    Example:
        # Basic query
        db.query(sql="SELECT * FROM users LIMIT 5", db_url=ot.project("myproject", attr="db_url"))

        # Parameterized query (safe from SQL injection)
        db.query(
            sql="SELECT * FROM users WHERE status = :status",
            db_url="sqlite:///data.db",
            params={"status": "active"}
        )

        # INSERT/UPDATE/DELETE
        db.query(
            sql="UPDATE users SET status = :status WHERE id = :id",
            db_url="postgresql://user:pass@localhost/db",
            params={"status": "inactive", "id": 123}
        )
    """
    with log("db.query", sql=sql, db_url=db_url) as s:
        if not sql or not sql.strip():
            s.add(error="empty_query")
            return "Error: sql parameter is required"

        try:
            engine = _get_engine(db_url)
            with engine.connect() as conn:
                cursor_result = conn.execute(text(sql), params or {})

                if not cursor_result.returns_rows:
                    affected = cursor_result.rowcount
                    s.add(rowsAffected=affected)
                    return f"Success: {affected} rows affected"

                max_chars = get_config("tools.db.max_chars") or 4000
                output, row_count, truncated = _format_query_results(
                    cursor_result, max_chars
                )
                s.add(rows=row_count, truncated=truncated)
                return output

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def _format_query_results(cursor_result: Any, max_chars: int) -> tuple[str, int, bool]:
    """Format query results in vertical format.

    Args:
        cursor_result: SQLAlchemy cursor result
        max_chars: Maximum characters for output

    Returns:
        Tuple of (formatted_output, row_count, was_truncated)
    """
    result: list[str] = []
    size = 0
    row_count = 0
    truncated = False
    keys = list(cursor_result.keys())

    while row := cursor_result.fetchone():
        row_count += 1

        if truncated:
            continue

        sub_result = [f"{row_count}. row"]
        for col, val in zip(keys, row, strict=True):
            sub_result.append(f"{col}: {_format_value(val)}")
        sub_result.append("")

        row_size = sum(len(x) + 1 for x in sub_result)
        size += row_size

        if size > max_chars:
            truncated = True
        else:
            result.extend(sub_result)

    if row_count == 0:
        return "No rows returned", 0, False

    if truncated:
        result.append(
            f"Result: showing first {len(result) // 3} of {row_count} rows (output truncated)"
        )
    else:
        result.append(f"Result: {row_count} rows")

    return "\n".join(result), row_count, truncated


if __name__ == "__main__":
    worker_main()
