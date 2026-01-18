# Testing Strategy

**Fast feedback. Lean tests. Two markers per test.**

Every test gets a speed tier and a component tag. CI runs smoke tests in 30 seconds.

## Principles

1. **Lean tests** - Write the minimum tests to verify behaviour works. Don't test implementation details.
2. **DRY fixtures** - Share setup code via `conftest.py`. Don't duplicate.
3. **Test behaviour** - Focus on inputs/outputs, not internal code paths.
4. **Fast feedback** - Smoke tests run in CI on every push. Slow tests run on merge.
5. **Isolation** - Mock HTTP/subprocess calls to avoid network I/O in unit tests.

## Test Markers

Every test requires two markers: a **speed tier** and a **component tag**.

### Speed Tiers (pick one)

| Marker | Criteria | When to use |
|--------|----------|-------------|
| `smoke` | <1s, no I/O | Quick sanity checks that verify basic functionality |
| `unit` | <1s, no I/O | Fast isolated tests for pure logic |
| `integration` | May be slow | End-to-end tests with real dependencies |
| `slow` | >10s | Long-running tests (benchmarks, large data) |

### Component Tags (pick one)

| Marker | Component |
|--------|-----------|
| `tools` | Tool implementations (`ot_tools`) |
| `core` | Core library (`ot`) |
| `serve` | MCP server (`ot_serve`) |
| `bench` | Benchmark harness (`ot_bench`) |
| `browse` | Browser inspector (`ot_browse`) |
| `pkg` | Package management |
| `spec` | OpenSpec tooling |

### Dependency Tags (add as needed)

| Marker | Requires |
|--------|----------|
| `network` | Network access |
| `api` | API keys (OT_BRAVE_API_KEY, etc.) |
| `playwright` | Playwright browsers installed |
| `docker` | Docker daemon running |

## Example Test

```python
import pytest

@pytest.mark.smoke
@pytest.mark.serve
def test_server_starts():
    """Verify server can start without errors."""
    from ot_serve.server import create_server
    server = create_server()
    assert server is not None
```

## Running Tests

```bash
# All tests
uv run pytest

# Smoke tests only (fast CI)
uv run pytest -m smoke

# Specific component
uv run pytest -m serve

# Combine markers
uv run pytest -m "smoke and serve"

# Skip slow tests
uv run pytest -m "not slow"

# Skip tests requiring network
uv run pytest -m "not network"
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures (mock_http_get, mock_secrets, etc.)
├── smoke/                   # Quick sanity checks
├── unit/                    # Fast isolated tests (mocked dependencies)
│   ├── core/                # Core library tests
│   ├── bench/               # Benchmark harness tests
│   ├── serve/               # MCP server tests
│   ├── sdk/                 # SDK tests
│   └── tools/               # Tool unit tests
│       ├── test_brave_search.py
│       ├── test_package.py
│       └── ...
└── integration/             # End-to-end tests (real dependencies)
    └── tools/               # Tool integration tests
        ├── conftest.py      # Secrets loading for API tests
        ├── test_brave_search.py
        └── ...
```

Unit and integration tests mirror each other - same filenames, different directories. This requires `__init__.py` files in test directories to avoid module name collisions.

## Fixture Guidelines

### Good: Shared fixture in conftest.py

```python
# tests/conftest.py
@pytest.fixture
def temp_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("tools: [demo]")
    return config_file
```

### Bad: Duplicated setup in each test

```python
# Don't do this
def test_one():
    config_file = Path("/tmp/config.yaml")
    config_file.write_text("tools: [demo]")
    ...

def test_two():
    config_file = Path("/tmp/config.yaml")  # Duplicated!
    config_file.write_text("tools: [demo]")
    ...
```

## Global Fixtures

These fixtures are defined in `tests/conftest.py` and available to all tests:

| Fixture | Purpose | Example Usage |
|---------|---------|---------------|
| `executor` | Direct Python code execution | `executor("1 + 1")` returns `"2"` |
| `mock_http_get` | Mock `ot.http_client.http_get` | `mock_http_get.return_value = (True, {...})` |
| `mock_secrets` | Mock `ot_sdk.get_secret` | `mock_secrets.return_value = "test-key"` |
| `mock_subprocess` | Mock `subprocess.run` | `mock_subprocess.return_value = MagicMock(returncode=0)` |
| `mock_config` | Mock `ot.config.get_config` | `mock_config.return_value.tools.ripgrep.timeout = 30` |
| `mock_ot_sdk_config` | Mock `ot_sdk.get_config` | `mock_ot_sdk_config.return_value = "value"` |

### Integration Fixtures

The `tests/integration/tools/conftest.py` provides fixtures for live API tests:

- Forces reload of secrets from `secrets.yaml` for API key access
- Sets `OT_SECRETS_FILE` environment variable
- Loads secrets into `ot_sdk.config._current_secrets`

## Testing Patterns

### Pattern 1: Pure Function Tests (No Mocking)

```python
@pytest.mark.unit
@pytest.mark.tools
class TestCleanVersion:
    """Test _clean_version semver prefix stripping."""

    def test_strips_caret(self):
        assert _clean_version("^1.0.0") == "1.0.0"

    def test_strips_tilde(self):
        assert _clean_version("~1.0.0") == "1.0.0"
```

### Pattern 2: HTTP Tests with Mocking

```python
@pytest.mark.unit
@pytest.mark.tools
class TestNpm:
    """Test npm function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_fetches_single_package(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})
        result = npm(packages=["react"])
        assert "18.2.0" in result

    @patch("ot_tools.package._fetch")
    def test_handles_unknown_package(self, mock_fetch):
        mock_fetch.return_value = (False, "Not found")
        result = npm(packages=["nonexistent-package-xyz"])
        assert "unknown" in result
```

### Pattern 3: Smoke Tests (Import Verification)

```python
@pytest.mark.smoke
@pytest.mark.core
def test_config_imports() -> None:
    """Verify config module imports successfully."""
    from ot.config import OneToolConfig, get_config
    assert OneToolConfig is not None
    assert get_config is not None
```

### Pattern 4: Integration Tests with Live APIs

```python
@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestPackageLive:
    """Live integration tests for package version tool."""

    def test_npm_live(self):
        from ot_tools.package import npm
        result = npm(packages=["lodash"])
        assert "lodash" in result
        assert "unknown" not in result.lower()
```

## Writing New Tests

### Checklist

- [ ] Add speed marker (`smoke`, `unit`, `integration`, or `slow`)
- [ ] Add component marker (`tools`, `core`, `serve`, `bench`, `browse`, `pkg`, `spec`)
- [ ] Add dependency markers if needed (`network`, `api`, `playwright`, `docker`)
- [ ] Write descriptive docstring explaining what is tested
- [ ] Use class grouping for related tests
- [ ] Mock external dependencies in unit tests
- [ ] Use clear assertions with descriptive messages

### Test File Location

| Test Type | Directory | Example |
|-----------|-----------|---------|
| Smoke tests | `tests/smoke/` | `test_imports.py` |
| Unit tests | `tests/unit/{component}/` | `tests/unit/tools/test_package.py` |
| Integration tests | `tests/integration/{component}/` | `tests/integration/tools/test_package.py` |

Unit and integration tests mirror each other - same filenames, different directories.

## CI Integration

- **On push**: Run `pytest -m smoke` (~30s)
- **On PR**: Run `pytest -m "not slow"` (~2min)
- **Nightly**: Run full suite including slow tests
