# Testing

**Fast feedback. Lean tests. Two markers per test.**

Every test gets a speed tier and a component tag. CI runs smoke tests in 30 seconds.

---

## Principles

1. **Lean tests** - Write the minimum tests to verify behaviour works. Don't test implementation details.
2. **DRY fixtures** - Share setup code via `conftest.py`. Don't duplicate.
3. **Test behaviour** - Focus on inputs/outputs, not internal code paths.
4. **Fast feedback** - Smoke tests run in CI on every push. Slow tests run on merge.
5. **Isolation** - Mock HTTP/subprocess calls to avoid network I/O in unit tests.

---

## Running Tests

Always use `uv run pytest` (never bare `pytest`). Shortcuts via justfile:

```bash
just test              # all tests (strict - errors on missing requirements)
just test-lenient      # skip tests with missing requirements
just test-unit         # unit tests only
just test-integration  # integration tests only
just test-coverage     # with coverage report
```

**Direct pytest usage:**
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

---

## Required Markers

Every test must have **two markers** - a speed tier and a component:

### Speed Tier (pick one)

| Marker | Criteria | When to use |
|--------|----------|-------------|
| `smoke` | <1s, no I/O | Quick sanity checks that verify basic functionality |
| `unit` | <1s, no I/O | Fast isolated tests for pure logic |
| `integration` | May be slow | End-to-end tests with real dependencies |
| `slow` | >10s | Long-running tests (benchmarks, large data) |

### Component Tag (pick one)

| Marker | Component |
|--------|-----------|
| `core` | Core library (`ot`) - executor, config, registry |
| `serve` | MCP server (`onetool`) |
| `tools` | Tool implementations (`ottools`) |
| `pkg` | Package management |
| `spec` | OpenSpec tooling |

### Dependency Tags (add as needed)

| Marker | Requires |
|--------|----------|
| `network` | Network access |
| `api` | API keys (BRAVE_API_KEY, etc. in secrets.yaml) |
| `playwright` | Playwright browsers installed |
| `docker` | Docker daemon running |

**Tests missing required markers are skipped with a warning.**

---

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures (mock_http_get, mock_secrets, etc.)
├── smoke/                   # Quick sanity checks
├── unit/                    # Fast isolated tests (mocked dependencies)
│   ├── core/                # Core library tests
│   ├── serve/               # MCP server tests
│   └── tools/               # Tool unit tests
│       ├── test_package.py
│       └── ...
├── otutil/unit/tools/       # util extra tool unit tests
│   ├── test_brave.py
│   └── ...
├── otdev/unit/tools/        # dev extra tool unit tests
│   ├── test_context7.py
│   └── ...
└── integration/             # End-to-end tests (real dependencies)
    └── tools/               # Tool integration tests
        ├── conftest.py      # Secrets loading for API tests
        ├── test_brave.py
        └── ...
```

**Note:** Unit and integration tests mirror each other - same filenames, different directories. This requires `__init__.py` files in test directories to avoid module name collisions.

---

## Shared Fixtures

### Global Fixtures (from `tests/conftest.py`)

Available to all tests:

| Fixture | Purpose | Example Usage |
|---------|---------|---------------|
| `executor` | Direct Python code execution | `executor("1 + 1")` returns `"2"` |
| `mock_http_get` | Mock `ot.http_client.http_get` | `mock_http_get.return_value = (True, {...})` |
| `mock_secrets` | Mock `ot.config.secrets.get_secret` | `mock_secrets.return_value = "test-key"` |
| `mock_subprocess` | Mock `subprocess.run` | `mock_subprocess.return_value = MagicMock(returncode=0)` |
| `mock_config` | Mock `ot.config.get_config` | `mock_config.return_value.tools.ripgrep.timeout = 30` |
| `reset_config_cache` | Auto-resets config (per-test) | Auto-applied fixture |

### Integration Fixtures (from `tests/integration/tools/conftest.py`)

- Forces reload of secrets from `secrets.yaml` for API key access
- Sets `OT_SECRETS_FILE` environment variable

---

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

    @patch("ottools.package._fetch")
    def test_fetches_single_package(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})
        result = npm(packages=["react"])
        assert "18.2.0" in result

    @patch("ottools.package._fetch")
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
        from ottools.package import npm
        result = npm(packages=["lodash"])
        assert "lodash" in result
        assert "unknown" not in result.lower()
```

### Pattern 5: Requiring External Resources

```python
@pytest.mark.integration
@pytest.mark.tools
def test_brave_live(request):
    require(
        get_secret("BRAVE_API_KEY") is not None,
        "BRAVE_API_KEY not configured",
        request,
    )
    result = search(query="test")
    assert "web" in result
```

---

## Integration Test Guidelines

### What integration tests are for

Unit tests own logic and edge cases. Integration tests verify the tool works with real
dependencies end-to-end. They are not a second pass of unit tests.

**Write integration tests to answer:** "Does this tool work at all against real I/O?"
**Do not write integration tests to answer:** "Does this function handle every edge case?"

Aim for 3–5 tests per tool: one happy path, one lifecycle check (create/delete). No more.

### Prerequisites — all deps must be installed

Integration tests require their full environment to be present. A missing dependency
is a **failure**, not a skip. This keeps CI honest: a red test means "fix your
environment", not "silently skipped".

- **API keys** — configure them in `secrets.yaml` before running integration tests
- **Libraries** — install the relevant extras (`pip install onetool-mcp[dev,util]`)
- **CLIs** — install binaries like `rg` (ripgrep) before running tests that need them

Use `pytest.fail()` (never `pytest.skip()`) when a dependency is absent:

```python
@pytest.fixture(autouse=True)
def require_api_key(self):
    if not get_test_secret("BRAVE_API_KEY"):
        pytest.fail("BRAVE_API_KEY not configured")

@pytest.fixture(autouse=True)
def require_binary(self):
    if shutil.which("rg") is None:
        pytest.fail("ripgrep (rg) not installed")
```

### Three dependency tiers

Tools fall into one of three tiers. The tier determines markers and check strategy.

**Tier 1 — No external deps** (stdlib, local files, local SQLite)

No check needed. Use `tmp_path` for file I/O. Clean up created state in `finally`.

```python
@pytest.mark.integration
@pytest.mark.tools
class TestCtxWriteRead:
    def test_write_and_read(self) -> None:
        from otutil.tools.ctx import delete, read, write

        result = write("alpha\nbeta\ngamma")
        handle = result["handle"]
        try:
            read_result = read(handle)
            assert any("alpha" in ln for ln in read_result["lines"])
        finally:
            delete(handle)
```

**Tier 2 — Binary or library dep**

Fail early using `shutil.which()` or a try/except import in an `autouse` fixture.

```python
@pytest.mark.integration
@pytest.mark.tools
class TestRipgrepLive:
    @pytest.fixture(autouse=True)
    def require_rg(self):
        if shutil.which("rg") is None:
            pytest.fail("ripgrep (rg) not installed")

    def test_search_live(self, tmp_path):
        ...
```

**Tier 3 — API key required**

Add `@pytest.mark.network @pytest.mark.api`. Fail via `autouse` fixture that checks
`get_test_secret()` from the conftest.

```python
@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestBraveSearchLive:
    @pytest.fixture(autouse=True)
    def require_api_key(self):
        if not get_test_secret("BRAVE_API_KEY"):
            pytest.fail("BRAVE_API_KEY not configured")

    def test_search_live(self):
        ...
```

### Isolation — never pollute real `.onetool/` state

Integration tests must not read from or write to the real `.onetool/` directory.

- **File-based tools:** always pass `tmp_path` — never hardcode paths under `.onetool/`
- **Store-backed tools** (image, ctx): patch the storage path or clean up in `finally`
- **Image store:** patch `_images_dir` on the store module

```python
from ottools._image import store

with patch.object(store, "_images_dir", return_value=tmp_path):
    result = load(img=str(img_path))
```

- **Ctx store:** don't patch (real pool); delete test handles in `finally`

### Assertions — structural, not exact

Check that the response has the right shape. Don't assert on exact strings returned by
real APIs or real file contents beyond what you wrote yourself.

```python
# Good — checks structure
assert "handle" in result
assert result["handle"].startswith("#img_")

# Good — checks content you wrote
assert any("alpha" in ln for ln in read_result["lines"])

# Bad — brittle against real API variation
assert result == "A red square on a white background."
```

### Disabling broken tests

Use `pytest.skip(..., allow_module_level=True)` to disable an entire file. Do **not**
use `pytestmark = [..., pytest.mark.skip(...)]` — that form doesn't prevent `autouse`
fixtures from running before the skip is evaluated.

```python
# Correct — skips at collection time, before any fixtures run
import pytest
pytest.skip("disabled: tests broken", allow_module_level=True)

# Wrong — fixtures run first, causing errors before skip takes effect
pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="disabled")]
```

---

## Writing New Tests

### Checklist

- [ ] Add speed marker (`smoke`, `unit`, `integration`, or `slow`)
- [ ] Add component marker (`tools`, `core`, `bench`, `serve`, `pkg`, `spec`)
- [ ] Add dependency markers if needed (`network`, `api`, `playwright`, `docker`)
- [ ] Write descriptive docstring explaining what is tested
- [ ] Use class grouping for related tests
- [ ] Mock external dependencies in unit tests
- [ ] For integration tests: identify the dependency tier and apply the correct skip pattern
- [ ] For integration tests: verify isolation — no writes to real `.onetool/`
- [ ] Use clear assertions with descriptive messages

### Test File Location

| Test Type | Directory | Example |
|-----------|-----------|---------|
| Smoke tests | `tests/smoke/` | `test_imports.py` |
| Unit tests | `tests/unit/{component}/` | `tests/unit/tools/test_package.py` |
| Integration tests | `tests/integration/{component}/` | `tests/integration/tools/test_package.py` |

---

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

---

## Config Isolation

Tests use `tests/.onetool/config/onetool.yaml` with `inherit: none` to ensure isolation from user configs.

---

## Test URLs

Do not use `example.com` - use `https://www.wikipedia.org/` instead for test URLs.

---

## CI Integration

- **On push**: Run `pytest -m smoke` (~30s)
- **On PR**: Run `pytest -m "not slow"` (~2min)
- **Nightly**: Run full suite including slow tests

---

**Related:**
- Test configuration: `pyproject.toml` → `[tool.pytest.ini_options]`
- Shared fixtures: `tests/conftest.py`
- Integration fixtures: `tests/integration/tools/conftest.py`
