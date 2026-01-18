# Database

**Any SQL database. Three functions. LLM-friendly output.**

Database introspection and query execution via SQLAlchemy. Supports any SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite, Oracle, MS SQL Server, etc.).

| Function | Description |
|----------|-------------|
| `db.tables(db_url, ...)` | List table names in the database |
| `db.schema(table_names, db_url)` | Get schema definitions for tables |
| `db.query(sql, db_url, ...)` | Execute SQL and return formatted results |

**Key Parameters:**
- `db_url`: Database URL (required) - SQLAlchemy connection string
- `filter`: Substring to filter table names (tables only)
- `table_names`: List of tables to inspect (schema only)
- `params`: Query parameters for safe substitution (query only)

**Example:**

```python
# Get database URL from project config
db_url = proj.attr("myproject", "db_url")

# List all tables
db.tables(db_url=db_url)

# Filter tables
db.tables(db_url=db_url, filter="user")

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

**Based on:** [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) by Rui Machado

**Implementation notes:**
- Connection pooling with automatic health checks (`pool_pre_ping`)
- Connections recycled after 1 hour
- Results formatted in vertical format with row numbers
- Large results truncated at 4000 characters
- Each unique `db_url` maintains its own connection pool

**Comparison:** Based on mcp-alchemy with simplified API. Requires explicit db_url parameter (no environment fallback), vertical result formatting optimized for LLM consumption.

**License:** MPL 2.0 ([LICENSE](../licenses/mcp-alchemy-LICENSE))
