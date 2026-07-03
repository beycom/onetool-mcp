## MODIFIED Requirements

### Requirement: Query Execution

The `db.query()` function SHALL execute SQL queries and return formatted results. It SHALL accept an opt-in `read_only: bool = False` parameter; when `True`, the call SHALL be rejected unless the statement's first keyword is `SELECT`, `EXPLAIN`, or `PRAGMA`. Default behavior (`read_only=False`) is unchanged from prior versions: any statement is executed under autocommit.

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
- **WHEN** query is executed without `read_only`
- **THEN** it SHALL return "Success: {n} rows affected"

#### Scenario: Query error
- **GIVEN** an invalid SQL query
- **WHEN** query is executed
- **THEN** it SHALL return "Error: {message}"

#### Scenario: read_only rejects a write statement
- **GIVEN** a valid database URL
- **WHEN** `db.query(sql="INSERT INTO users (name) VALUES ('x')", db_url=..., read_only=True)` is called
- **THEN** it SHALL return an error indicating the statement is not SELECT/EXPLAIN/PRAGMA
- **AND** the statement SHALL NOT be executed against the database

#### Scenario: read_only allows SELECT, EXPLAIN, and PRAGMA
- **GIVEN** a valid database URL
- **WHEN** `db.query(sql="SELECT * FROM users", db_url=..., read_only=True)`, `db.query(sql="EXPLAIN SELECT * FROM users", db_url=..., read_only=True)`, or `db.query(sql="PRAGMA table_info(users)", db_url=..., read_only=True)` is called
- **THEN** each SHALL execute normally and return results, identical to calling without `read_only`

#### Scenario: read_only is opt-in and off by default
- **GIVEN** a valid database URL
- **WHEN** `db.query(sql="INSERT INTO users (name) VALUES ('x')", db_url=...)` is called without specifying `read_only`
- **THEN** the statement SHALL execute normally (the default `read_only=False` preserves pre-existing behavior)
