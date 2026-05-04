# Database

Database introspection and query execution via SQLAlchemy. Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MS SQL Server, etc.).

## Highlights

- Connection pooling with automatic health checks and 1-hour recycling
- Vertical result formatting optimized for LLM consumption
- Parameterized queries for safe SQL execution
- Large results truncated at configurable character limit

## Functions

| Function | Description |
|----------|-------------|
| `db.tables(db_url, ...)` | List table names in the database |
| `db.sample(table, db_url, limit=10)` | Return sample rows from one table |
| `db.schema(table_names, db_url)` | Get schema definitions for tables |
| `db.query(sql, db_url, ...)` | Execute SQL and return formatted results |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `db_url` | str | SQLAlchemy connection string (required) |
| `filter` | str | Substring to filter table names (tables only) |
| `ignore_case` | bool | Case-insensitive filter matching (tables only, default: False) |
| `include_row_count` | bool | Include row counts in `db.tables()` output (default: False) |
| `table_names` | list[str] | Tables to inspect (schema only) |
| `table` | str | Table to preview (sample only) |
| `limit` | int | Max rows to return for `db.sample()` (default: 10) |
| `params` | dict | Query parameters for safe substitution (query only) |

## Project Configuration

Configure database connections in `onetool.yaml`:

```yaml
projects:
  myapp:
    path: /path/to/project
    attrs:
      db_url: postgresql://localhost/myapp

  demo:
    path: .
    attrs:
      db_url: sqlite:///demo/data/northwind.db
```

### Supported Databases

Any SQLAlchemy-compatible database:

- SQLite: `sqlite:///path/to/db.db`
- PostgreSQL: `postgresql://user:pass@host/db`
- MySQL: `mysql://user:pass@host/db`

## Configuration

### Required

- No required `tools.db` settings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.db.max_chars` | int | `4000` | Maximum characters in query output. Range: `100-100000`. |

```yaml
tools:
  db:
    max_chars: 8000
```

### Defaults

- If `tools.db` is omitted, query output is truncated at 4000 characters.

## Examples

```python
db_url = "postgresql://localhost/myapp"

# List all tables
db.tables(db_url=db_url)

# Filter tables
db.tables(db_url=db_url, filter="user")

# Include table row counts
db.tables(db_url=db_url, include_row_count=True)

# Sample rows from one table
db.sample(table="users", db_url=db_url, limit=5)

# Get schema for tables
db.schema(table_names=["users", "orders"], db_url=db_url)

# Execute queries (parameterized for safety)
db.query(sql="SELECT * FROM users LIMIT 5", db_url=db_url)
db.query(
    sql="SELECT * FROM users WHERE status = :status",
    db_url=db_url,
    params={"status": "active"}
)
```

## Security

- Queries are read-only by default
- Use parameterized queries for user input
- Configure `max_chars` to prevent excessive output

## Based on

This tool is based on [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy)
by Rui Machado, licensed under MPL-2.0.
