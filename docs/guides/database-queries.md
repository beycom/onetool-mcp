# Database Queries

**SQL from your AI. Three functions. Any database.**

The `db.*` namespace gives LLMs direct database access - explore tables, inspect schemas, run queries.

## Available Functions

| Function | Purpose |
|----------|---------|
| `db.tables(project)` | List all tables in a database |
| `db.schema(project, table)` | Get table schema |
| `db.query(project, sql)` | Execute SQL query |

## Setup

Configure database connections in `ot-serve.yaml`:

```yaml
projects:
  myapp:
    path: /path/to/project
    attrs:
      db_url: postgresql://localhost/myapp

  demo:
    path: .
    attrs:
      db_url: sqlite:///demo/db/northwind.db
```

## Basic Usage

### List Tables

```python
db.tables(project="demo")
```

### Get Schema

```python
db.schema(project="demo", table="customers")
```

### Run Query

```python
db.query(project="demo", sql="SELECT * FROM customers LIMIT 10")
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `db.max_chars` | 4000 | Maximum output characters |

Override in config:

```yaml
tools:
  db:
    max_chars: 8000  # Larger output
```

## Supported Databases

Any SQLAlchemy-compatible database:

- SQLite: `sqlite:///path/to/db.db`
- PostgreSQL: `postgresql://user:pass@host/db`
- MySQL: `mysql://user:pass@host/db`

## Security Notes

- Queries are read-only by default
- Use parameterized queries for user input
- Configure `max_chars` to prevent excessive output

## Example Workflow

```python
# 1. Explore available tables
tables = db.tables(project="demo")

# 2. Check schema
schema = db.schema(project="demo", table="orders")

# 3. Query data
results = db.query(
    project="demo",
    sql="SELECT customer_id, COUNT(*) as order_count FROM orders GROUP BY customer_id"
)
```