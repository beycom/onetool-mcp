# Tool-Db Specification

## Purpose

Provides database introspection and query execution for SQL databases via SQLAlchemy.
## Requirements
### Requirement: Table Listing

The `db.tables()` function SHALL list table names from the connected database.

#### Scenario: List all tables
- **GIVEN** a valid database URL
- **WHEN** `db.tables(db_url=...)` is called
- **THEN** it SHALL return a comma-separated list of all table names

#### Scenario: Filter tables by substring
- **GIVEN** a valid database URL and filter parameter
- **WHEN** `db.tables(db_url=..., filter="user")` is called
- **THEN** it SHALL return only table names containing "user"

### Requirement: Schema Definitions

The `db.schema()` function SHALL return detailed schema information for specified tables.

#### Scenario: Single table schema
- **GIVEN** a valid database URL
- **WHEN** `db.schema(["users"], db_url=...)` is called
- **THEN** it SHALL return schema including:
  - Column names and types
  - Primary key indicators
  - Nullable flags
  - Foreign key relationships

#### Scenario: Multiple table schemas
- **GIVEN** a valid database URL
- **WHEN** `db.schema(["users", "orders"], db_url=...)` is called
- **THEN** it SHALL return schemas for both tables
- **AND** each table SHALL be clearly labeled

#### Scenario: Relationship display
- **GIVEN** tables with foreign key relationships
- **WHEN** schema is retrieved
- **THEN** relationships SHALL be displayed as `column -> referenced_table.column`

### Requirement: Query Execution

The `db.query()` function SHALL execute SQL queries and return formatted results.

#### Scenario: Basic SELECT query
- **GIVEN** a valid database URL
- **WHEN** `db.query("SELECT * FROM users LIMIT 5", db_url=...)` is called
- **THEN** it SHALL return results in vertical format with row numbers

#### Scenario: Parameterized query
- **GIVEN** a query with parameters
- **WHEN** `db.query("SELECT * FROM users WHERE id = :id", db_url=..., params={"id": 123})` is called
- **THEN** it SHALL safely substitute parameters
- **AND** it SHALL prevent SQL injection

#### Scenario: Result truncation
- **GIVEN** a query returning large results
- **WHEN** results exceed the configured max characters (default 4000)
- **THEN** output SHALL be truncated with a count message

#### Scenario: No rows returned
- **GIVEN** a query matching no rows
- **WHEN** query is executed
- **THEN** it SHALL return "No rows returned"

#### Scenario: Non-SELECT query
- **GIVEN** an INSERT, UPDATE, or DELETE query
- **WHEN** query is executed
- **THEN** it SHALL return "Success: {n} rows affected"

#### Scenario: Query error
- **GIVEN** an invalid SQL query
- **WHEN** query is executed
- **THEN** it SHALL return "Error: {message}"

### Requirement: Connection Configuration

The tool SHALL require explicit database URL parameter on all functions.

#### Scenario: Database URL required
- **GIVEN** a db function call without `db_url` parameter
- **WHEN** the function is invoked
- **THEN** it SHALL fail with missing parameter error

#### Scenario: Valid connection string
- **GIVEN** `db_url` is a valid SQLAlchemy URL
- **WHEN** any db function is called with that URL
- **THEN** it SHALL connect successfully

#### Scenario: Multi-database session
- **GIVEN** multiple db function calls with different URLs
- **WHEN** queries are executed
- **THEN** each URL SHALL maintain its own connection pool

### Requirement: Connection Pooling

The tool SHALL use connection pooling optimized for long-running servers.

#### Scenario: Connection health check
- **GIVEN** a pooled connection
- **WHEN** a database operation is requested
- **THEN** it SHALL verify connection health before use (pool_pre_ping)

#### Scenario: Connection recycling
- **GIVEN** a connection older than 1 hour
- **WHEN** a database operation is requested
- **THEN** the old connection SHALL be recycled

#### Scenario: Transient failure recovery
- **GIVEN** a database connection failure
- **WHEN** the first attempt fails
- **THEN** it SHALL retry once with a fresh connection

### Requirement: Database Tool Logging

The tool SHALL log all operations using LogSpan.

#### Scenario: Query logging
- **GIVEN** a query is executed
- **WHEN** the query completes
- **THEN** it SHALL log:
  - `span: "db.query"`
  - `rows`: Number of rows returned
  - `truncated`: Whether output was truncated

#### Scenario: Error logging
- **GIVEN** any database operation fails
- **WHEN** error occurs
- **THEN** it SHALL log the error with appropriate context

### Requirement: SQLite Path Resolution

The tool SHALL expand path prefixes in SQLite database URLs.

#### Scenario: Tilde expansion in SQLite URL
- **GIVEN** a SQLite URL with tilde: `sqlite:///~/data.db`
- **WHEN** `db.query("SELECT 1", db_url="sqlite:///~/data.db")` is called
- **THEN** `~` SHALL expand to the user's home directory
- **AND** the connection SHALL be made to the expanded path

#### Scenario: CWD prefix in SQLite URL
- **GIVEN** a SQLite URL with CWD prefix: `sqlite:///CWD/data.db`
- **WHEN** `db.query("SELECT 1", db_url="sqlite:///CWD/data.db")` is called
- **THEN** `CWD` SHALL expand to the effective working directory (OT_CWD)

#### Scenario: Relative SQLite path
- **GIVEN** a relative SQLite URL: `sqlite:///data.db`
- **WHEN** `db.query("SELECT 1", db_url="sqlite:///data.db")` is called
- **THEN** the path SHALL be resolved relative to CWD

#### Scenario: Absolute SQLite path unchanged
- **GIVEN** an absolute SQLite URL: `sqlite:////tmp/data.db`
- **WHEN** `db.query("SELECT 1", db_url="sqlite:////tmp/data.db")` is called
- **THEN** the path SHALL be used unchanged

#### Scenario: Non-SQLite URLs unchanged
- **GIVEN** a non-SQLite URL: `postgresql://localhost/db`
- **WHEN** `db.query("SELECT 1", db_url="postgresql://localhost/db")` is called
- **THEN** the URL SHALL be passed to SQLAlchemy unchanged

