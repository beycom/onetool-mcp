# testing Specification

## Purpose

Defines testing conventions and requirements for OneTool. Covers test organization, markers, fixtures, and CI integration.
## Requirements
### Requirement: Test Principles

All tests SHALL follow core testing principles.

#### Scenario: Lean tests
- **GIVEN** a feature needs testing
- **WHEN** writing tests
- **THEN** write the minimum tests to verify behavior
- **AND** do not test implementation details

#### Scenario: DRY fixtures
- **GIVEN** multiple tests need similar setup
- **WHEN** creating fixtures
- **THEN** share setup code via `conftest.py`
- **AND** do not duplicate fixture code in test files

#### Scenario: Behavior focus
- **GIVEN** a test is being written
- **WHEN** designing assertions
- **THEN** focus on inputs/outputs
- **NOT** internal code paths

---

### Requirement: Test Markers

Every test SHALL have exactly two required markers: a speed tier and a component tag.

#### Scenario: Speed tier required
- **GIVEN** a test function
- **WHEN** defined
- **THEN** it SHALL have exactly one speed tier marker

#### Scenario: Component tag required
- **GIVEN** a test function
- **WHEN** defined
- **THEN** it SHALL have exactly one component tag marker

#### Scenario: Valid speed tiers
- **GIVEN** a test needs a speed tier
- **WHEN** selecting a marker
- **THEN** it SHALL be one of:
  - `smoke` - <1s, no I/O, quick sanity checks
  - `unit` - <1s, no I/O, fast isolated tests
  - `integration` - may be slow, end-to-end tests
  - `slow` - >10s, long-running tests

#### Scenario: Valid component tags
- **GIVEN** a test needs a component tag
- **WHEN** selecting a marker
- **THEN** it SHALL be one of:
  - `tools` - Tool implementations (`ot_tools`)
  - `core` - Core library (`ot`)
  - `serve` - MCP server (`ot_serve`)
  - `bench` - Benchmark harness (`ot_bench`)
  - `pkg` - Package management
  - `spec` - OpenSpec tooling

---

### Requirement: Dependency Markers

Tests requiring external dependencies SHALL declare them.

#### Scenario: Network dependency
- **GIVEN** a test requires network access
- **WHEN** the test is defined
- **THEN** it SHALL have the `network` marker

#### Scenario: API key dependency
- **GIVEN** a test requires API keys
- **WHEN** the test is defined
- **THEN** it SHALL have the `api` marker

#### Scenario: Docker dependency
- **GIVEN** a test requires Docker
- **WHEN** the test is defined
- **THEN** it SHALL have the `docker` marker

---

### Requirement: Test Organization

Tests SHALL be organized by speed tier.

#### Scenario: Directory structure
- **GIVEN** tests are organized
- **WHEN** creating the test directory structure
- **THEN** it SHALL follow:
  ```
  tests/
  ├── conftest.py              # Shared fixtures
  ├── smoke/                   # Quick sanity checks
  ├── unit/                    # Fast isolated tests (mocked dependencies)
  │   ├── core/                # Core library tests
  │   ├── bench/               # Benchmark harness tests
  │   ├── serve/               # MCP server tests
  │   ├── sdk/                 # SDK tests
  │   └── tools/               # Tool unit tests
  └── integration/             # End-to-end tests (real dependencies)
      └── tools/               # Tool integration tests
  ```

- **AND** unit and integration tests MAY mirror each other with same filenames
- **AND** mirrored structures require `__init__.py` files to avoid module name collisions

#### Scenario: conftest.py location
- **GIVEN** shared fixtures are needed
- **WHEN** creating fixtures
- **THEN** they SHALL be in `tests/conftest.py`

---

### Requirement: Fixture Guidelines

Fixtures SHALL be shared via conftest.py.

#### Scenario: Shared fixture
- **GIVEN** a fixture is used by multiple tests
- **WHEN** defining the fixture
- **THEN** it SHALL be in `tests/conftest.py`

#### Scenario: No duplicate setup
- **GIVEN** tests need similar setup
- **WHEN** writing test functions
- **THEN** they SHALL use fixtures
- **NOT** duplicate setup code

---

### Requirement: CI Integration

Tests SHALL support tiered CI execution.

#### Scenario: Push builds
- **GIVEN** code is pushed to a branch
- **WHEN** CI runs
- **THEN** it SHALL execute `pytest -m smoke` (~30s)

#### Scenario: PR builds
- **GIVEN** a pull request is created
- **WHEN** CI runs
- **THEN** it SHALL execute `pytest -m "not slow"` (~2min)

#### Scenario: Nightly builds
- **GIVEN** scheduled nightly build
- **WHEN** CI runs
- **THEN** it SHALL execute full test suite including slow tests

---

### Requirement: Test Execution

Tests SHALL support filtering by markers.

#### Scenario: Run smoke tests only
- **GIVEN** a user wants quick feedback
- **WHEN** running `uv run pytest -m smoke`
- **THEN** only smoke tests SHALL execute

#### Scenario: Run specific component
- **GIVEN** a user wants to test one component
- **WHEN** running `uv run pytest -m serve`
- **THEN** only serve component tests SHALL execute

#### Scenario: Combine markers
- **GIVEN** a user wants specific intersection
- **WHEN** running `uv run pytest -m "smoke and serve"`
- **THEN** only tests with both markers SHALL execute

#### Scenario: Skip slow tests
- **GIVEN** a user wants fast feedback
- **WHEN** running `uv run pytest -m "not slow"`
- **THEN** slow tests SHALL be skipped

#### Scenario: Skip network tests
- **GIVEN** a user is offline
- **WHEN** running `uv run pytest -m "not network"`
- **THEN** network-dependent tests SHALL be skipped

### Requirement: Executor Fixture

Tests requiring Python code execution SHALL use the `executor` fixture.

#### Scenario: Executor fixture available
- **GIVEN** a test needs to execute Python code
- **WHEN** the test is defined
- **THEN** it SHALL use the `executor` fixture from `tests/conftest.py`
- **AND** the fixture provides direct execution without LLM

#### Scenario: Executor fixture implementation
- **GIVEN** `tests/conftest.py`
- **WHEN** the `executor` fixture is defined
- **THEN** it SHALL:
  - Import `execute_python_code` from `ot.executor.runner`
  - Import `load_tool_functions` from `ot.executor.tool_loader`
  - Load tool functions from `src/ot_tools/`
  - Return a callable that executes code and returns results
- **AND** NOT require LLM or API calls

#### Scenario: Executor test speed
- **GIVEN** tests using the `executor` fixture
- **WHEN** they run
- **THEN** they SHALL complete in milliseconds
- **AND** be marked with the `unit` speed tier

---

### Requirement: Execution Engine Tests

The execution engine SHALL have dedicated unit tests.

#### Scenario: Test file location
- **GIVEN** execution engine tests
- **WHEN** organised
- **THEN** they SHALL be in `tests/unit/test_python_exec.py`

#### Scenario: Test categories
- **GIVEN** `test_python_exec.py`
- **WHEN** defining tests
- **THEN** it SHALL cover:
  - Parsing (arguments, nested calls, multiline, literals)
  - Execution (variables, loops, conditionals, comprehensions, functions)
  - Return values (expression, print, function return, edge cases)
  - Imports (patterns, usage)
  - Errors (indentation, brackets, names)
  - Exceptions (raise, runtime)
  - Timeout (infinite loops)

#### Scenario: Test markers
- **GIVEN** execution engine tests
- **WHEN** defined
- **THEN** they SHALL have:
  - Speed tier: `unit`
  - Component: `core`

