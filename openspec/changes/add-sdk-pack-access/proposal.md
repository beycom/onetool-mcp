# Change: Expand ot_sdk with Common Tool Utilities

## Why

Tool development requires significant boilerplate for common patterns:

1. **Inter-tool communication** - Calling other packs requires 10+ lines of registry access
2. **Batch processing** - Every batch tool repeats 30-40 lines of ThreadPoolExecutor code
3. **HTTP error handling** - 20-30 lines of try/except with status extraction
4. **Lazy client init** - 25 lines of thread-safe singleton pattern
5. **API headers** - 10-15 lines to get secret and build headers
6. **Dependency validation** - No standard way to declare/check CLI or library dependencies

## What Changes

### New SDK Modules

| Module | Functions | Purpose |
|--------|-----------|---------|
| `packs.py` | `get_pack()`, `call_tool()` | Inter-tool communication |
| `batch.py` | `batch_execute()`, `normalize_items()` | Concurrent processing |
| `request.py` | `safe_request()`, `api_headers()` | HTTP utilities |
| `factory.py` | `lazy_client()` | Thread-safe lazy init |
| `deps.py` | `requires_cli()`, `requires_lib()`, `check_deps()` | Dependency validation |

### Tool Refactoring

Migrate existing tools to use new SDK functions:
- `brave_search.py` - Use `batch_execute()`, `safe_request()`, `api_headers()`
- `web_fetch.py` - Use `batch_execute()`, `normalize_items()`
- `firecrawl_tool.py` - Use `lazy_client()`
- `context7.py` - Use `safe_request()`, `api_headers()`
- `grounding_search.py` - Use `batch_execute()`, `api_headers()`

### CLI Integration

- `ot-serve init validate` calls `check_deps()` to verify tool dependencies
- Tools declare dependencies via module-level `__ot_requires__` or decorator

## Impact

- Affected specs: `tool-sdk`, `onetool-cli`
- Affected code:
  - `src/ot_sdk/` - 5 new modules (~200 lines total)
  - `src/ot_sdk/__init__.py` - export new functions
  - `src/ot_tools/*.py` - refactor 5+ tools
  - `src/ot_serve/cli.py` - add dependency check to validate

## Estimated Savings

~350-450 lines removed from tools after refactoring.
