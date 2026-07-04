## 1. kb/knowledge: rename `q` → `query` (`kb.search`, `kb.ask`)

- [x] 1.1 In `src/otutil/tools/_knowledge/retrieval.py`, rename the `q` parameter to `query` in `search()` (signature currently at line 50) and update every reference inside the function body: the `Args:` docstring line (62), both `Example:` docstring lines (75-76), the `LogSpan(span="kb.search", q=q, ...)` keyword (84), the three `search_hybrid`/`search_vec`/`search_fts` call sites that pass `q` positionally (89, 91, 93), and the two f-strings referencing `{q}` (108, 111).
- [x] 1.2 In the same file, rename the `q` parameter to `query` in `ask()` (signature currently at line 135) and update: the `Args:` docstring line (146), the `Example:` docstring line (156), the `LogSpan(span="kb.ask", q=q, ...)` keyword (158), the two retrieval call sites passing `q` positionally (164, 166), the f-string at 170 (`"No relevant entries found for: {q}"`), and the `_synthesise(q, context)` call (190).
- [x] 1.3 Do NOT modify `related()` (parameter is `topic`, unrelated to this rename) or the private `search_hybrid`/`search_vec`/`search_fts` functions in `src/otutil/tools/_knowledge/search.py` (their own internal parameter names are unaffected).
- [x] 1.4 Update `docs/reference/tools/knowledge.md`: function table rows (lines 21-22: `knowledge.search(q, db, ...)` → `knowledge.search(query, db, ...)`, `knowledge.ask(q, db, ...)` → `knowledge.ask(query, db, ...)`), Key Parameters table row (line 36: `q` → `query`), and the three example lines (107, 110, 113: `q='...'` → `query='...'`).
- [x] 1.5 Do NOT modify `docs/learn/whats-new-v2.md:94-95` — it documents the v2-era API surface as historical changelog content and must remain accurate to what shipped in v2.
- [x] 1.6 Update `tests/otutil/unit/tools/test_knowledge.py:1231` — `search(q="test", db="test", mode="invalid")` → `search(query="test", db="test", mode="invalid")`.
- [x] 1.7 Run `just docs-sync` (regenerates `docs/reference/tools/tool-index.md` from live signatures) — do not hand-edit `tool-index.md`.

## 2. mem: rename mode value `"pattern"` → `"keyword"`

- [x] 2.1 In `src/otutil/tools/_mem/search.py`, update the `mode:` docstring line (149) and the `Example:` line (161) referencing `mode="pattern"`.
- [x] 2.2 Update the mode validation tuple (171): `if mode not in ("semantic", "pattern", "hybrid")` → `("semantic", "keyword", "hybrid")`.
- [x] 2.3 Update the error message (172): `"...Must be 'semantic', 'pattern', or 'hybrid'"` → `"...Must be 'semantic', 'keyword', or 'hybrid'"`.
- [x] 2.4 Update the dispatch branch (190): `elif mode == "pattern":` → `elif mode == "keyword":`.
- [x] 2.5 Rename the private helper `_search_pattern()` (defined at 254) to `_search_keyword()`, and update its two call sites: the dispatch call (191) and the call inside `_search_hybrid()` (316). Update the `__all__` entry (367) from `"_search_pattern"` to `"_search_keyword"`.
- [x] 2.6 Do NOT modify `mem.grep(pattern=...)` — that `pattern` parameter (the regex/literal search string) is an unrelated concept to the search `mode` value. Do NOT modify `glob_pattern`, `redaction_patterns`, or `exclude_file_patterns` elsewhere in the mem pack — unrelated.
- [x] 2.7 Update `docs/reference/tools/mem.md`: Highlights bullet (line 8: "Semantic, pattern, and hybrid" → "Semantic, keyword, and hybrid"), `mem.search()` parameter table row (line 99: `"semantic" (default), "pattern", or "hybrid"` → `"semantic" (default), "keyword", or "hybrid"`), the example at line 302 (`mode="pattern"` → `mode="keyword"`, and update the comment above it from "# Pattern search with topic filter" to "# Keyword search with topic filter"), and the Embedding Large Content paragraph (line 403: `pattern search (`mode="pattern"`)` → `keyword search (`mode="keyword"`)`). Leave line 432's "pattern search" prose as a generic description if it does not name the literal mode value, otherwise update it to "keyword search" for consistency.
- [x] 2.8 Update `tests/otutil/unit/tools/test_mem.py:580` and `:717` — `mode="pattern"` → `mode="keyword"` (the enclosing test methods are currently named `test_pattern_search` / similar; renaming the test method name to reflect `test_keyword_search` is optional polish, not required).
- [x] 2.9 Update `tests/integration/tools/test_mem.py:105` — `mode="pattern"` → `mode="keyword"`.
- [x] 2.10 Run `rg -n 'mode\s*=\s*"pattern"|mode\s*=\s*.pattern.' src/otutil/tools/_mem/ tests/ docs/reference/tools/mem.md` and confirm the only remaining hits (if any) are unrelated identifiers, not the mem search mode.

## 3. brave: rename `count` → `max_results` pack-wide (all functions)

Scope note: pack-wide is deliberate (report intent: "unify result-count param across search
packs … `max=` then works everywhere via prefix"); a search-only rename would leave brave
internally inconsistent. Defaults are unchanged (10 for single searches, 2 per query for
`search_batch`).

- [x] 3.1 In `src/otutil/tools/brave.py`, rename the shared `_validate_count()` helper (around
  line 399-403) to `_validate_max_results()` with the same 1-20 range, message shape mirroring
  `src/otutil/tools/tavily.py:418-422`'s `_validate_max_results`:
  ```python
  def _validate_max_results(max_results: int) -> str | None:
      """Validate max_results is in range 1-20. Returns error string or None if valid."""
      if 1 <= max_results <= 20:
          return None
      return f"Error: max_results must be between 1 and 20 (got {max_results})"
  ```
- [x] 3.2 Rename the `count` parameter to `max_results` in ALL five function signatures:
  `search()` (`count: int = 10`, line 467-478), `news()`, `image()`, `video()` (each
  `count: int = 10`), and `search_batch()` (`count: int = 2`). Keep each default.
- [x] 3.3 Update every function's `Args:` docstring line (`count: Number of results...` →
  `max_results: ...`) and every `Example:` docstring line using `count=` (e.g. line 506:
  `brave.search(query="AI news", freshness="pw", count=5)` → `max_results=5`).
- [x] 3.4 In each function body, replace `_validate_count(count)` calls with
  `_validate_max_results(max_results)`, and in each outgoing request-params dict replace
  `"count": count,` with `"count": max_results,` (the Brave API's own query-string field name
  stays `"count"` — only the Python variable feeding it changes). In `search_batch()`, update the
  per-query forwarding kwarg into `search()` (`count=count` → `max_results=max_results`).
- [x] 3.5 Leave internal log/stats field names unchanged (e.g. a `count` key in LogEntry/stats
  payloads is not part of the tool contract); do not rename unrelated locals like loop counters.
- [x] 3.6 Update `src/ottools/ot_llm.py` docstring examples at lines 7, 119, and 125 — each is `brave.search(query="...", count=N)`; change to `max_results=N`. These break under the rename regardless of whether item 6 (optional) is implemented.
- [x] 3.7 Update `docs/reference/tools/brave.md`: Key Parameters table (one `count` row at line 29) — rename the row to `max_results`, noting it applies to all functions (default 10; 2 per query for `search_batch`). Update the example at line 66: `brave.search(query="python async tutorial", count=10)` → `max_results=10`, and any `count=` examples for news/image/video/search_batch.
- [x] 3.8 Update `docs/learn/explicit-calls.md:113` — `brave.search(query='latest AI news', count=5)` → `max_results=5`.
- [x] 3.9 Update `tests/explore/sanity.md:387` — `brave.search(query="test", count=2)` → `max_results=2` (manual exploratory-test doc, not part of the automated pytest suite, but keep it accurate).
- [x] 3.10 Update `tests/otutil/unit/tools/test_brave.py`: in `class TestSearch` (starts at line 495), `test_rejects_count_too_high` (536: `count=21` → `max_results=21`), `test_rejects_count_zero` (540: `count=0` → `max_results=0`), `test_rejects_count_negative` (544: `count=-1` → `max_results=-1`), and the three `assert "count" in result` lines (537, 541, 545) → `assert "max_results" in result`. Rename `TestValidateCount` (class at line 154) to `TestValidateMaxResults` and point it at the renamed `_validate_max_results` helper. Update `test_rejects_invalid_count` at line 794 (`search_batch`) to `max_results=` and the new error text. Then sweep the whole file for any remaining `count=` call sites on brave functions (`rg -n 'count=' tests/otutil/unit/tools/test_brave.py`) and update them.
- [x] 3.11 Update `tests/integration/tools/test_brave.py:30` — `search(query="python programming", count=3)` → `max_results=3` — and sweep that file for other brave `count=` call sites.
- [x] 3.12 Run `rg -n 'brave\.(search|news|image|video|search_batch)\w*\([^)]*count=' src/ docs/ tests/` and confirm zero remaining matches (any match is a missed call site; `docs/learn/whats-new-v2.md` is the one allowed historical exception per design Non-Goals).

## 4. db: add `read_only` guard to `db.query()`

- [x] 4.1 In `src/otdev/tools/db.py`, add a module-level helper near `query()` (it can go directly above `query()`, currently defined starting at line 408):
  ```python
  _READ_ONLY_KEYWORDS = ("SELECT", "EXPLAIN", "PRAGMA")


  def _is_read_only_sql(sql: str) -> bool:
      """Return True if sql's first keyword is SELECT, EXPLAIN, or PRAGMA."""
      stripped = sql.strip()
      if not stripped:
          return False
      first_word = stripped.split(None, 1)[0].upper()
      return first_word in _READ_ONLY_KEYWORDS
  ```
- [x] 4.2 Add `read_only: bool = False` to `query()`'s signature (currently `def query(*, sql: str, db_url: str, params: dict[str, Any] | None = None) -> ...`).
- [x] 4.3 Add a docstring `Args:` line: `read_only: If True, reject any statement whose first keyword is not SELECT, EXPLAIN, or PRAGMA (default: False)`.
- [x] 4.4 In the function body, immediately after the existing `db_url`/`sql` emptiness checks (currently lines 442-448) and before the `try:` block that opens the engine connection, add:
  ```python
          if read_only and not _is_read_only_sql(sql):
              s.add(error="read_only_violation")
              return "Error: read_only=True but statement is not SELECT/EXPLAIN/PRAGMA"
  ```
- [x] 4.5 Update `docs/reference/tools/db.md` Key Parameters table (currently ends at line 32): add a row `| \`read_only\` | bool | Reject non-SELECT/EXPLAIN/PRAGMA statements when True (query only, default: False) |`. Do NOT touch line 112's "Queries are read-only by default" claim — that fix belongs to `p18-docs-debt-sweep`.
- [x] 4.6 Add tests to `tests/integration/tools/test_db.py`, `class TestQuery` (starts at line 172, uses the module's `@pytest.mark.integration` marker and the real in-memory-SQLite `db_url` fixture):
  - `test_read_only_rejects_insert`: `db.query(sql="INSERT INTO users (name, active) VALUES ('X', 1)", db_url=db_url, read_only=True)` returns a string starting with `"Error:"` and containing "SELECT/EXPLAIN/PRAGMA"; follow up with a `SELECT COUNT(*)` (without `read_only`) to assert the row was NOT inserted.
  - `test_read_only_allows_select`: `db.query(sql="SELECT * FROM users", db_url=db_url, read_only=True)` returns the same shape as the existing `test_select_all_rows` (a dict with `row_count`).
  - `test_read_only_allows_pragma`: `db.query(sql="PRAGMA table_info(users)", db_url=db_url, read_only=True)` does not error.
  - `test_read_only_defaults_to_false`: `db.query(sql="SELECT 1", db_url=db_url)` (no `read_only` arg) behaves exactly as before this change.
- [x] 4.7 Run `rg -n "read_only" src/otdev/tools/db.py docs/reference/tools/db.md tests/integration/tools/test_db.py` to confirm the guard, its doc row, and its tests are all present.

## 5. excalidraw: add `excalidraw` as a second pack alias

- [x] 5.1 In `src/otdev/tools/excalidraw.py:20`, change `pack_aliases = ("wb",)` to `pack_aliases = ("wb", "excalidraw")`.
- [x] 5.2 Confirm no code change is needed in `src/ot/executor/tool_loader.py` (alias collection, lines 319-322) or `src/ot/executor/pack_proxy.py` (alias injection, lines 316-320) — both already support N aliases per pack via the same loop; this is a pure metadata addition.
- [x] 5.3 In `tests/unit/core/test_pack_proxy.py`, `class TestPackShortNameAliases`: update `mock_registry.pack_aliases["whiteboard"]` from `("wb",)` to `("wb", "excalidraw")` in both places it is set (the `_build_namespace_with_packs` helper, currently line 232, and the `aliases` dict inside `test_all_metadata_aliases_are_valid_identifiers`, currently line 288).
- [x] 5.4 In the same class, add a new test method (mirroring `test_whiteboard_gets_wb_short_alias`):
  ```python
  def test_whiteboard_gets_excalidraw_alias(self) -> None:
      """whiteboard pack should appear as both 'whiteboard' and 'excalidraw'."""
      packs = {"whiteboard": {"draw": MagicMock(), "open": MagicMock()}}
      ns = self._build_namespace_with_packs(packs)

      assert "excalidraw" in ns
      assert ns["excalidraw"] is ns["whiteboard"]
  ```
- [x] 5.5 Update `tests/unit/tools/test_excalidraw.py`'s module docstring (line 1: "short alias: wb" → "short aliases: wb, excalidraw") for accuracy — cosmetic, but keep the file's self-description true.
- [x] 5.6 Verify (by inspection — no code edit needed) that each of the following 14 docstring example lines in `src/otdev/tools/excalidraw.py` now resolves given the new alias: `:1491` (`excalidraw.save(...)`), `:1543` (`excalidraw.load(...)`), `:1615` (`excalidraw.sync()`), `:1650` (`excalidraw.help()`), `:1696` (`excalidraw.style(...)`), `:1786` (`excalidraw.share()`), `:1880` (`excalidraw.clear()`), `:1906` (`excalidraw.scroll(...)`), `:1928` (`excalidraw.zoom(...)`), `:1953` (`excalidraw.fit()`), `:2466` (`excalidraw.screenshot()`), `:2499` (`excalidraw.hard_reset()`), `:2555` (`excalidraw.open()`), `:2581` (`excalidraw.close()`). Re-run `rg -n "excalidraw\." src/otdev/tools/excalidraw.py` and confirm the line count/positions match (allowing for line-number drift from earlier edits in this change) and that `pack_aliases` on line 20 includes `"excalidraw"`.
- [x] 5.7 Run `just docs-sync` and confirm `docs/reference/tools/tool-index.md`'s whiteboard section heading changes from `## whiteboard, wb` to `## whiteboard, wb, excalidraw`.

## 6. (Optional) ot_llm: stop string-sniffing "Error:" in transform_file

- [ ] 6.1 In `src/ottools/ot_llm.py`, extract `transform()`'s current body (validation + API call, everything after the docstring, currently starting around line 142) into a new private function `_transform_core(*, data: Any, prompt: str, model: str | None, json_mode: bool) -> tuple[bool, str]` that returns `(False, "Error: ...")` on every current failure path and `(True, content)` on success, never raising.
- [ ] 6.2 Rewrite `transform()` as a thin wrapper: `_ok, result = _transform_core(...); return result`. Keep `transform()`'s docstring, signature, and `LogSpan` call unchanged — its external string-based contract (documented in the unmodified "Error Handling" requirement in `openspec/specs/ottools/tool-llm/spec.md`) must not change.
- [ ] 6.3 In `transform_file()` (currently starting at line 243), replace the call to `transform(...)` at line 321 and the `if result.startswith("Error:"):` check at line 329 with a direct call to `_transform_core(...)`, branching on the returned boolean instead of string-sniffing.
- [ ] 6.4 Do NOT implement a batch-transform function. The report's phrase "batch `transform` parity" does not correspond to any existing function in `src/ottools/ot_llm.py` (confirmed via `grep -n "^def " src/ottools/ot_llm.py` — only `transform` and `transform_file` exist). This is documented anchor drift in `design.md`'s Open Questions; do not invent new functionality to satisfy it.
- [ ] 6.5 Add a unit test in `tests/ottools/unit/tools/test_llm.py` covering the false-positive case: mock the underlying LLM call to return content that literally starts with `"Error:"` (e.g. `"Error: check the logs for details"` as *legitimate* transformed output, not a real failure) and assert `transform_file()` writes it to the output file and returns the `"OK: Transformed ..."` success string, not a failure.
- [x] 6.6 If this optional item is skipped due to capacity, delete `openspec/changes/p17-pack-api-consistency/specs/ottools/tool-llm/spec.md` before archiving this change — do not leave a spec delta describing behavior that was not implemented.

## 7. Verification

- [x] 7.1 `rg -n 'kb\.search\(q=|kb\.ask\(q=|knowledge\.search\(q=|knowledge\.ask\(q=' src/ docs/reference tests/` returns empty (excluding `docs/learn/whats-new-v2.md`, which is intentionally excluded — verify separately that this file is untouched via `git diff --stat docs/learn/whats-new-v2.md` showing no changes).
- [x] 7.2 `uv run python -c "from otutil.tools._knowledge.retrieval import search, ask; import inspect; print(inspect.signature(search)); print(inspect.signature(ask))"` shows `query` (not `q`) in both signatures.
- [x] 7.3 Manually confirm (via the `run` tool or a direct pytest against the retrieval functions with a test DB) that both `kb.search(query=...)` and `kb.search(q=...)` succeed identically — the latter proves prefix matching still provides the short form.
- [x] 7.4 `rg -n 'mode\s*=\s*"pattern"' src/otutil/tools/_mem/ docs/reference/tools/mem.md tests/otutil/unit/tools/test_mem.py tests/integration/tools/test_mem.py` returns empty.
- [x] 7.5 Manually confirm `mem.search(query="test", mode="keyword")` succeeds and `mem.search(query="test", mode="pattern")` returns an `"Error: Invalid mode 'pattern'..."` string.
- [x] 7.6 `rg -n 'brave\.(search|news|image|video|search_batch)\w*\([^)]*count=' src/ docs/ tests/` returns empty (whats-new-v2.md is the one allowed historical exception).
- [x] 7.7 Manually confirm `brave.search(query="test", max_results=5)` and `brave.search(query="test", max=5)` both succeed (the latter proves the `max=` prefix match), and that `brave.search(query="test", count=5)` and `brave.news(query="test", count=5)` both raise keyword-argument errors (pack-wide rename).
- [x] 7.8 `uv run pytest tests/integration/tools/test_db.py -m integration -k "read_only" -v` passes, including the case asserting an `INSERT` is rejected under `read_only=True` and not applied to the database.
- [x] 7.9 `uv run pytest tests/unit/core/test_pack_proxy.py -m unit -k "excalidraw" -v` passes.
- [x] 7.10 `rg -n 'pack_aliases' src/otdev/tools/excalidraw.py` shows `("wb", "excalidraw")`.
- [x] 7.11 `rg -n "excalidraw\." src/otdev/tools/excalidraw.py` — every match is inside a docstring example (14 expected, per task 5.6) and, given the new alias, each one is now a call that would actually resolve at runtime.
- [x] 7.12 (If item 6 was implemented) `uv run pytest tests/ottools/unit/tools/test_llm.py -m unit -v` passes, including the new false-positive-detection test.
- [x] 7.13 `just docs-sync` runs clean (regenerates `tool-index.md`, then validates counts against the runtime registry via `check_docs_registry.py`) with no manual edits needed to its output beyond what task 1.7/5.7 already produced.
- [x] 7.14 `just check` (lint + type + test) passes with zero errors.
