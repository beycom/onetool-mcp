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
doc_slug = "db"

__all__ = ["query", "sample", "schema", "tables"]

import contextlib
import threading
from collections import OrderedDict
from datetime import date, datetime
from typing import Any, cast

from pydantic import BaseModel, Field

from otpack import LogSpan, get_tool_config, resolve_cwd_path


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    max_chars: int = Field(
        default=4000,
        ge=100,
        le=100000,
        description="Maximum characters in query result output",
    )


def _get_config() -> Config:
    """Get db pack configuration."""
    return get_tool_config("db", Config)


# Connection pool keyed by URL - persists across calls in process
# Uses OrderedDict for LRU eviction with bounded size
_ENGINES_MAXSIZE = 8
_engines_lock = threading.Lock()
_engines: OrderedDict[str, Any] = OrderedDict()


def _require_sqlalchemy() -> None:
    """Check sqlalchemy is available, raise helpful error if not."""
    try:
        import sqlalchemy  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Database tools require the [dev] extra. "
            "Install with: pip install onetool-mcp[dev]"
        ) from exc


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


def _create_engine(db_url: str) -> Any:
    """Create SQLAlchemy engine with MCP-optimized settings."""
    from sqlalchemy import create_engine as _ce

    # MCP-optimized defaults
    options: dict[str, Any] = {
        "isolation_level": "AUTOCOMMIT",
        "pool_pre_ping": True,  # Test connections before use
        "pool_size": 1,  # Single connection for MCP patterns
        "max_overflow": 2,  # Allow temporary burst capacity
        "pool_recycle": 3600,  # Refresh connections older than 1hr
    }

    return _ce(db_url, **options)


def _get_engine(db_url: str) -> Any:
    """Get or create engine for given URL with retry logic."""
    # Resolve relative paths in SQLite URLs
    resolved_url = _resolve_sqlite_url(db_url)

    # Fast path: check cache with lock
    with _engines_lock:
        if resolved_url in _engines:
            # LRU: move to end on access
            _engines.move_to_end(resolved_url)
            return _engines[resolved_url]

    # Create engine outside lock (slow operation)
    with LogSpan(span="db.connect", dbUrl=resolved_url) as span:
        try:
            engine = _create_engine(resolved_url)
        except Exception:
            span.add(retry=True)
            # One retry with fresh engine
            engine = _create_engine(resolved_url)

        # Double-check after acquiring lock
        with _engines_lock:
            if resolved_url in _engines:
                # Another thread created it while we were waiting
                engine.dispose()
                _engines.move_to_end(resolved_url)
                return _engines[resolved_url]

            _engines[resolved_url] = engine

            # LRU eviction: dispose oldest engine when over maxsize
            while len(_engines) > _ENGINES_MAXSIZE:
                _, oldest_engine = _engines.popitem(last=False)
                with contextlib.suppress(Exception):
                    oldest_engine.dispose()

            span.add(cached=False)
            return engine


def _format_value(val: Any) -> str:
    """Format a value for display."""
    if val is None:
        return "NULL"
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val)


def _convert_value_for_json(val: Any) -> Any:
    """Convert a value to JSON-serializable format.

    Handles datetime/date objects by converting to ISO format strings.
    None values are preserved as null in JSON.
    """
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def tables(
    *,
    db_url: str,
    filter: str | None = None,
    ignore_case: bool = False,
    include_row_count: bool = False,
) -> list[str] | list[dict[str, Any]] | str:
    """List table names in the database.

    Args:
        db_url: Database URL (required)
        filter: Optional substring to filter table names
        ignore_case: If True, filter matching is case-insensitive
        include_row_count: If True, include row counts for each table

    Returns:
        List of table names, list of table/count dicts, or error string

    Example:
        # List all tables
        db.tables(db_url=proj.attr("myproject", "db_url"))

        # Filter tables containing "user"
        db.tables(db_url="sqlite:///data.db", filter="user")

        # Case-insensitive filter
        db.tables(db_url="sqlite:///data.db", filter="USER", ignore_case=True)
    """
    _require_sqlalchemy()
    with LogSpan(
        span="db.tables",
        dbUrl=db_url,
        filter=filter,
        includeRowCount=include_row_count,
    ) as s:
        if not db_url or not db_url.strip():
            s.add(error="empty_db_url")
            return "Error: db_url parameter is required"

        try:
            from sqlalchemy import inspect as _inspect

            engine = _get_engine(db_url)
            with engine.connect() as conn:
                inspector = _inspect(conn)
                all_tables = inspector.get_table_names()

                if filter:
                    if ignore_case:
                        filter_lower = filter.lower()
                        all_tables = [t for t in all_tables if filter_lower in t.lower()]
                    else:
                        all_tables = [t for t in all_tables if filter in t]

                if not include_row_count:
                    s.add(resultCount=len(all_tables))
                    return cast("list[str]", all_tables)

                from sqlalchemy import MetaData, Table, func, select

                rows: list[dict[str, Any]] = []
                for table_name in all_tables:
                    table = Table(table_name, MetaData(), autoload_with=conn)
                    row_count = conn.execute(
                        select(func.count()).select_from(table)
                    ).scalar_one()
                    rows.append({"table_name": table_name, "row_count": int(row_count)})

                s.add(resultCount=len(rows))
                return rows

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def schema(*, table_names: list[str], db_url: str) -> list[dict[str, Any]] | str:
    """Get schema definitions for specified tables.

    Returns column names, types, primary keys, and foreign key relationships.

    Args:
        table_names: List of table names to inspect
        db_url: Database URL (required)

    Returns:
        List of schema dicts for each table, or error string

    Example:
        # Single table
        db.schema(table_names=["users"], db_url=ot.project("myproject", attr="db_url"))

        # Multiple tables
        db.schema(table_names=["users", "orders"], db_url="sqlite:///data.db")
    """
    _require_sqlalchemy()
    with LogSpan(span="db.schema", tables=table_names, dbUrl=db_url) as s:
        if not db_url or not db_url.strip():
            s.add(error="empty_db_url")
            return "Error: db_url parameter is required"

        if not table_names:
            s.add(error="no_tables")
            return "Error: table_names parameter is required"

        try:
            from sqlalchemy import inspect as _inspect

            engine = _get_engine(db_url)
            with engine.connect() as conn:
                inspector = _inspect(conn)
                results: list[dict[str, Any]] = []

                for table_name in table_names:
                    results.append(_get_table_schema(inspector, table_name))

                s.add(resultCount=len(table_names))
                return results

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def _get_table_schema(inspector: Any, table_name: str) -> dict[str, Any]:
    """Get schema for a single table as structured data.

    Returns:
        Dict with table_name, columns, and relationships
    """
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return {"table_name": table_name, "error": "table not found"}

    try:
        foreign_keys = inspector.get_foreign_keys(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
    except Exception:
        foreign_keys = []
        pk_constraint = {}

    primary_keys = set(pk_constraint.get("constrained_columns", []))

    # Process columns into structured format
    column_defs = []
    for column in columns:
        col_def: dict[str, Any] = {
            "name": column["name"],
            "type": str(column["type"]),
            "primary_key": column["name"] in primary_keys,
        }

        # Add optional properties
        if column.get("nullable") is not None:
            col_def["nullable"] = column["nullable"]
        if column.get("autoincrement"):
            col_def["autoincrement"] = True
        if column.get("default") is not None:
            col_def["default"] = str(column["default"])

        column_defs.append(col_def)

    # Process foreign keys into structured format
    relationships = []
    for fk in foreign_keys:
        relationships.append({
            "constrained_columns": fk["constrained_columns"],
            "referred_table": fk["referred_table"],
            "referred_columns": fk["referred_columns"],
        })

    return {
        "table_name": table_name,
        "columns": column_defs,
        "relationships": relationships,
    }


def sample(
    *,
    table: str,
    db_url: str,
    limit: int = 10,
) -> list[dict[str, Any]] | str:
    """Fetch a quick sample of rows from a table.

    Args:
        table: Table name to sample
        db_url: Database URL (required)
        limit: Maximum rows to return (default: 10)

    Returns:
        List of sampled rows, or error string
    """
    _require_sqlalchemy()
    with LogSpan(span="db.sample", table=table, dbUrl=db_url, limit=limit) as s:
        if not db_url or not db_url.strip():
            s.add(error="empty_db_url")
            return "Error: db_url parameter is required"

        if not table or not table.strip():
            s.add(error="empty_table")
            return "Error: table parameter is required"

        if limit <= 0:
            s.add(error="invalid_limit")
            return "Error: limit must be greater than 0"

        try:
            from sqlalchemy import MetaData, Table, select

            engine = _get_engine(db_url)
            with engine.connect() as conn:
                table_ref = Table(table, MetaData(), autoload_with=conn)
                cursor_result = conn.execute(select(table_ref).limit(limit))
                rows_data, _, _ = _convert_query_results_to_json(cursor_result, limit)
                s.add(resultCount=len(rows_data))
                return rows_data
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"




_READ_ONLY_KEYWORDS = ("SELECT", "EXPLAIN", "PRAGMA")


def _is_read_only_sql(sql: str) -> bool:
    """Return True if sql's first keyword is SELECT, EXPLAIN, or PRAGMA."""
    stripped = sql.strip()
    if not stripped:
        return False
    first_word = stripped.split(None, 1)[0].upper()
    return first_word in _READ_ONLY_KEYWORDS


def query(
    *,
    sql: str,
    db_url: str,
    params: dict[str, Any] | None = None,
    read_only: bool = False,
) -> dict[str, Any] | list[dict[str, Any]] | str:
    """Execute a SQL query and return results.

    IMPORTANT: Always use the params parameter for variable substitution
    (e.g., 'WHERE id = :id' with params={'id': 123}) to prevent SQL injection.

    Args:
        sql: SQL query to execute
        db_url: Database URL (required)
        params: Query parameters for safe substitution
        read_only: If True, reject any statement whose first keyword is not
            SELECT, EXPLAIN, or PRAGMA (default: False)

    Returns:
        Dict with rows/row_count/truncated for SELECT, success dict for INSERT/UPDATE/DELETE, or error string

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
    _require_sqlalchemy()
    with LogSpan(span="db.query", sql=sql, dbUrl=db_url) as s:
        if not db_url or not db_url.strip():
            s.add(error="empty_db_url")
            return "Error: db_url parameter is required"

        if not sql or not sql.strip():
            s.add(error="empty_query")
            return "Error: sql parameter is required"

        if read_only and not _is_read_only_sql(sql):
            s.add(error="read_only_violation")
            return "Error: read_only=True but statement is not SELECT/EXPLAIN/PRAGMA"

        try:
            engine = _get_engine(db_url)
            with engine.connect() as conn:
                from sqlalchemy import text as _text

                cursor_result = conn.execute(_text(sql), params or {})

                if not cursor_result.returns_rows:
                    affected = cursor_result.rowcount
                    s.add(rowsAffected=affected)
                    return {
                        "success": True,
                        "rows_affected": affected,
                        "message": f"{affected} rows affected",
                    }

                max_rows = _get_config().max_chars // 100  # Rough estimate for row limit
                rows_data, row_count, truncated = _convert_query_results_to_json(
                    cursor_result, max_rows
                )
                s.add(rows=row_count, truncated=truncated)

                return {
                    "rows": rows_data,
                    "row_count": row_count,
                    "truncated": truncated,
                }

        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def _convert_query_results_to_json(
    cursor_result: Any, max_rows: int
) -> tuple[list[dict[str, Any]], int, bool]:
    """Convert query results to JSON-serializable list of dicts.

    Args:
        cursor_result: SQLAlchemy cursor result
        max_rows: Maximum number of rows to return

    Returns:
        Tuple of (rows_list, total_row_count, was_truncated)
    """
    rows_data: list[dict[str, Any]] = []
    row_count = 0
    truncated = False
    keys = list(cursor_result.keys())

    while row := cursor_result.fetchone():
        row_count += 1

        if row_count <= max_rows:
            # Convert row to dict with JSON-serializable values
            row_dict = {}
            for col, val in zip(keys, row, strict=True):
                row_dict[col] = _convert_value_for_json(val)
            rows_data.append(row_dict)
        else:
            truncated = True

    return rows_data, row_count, truncated
