# Database

**Any SQL database. Three functions. LLM-friendly output.**

Database introspection and query execution via SQLAlchemy. Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MS SQL Server, etc.).

## Highlights

- Connection pooling with automatic health checks
- Vertical result formatting optimized for LLM consumption
- Parameterized queries for safe SQL execution
- Large results truncated at 4000 characters
- Per-URL connection pools with 1-hour recycling

## Functions

| Function | Description |
|----------|-------------|
| `db.tables(db_url, ...)` | List table names in the database |
| `db.schema(table_names, db_url)` | Get schema definitions for tables |
| `db.query(sql, db_url, ...)` | Execute SQL and return formatted results |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `db_url` | str | SQLAlchemy connection string (required) |
| `filter` | str | Substring to filter table names (tables only) |
| `ignore_case` | bool | Case-insensitive filter matching (tables only, default: False) |
| `table_names` | list[str] | Tables to inspect (schema only) |
| `params` | dict | Query parameters for safe substitution (query only) |

## Examples

```python
# Get database URL from project config
db_url = proj.attr("myproject", "db_url")

# List all tables
db.tables(db_url=db_url)

# Filter tables
db.tables(db_url=db_url, filter="user")

# Case-insensitive filter
db.tables(db_url=db_url, filter="USER", ignore_case=True)

# Get schema for tables
db.schema(["users", "orders"], db_url=db_url)

# Execute queries (parameterized for safety)
db.query("SELECT * FROM users LIMIT 5", db_url=db_url)
db.query(
    "SELECT * FROM users WHERE status = :status",
    db_url=db_url,
    params={"status": "active"}
)
```

## Source

[SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

## Based on

[mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) by Rui Machado (MPL-2.0)
