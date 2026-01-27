# Tasks: Expand ot_sdk with Common Tool Utilities

## 1. Core SDK Modules

- [x] 1.1 Create `src/ot_sdk/packs.py` with `get_pack()` and `call_tool()`
- [x] 1.2 Create `src/ot_sdk/batch.py` with `batch_execute()` and `normalize_items()`
- [x] 1.3 Create `src/ot_sdk/request.py` with `safe_request()` and `api_headers()`
- [x] 1.4 Create `src/ot_sdk/factory.py` with `lazy_client()`
- [x] 1.5 Create `src/ot_sdk/deps.py` with `requires_cli()`, `requires_lib()`, `check_deps()`
- [x] 1.6 Update `src/ot_sdk/__init__.py` to export all new functions

## 2. CLI Integration

- [x] 2.1 Update `src/ot_serve/cli.py` to call `check_deps()` in `init validate`
- [x] 2.2 Add dependency status to validate output

## 3. Tool Refactoring

- [x] 3.1 Refactor `brave_search.py` to use `batch_execute()`, `normalize_items()`, `format_batch_results()`
- [x] 3.2 Refactor `web_fetch.py` to use `batch_execute()`, `normalize_items()`, `format_batch_results()`
- [x] 3.3 Refactor `firecrawl_tool.py` to use `lazy_client()`, `batch_execute()`, `normalize_items()`
- [x] 3.4 Refactor `context7.py` - evaluated, no major changes needed (already well-designed)
- [x] 3.5 Refactor `grounding_search.py` to use `batch_execute()`, `normalize_items()`, `format_batch_results()`
- [x] 3.6 Add `__ot_requires__` declarations to tools with CLI dependencies (ripgrep, grounding_search)

## 4. Testing

- [x] 4.1 Add unit tests for `batch.py` - batch_execute, normalize_items, format_batch_results
- [x] 4.2 Add unit tests for `factory.py` - lazy_client, LazyClient
- [x] 4.3 Add unit tests for `deps.py` - check_cli, check_lib, ensure_cli, ensure_lib
- [x] 4.4 Add export tests for all new SDK functions

## 5. Validation

- [x] 5.1 Run SDK unit tests (59 passed)
- [x] 5.2 Run existing tool tests to ensure no regressions (114 passed for refactored tools)
- [x] 5.3 Run affected tool tests after refactoring (all pass)
