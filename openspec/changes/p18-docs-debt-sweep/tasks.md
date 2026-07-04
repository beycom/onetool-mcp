## 1. db.md / db.query docs accuracy

- [x] 1.1 In `docs/reference/tools/db.md`, replace the "Security" section
  (currently at line ~110-114):
  ```
  ## Security

  - Queries are read-only by default
  - Use parameterized queries for user input
  - Configure `max_chars` to prevent excessive output
  ```
  First run `grep -n "read_only" src/otdev/tools/db.py`.
  - If it returns **no match** (the `read_only` guard from p17 has not
    landed yet), replace with:
    ```
    ## Security

    - Queries run under AUTOCOMMIT with no read-only restriction by default — any valid SQL (SELECT, INSERT, UPDATE, DELETE, DDL) executes
    - Use parameterized queries for user input
    - Configure `max_chars` to prevent excessive output
    ```
  - If it returns a **match** (p17's `read_only=True` guard already exists),
    replace with:
    ```
    ## Security

    - Queries run under AUTOCOMMIT with no read-only restriction by default — any valid SQL (SELECT, INSERT, UPDATE, DELETE, DDL) executes
    - Pass `read_only=True` to reject non-SELECT/EXPLAIN/PRAGMA statements
    - Use parameterized queries for user input
    - Configure `max_chars` to prevent excessive output
    ```
- [x] 1.2 In `src/otdev/tools/db.py`, in `query()`'s docstring (around line
  420), change:
  ```
      Returns:
          List of dicts for SELECT, success dict for INSERT/UPDATE/DELETE, or error string
  ```
  to:
  ```
      Returns:
          Dict with rows/row_count/truncated for SELECT, success dict for INSERT/UPDATE/DELETE, or error string
  ```
  (matches the actual return at `db.py:472-476`: `{"rows": ..., "row_count": ..., "truncated": ...}`).

## 2. package.md docs accuracy

- [x] 2.1 In `docs/reference/tools/package.md`, in the Functions table
  (line ~18), change:
  ```
  | `package.audit(packages, registry)` | Security audit for npm or PyPI packages |
  ```
  to:
  ```
  | `package.audit(path, registry)` | Version-staleness audit for npm or PyPI packages against a manifest file (no CVE/vulnerability lookup) |
  ```
  This matches the real signature `audit(*, path: str = ".", registry: str | None = None)` at `src/otdev/tools/package.py:224-227`.
- [x] 2.2 In the same file's "Key Parameters" table, add a row for `path`
  (it is currently undocumented):
  ```
  | `path` | str | Project directory to audit for `package.audit()` (default: `"."`) |
  ```

## 3. webfetch.py docstring examples

- [x] 3.1 In `src/otdev/tools/webfetch.py`, `fetch()`'s docstring
  (`Example:` block, lines 207-217), `fetch()` is keyword-only
  (`def fetch(*, url: str, ...)` at line 158-160). Fix each example line
  that passes `url` positionally:
  - Line 208: `content = webfetch.fetch("https://docs.python.org/3/library/asyncio.html")` → `content = webfetch.fetch(url="https://docs.python.org/3/library/asyncio.html")`
  - Line 211: `content = webfetch.fetch(url, output_format="text", fast=True)` → `content = webfetch.fetch(url=url, output_format="text", fast=True)`
  - Line 214: `content = webfetch.fetch(url, include_links=True)` → `content = webfetch.fetch(url=url, include_links=True)`
  - Line 217: `content = webfetch.fetch(url, output_format="json", include_metadata=True)` → `content = webfetch.fetch(url=url, output_format="json", include_metadata=True)`
- [x] 3.2 In the same file, `fetch_batch()`'s docstring (`Example:` block,
  lines 393-403), `fetch_batch()` is keyword-only
  (`def fetch_batch(*, urls: ..., ...)` at line 347-349). Fix both example
  calls that pass the URL list positionally:
  - Line 394: `content = webfetch.fetch_batch([` → `content = webfetch.fetch_batch(urls=[`
  - Line 400: `content = webfetch.fetch_batch([` → `content = webfetch.fetch_batch(urls=[`

## 4. doc_slug 404 fixes

- [x] 4.1 In `src/otdev/tools/db.py` (line 27), change
  `doc_slug = "database"` to `doc_slug = "db"`. The published page is
  `docs/reference/tools/db.md`, listed in `mkdocs.yml` nav (line ~65) as
  `DB: reference/tools/db.md` — the slug must equal `db` for
  `https://onetool.beycom.online/reference/tools/db/` to resolve.
- [x] 4.2 In `src/otdev/tools/webfetch.py` (line 14), change
  `doc_slug = "web-fetch"` to `doc_slug = "webfetch"`. The published page
  is `docs/reference/tools/webfetch.md`, listed in `mkdocs.yml` nav
  (line ~191) as `Webfetch: reference/tools/webfetch.md`.

## 5. whiteboard draw() docstring self-contradiction

- [x] 5.1 In `src/otdev/tools/excalidraw.py`, `draw()`'s docstring (line
  987), change:
  ```
          id["Label"]                           rectangle (only supported shape)
  ```
  to:
  ```
          id["Label"]                           rectangle (default; override with shape: prop, see below)
  ```
  This removes the contradiction with the same docstring's `shape` inline
  style prop at line 995 and `style()`'s `shape` value table at line 1677
  (`r`=rect, `d`=diamond, `c`=circle) — rectangle is only the DSL-literal
  creation default, not the only renderable shape. Do not touch line 797
  (`parse_dsl()`'s docstring) — that claim is accurate for what
  `parse_dsl()` itself does (literal ellipse/diamond bracket syntax really
  is unsupported and raises `ValueError` — see `excalidraw.py:710-723`); it
  is not part of this fix. Do not touch `pack_aliases` anywhere in this
  file — that is p17's change.

## 6. Surface undersold capabilities in doc Highlights

- [x] 6.1 In `docs/reference/tools/ot_core.md`'s Highlights section (after
  the existing "Unified `ot.help()` entry point..." bullet), add:
  ```
  - `ot.help(ask="...")` answers a natural-language question using only the deterministic help text narrowed by `query`
  ```
- [x] 6.2 In `docs/reference/tools/ot_context.md`'s Highlights section
  (after the existing bullets, before "Pure stdlib..."), add:
  ```
  - `ctx.ask()` sends one or more questions about stored content to an LLM in a single batched call
  ```

## 7. Fix: ground.py ImportError escapes the error formatter (code + test)

- [x] 7.1 In `src/otutil/tools/ground.py`, `_grounded_search()` (starts at
  line 358). Currently:
  ```python
      _require_google_genai()
      from google.genai import types

      with LogSpan(span=span_name, **log_extras) as s:
          try:
              cfg: Config | None = None
  ```
  Move the two lines (`_require_google_genai()` and
  `from google.genai import types`) to be the first two statements inside
  the `try:` block, so an `ImportError` is caught by the existing
  `except Exception as e: return _format_error(e)` at the end of the
  function instead of propagating uncaught:
  ```python
      with LogSpan(span=span_name, **log_extras) as s:
          try:
              _require_google_genai()
              from google.genai import types

              cfg: Config | None = None
  ```
  No other lines in the function change.
- [x] 7.2 Add a new test to
  `tests/otutil/unit/tools/test_ground.py`'s `TestGroundedSearch` class,
  modeled on the existing `test_handles_api_error` test in the same class:
  ```python
      @patch("otutil.tools.ground._require_google_genai")
      def test_missing_google_genai_returns_formatted_error(self, mock_require):
          from otutil.tools.ground import _grounded_search

          mock_require.side_effect = ImportError(
              "google-genai is required for grounding_search. "
              "Install with: pip install onetool-mcp[util]"
          )

          result = _grounded_search("test", span_name="test.span")

          assert isinstance(result, str)
          assert "google-genai" in result
          assert "pip install onetool-mcp[util]" in result
  ```
  Run `uv run pytest tests/otutil/unit/tools/test_ground.py -m "unit and tools" -v` and confirm the new test passes and no existing test in the file regresses.

## 8. Fix: kb.search() surfaces raw errors instead of guidance (code + test)

- [x] 8.1 In `src/otutil/tools/_knowledge/retrieval.py`, `search()` (starts
  at line 48). Add the missing-embeddings guard. Current body (lines
  78-93):
  ```python
      if mode not in ("hybrid", "semantic", "keyword"):
          return f"Error: Invalid mode '{mode}'. Must be 'hybrid', 'semantic', or 'keyword'"

      config = _get_config()
      limit = k if k is not None else config.search_limit

      with LogSpan(span="kb.search", q=q, db=db, mode=mode, k=limit) as s:
          try:
              conn = get_connection(db)

              if mode == "hybrid":
                  results = search_hybrid(conn, q, limit * 3, category=category)
              elif mode == "semantic":
                  results = search_vec(conn, q, limit * 3, category=category)
              else:
                  results = search_fts(conn, q, limit * 3, category=category)
  ```
  Change to:
  ```python
      if mode not in ("hybrid", "semantic", "keyword"):
          return f"Error: Invalid mode '{mode}'. Must be 'hybrid', 'semantic', or 'keyword'"

      config = _get_config()
      limit = k if k is not None else config.search_limit

      if mode in ("hybrid", "semantic"):
          from .indexer import _db_embeddings_enabled

          if not _db_embeddings_enabled(db):
              return (
                  "Semantic search requires embeddings. Enable with: "
                  f"tools.knowledge.kb.{db}.db.embeddings_enabled: true"
              )

      with LogSpan(span="kb.search", q=q, db=db, mode=mode, k=limit) as s:
          try:
              conn = get_connection(db)

              if mode in ("hybrid", "semantic"):
                  from .db import _check_vec_available

                  if not _check_vec_available():
                      return (
                          "Semantic search requires the sqlite-vec package. "
                          "Install with: pip install onetool-mcp[util]"
                      )
                  has_embeddings = conn.execute(
                      "SELECT 1 FROM chunks_vec LIMIT 1"
                  ).fetchone()
                  if not has_embeddings:
                      return (
                          f"No embeddings found for '{db}'. "
                          f"Run kb.reindex(db='{db}') to generate them."
                      )

              if mode == "hybrid":
                  results = search_hybrid(conn, q, limit * 3, category=category)
              elif mode == "semantic":
                  results = search_vec(conn, q, limit * 3, category=category)
              else:
                  results = search_fts(conn, q, limit * 3, category=category)
  ```
  Everything after this point in the function is unchanged. `keyword` mode
  is unaffected (the guard only applies to `hybrid`/`semantic`).
- [x] 8.2 Add two new tests to `tests/otutil/unit/tools/test_knowledge.py`
  (a new class, e.g. `TestSearchEmbeddingsGuard`, marked
  `@pytest.mark.unit @pytest.mark.tools`):
  ```python
  @pytest.mark.unit
  @pytest.mark.tools
  class TestSearchEmbeddingsGuard:
      """kb.search() returns actionable guidance instead of raw errors
      when embeddings are disabled or missing."""

      def test_embeddings_disabled_returns_friendly_message_without_opening_db(self):
          from otutil.tools._knowledge import retrieval

          with patch("otutil.tools._knowledge.indexer._db_embeddings_enabled", return_value=False), \
               patch.object(retrieval, "get_connection") as mock_get_conn:
              result = retrieval.search(q="x", db="testdb", mode="hybrid")

          assert result == (
              "Semantic search requires embeddings. Enable with: "
              "tools.knowledge.kb.testdb.db.embeddings_enabled: true"
          )
          mock_get_conn.assert_not_called()

      def test_no_embeddings_generated_returns_friendly_message(self):
          from otutil.tools._knowledge import retrieval

          mock_conn = MagicMock()
          mock_conn.execute.return_value.fetchone.return_value = None

          with patch("otutil.tools._knowledge.indexer._db_embeddings_enabled", return_value=True), \
               patch("otutil.tools._knowledge.db._check_vec_available", return_value=True), \
               patch.object(retrieval, "get_connection", return_value=mock_conn):
              result = retrieval.search(q="x", db="testdb", mode="semantic")

          assert result == "No embeddings found for 'testdb'. Run kb.reindex(db='testdb') to generate them."
  ```
  `MagicMock` and `patch` are already imported at the top of
  `tests/otutil/unit/tools/test_knowledge.py`. Run
  `uv run pytest tests/otutil/unit/tools/test_knowledge.py -m "unit and tools" -v`
  and confirm both new tests pass and no existing test in the file
  regresses (in particular the existing `TestKnowledgeSearch` class, which
  exercises `search_hybrid`/`search_vec`/`search_fts` directly rather than
  through `retrieval.search()`, should be unaffected).

## 9. chrome-util.md / play-util.md — relationship to the proxied server

**Coordination note (read before starting):** `p16-extras-restructure` also
adds content to both files' `## Requires` sections (Chrome-launch-flag
guidance), and `p31-demos-and-positioning` independently specifies the same
"proxy companion" framing as part of its `docs/learn/mcp-proxy.md`
walkthrough (it does not edit these two files directly — it documents the
relationship in the new walkthrough doc and cross-references these pages).
To stay robust regardless of implementation order: anchor the insertion
point on the section boundary (immediately before `## Configuration`), not
on matching the section's exact current text, and check first whether a
"Relationship to the Proxied Server" (or equivalently-titled) section
already exists in the file before adding a second one.

- [x] 9.1 In `docs/reference/tools/chrome-util.md`, check whether a section
  describing the pack's relationship to the proxied `chrome_devtools`
  server already exists (it may not, or `p16`'s Chrome-launch-flags
  addition to `## Requires` may have landed first — that's a different
  paragraph in a different section, not this one). If no such section
  exists, insert a new section immediately before `## Configuration`
  (after `## Requires`, wherever that section currently ends):
  ```
  ## Relationship to the Proxied Server

  `chrome_util` is a thin annotation/highlight layer over the Chrome
  DevTools MCP server it proxies to — it does not replace that server's
  own tools. Calls like `chrome_util.highlight_element()` and
  `chrome_util.guide_user()` forward to the proxied server via
  `call_tool_sync(server, tool, ...)` (see `src/otdev/_inject_base.py`),
  using the browser eval tool that server exposes. For anything outside
  annotation/highlighting (navigation, screenshots, network inspection,
  etc.), call the underlying server's own tools directly under its proxy
  name — by default `chrome_devtools`, or whatever name you configure
  under `servers:` in `onetool.yaml` and pass as `server=` to
  `chrome_util` functions.
  ```
- [x] 9.2 In `docs/reference/tools/play-util.md`, apply the same
  already-exists check, then insert the equivalent section immediately
  before `## Configuration`:
  ```
  ## Relationship to the Proxied Server

  `play_util` is a thin annotation/highlight layer over the Playwright MCP
  server it proxies to — it does not replace that server's own tools.
  Calls like `play_util.highlight_element()` and `play_util.guide_user()`
  forward to the proxied server via `call_tool_sync(server, tool, ...)`
  (see `src/otdev/_inject_base.py`), using the browser eval tool that
  server exposes. For anything outside annotation/highlighting
  (navigation, screenshots, waiting, network inspection, etc.), call the
  underlying server's own tools directly under its proxy name — by default
  `playwright`, or whatever name you configure under `servers:` in
  `onetool.yaml` and pass as `server=` to `play_util` functions.
  ```

## 10. Install prerequisites: Python 3.12 + uv

- [x] 10.1 In `docs/learn/installation.md`, replace line 3
  (`**Python 3.11+ required.**`) with:
  ```
  **Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).**
  ```
- [x] 10.2 In the same file, in the "System Requirements" table (line ~11),
  change `| **Python** | >= 3.11 | Runtime environment |` to
  `| **Python** | >= 3.12 | Runtime environment |`.
- [x] 10.3 In the same file's "Installing System Requirements" code blocks,
  change:
  - Line 19: `brew install python@3.11` → `brew install python@3.12`
  - Line 26: `apt install python3.11` → `apt install python3.12`
  - Line 33: `winget install Python.Python.3.11` → `winget install Python.Python.3.12`
- [x] 10.4 **Do NOT restructure `installation.md`'s `## Install` section to
  reorder it ahead of `## System Requirements`.** `p15-install-flow-and-mcp-config`
  already owns and is rewriting `installation.md:37-73` (the Install
  section) with bootstrap-installer content per its own task 5.3, and its
  task 5.5 explicitly excludes the Python-version lines (10.1-10.3 above)
  as this change's territory. A naive reorder here would conflict with
  p15's larger rewrite of the same lines. This change's contribution to
  "lead with the recommended install" is limited to the version-number
  fixes above; the actual reordering/rewrite is p15's.
- [x] 10.5 In `README.md`, line 15, change
  `python-3.11%2B-blue` to `python-3.12%2B-blue` (the Python version
  badge).

## 11. kb.py wrong package name in install hints

- [x] 11.1 In `src/onetool/kb.py`, line 209, change:
  ```python
              "[red]crawl4ai is required. Install with:[/red] pip install 'onetool\\[scrape]'"
  ```
  to:
  ```python
              "[red]crawl4ai is required. Install with:[/red] pip install 'onetool-mcp\\[scrape]'"
  ```
- [x] 11.2 In the same file, line 234, change:
  ```python
              "[red]Playwright is required. Install with:[/red] pip install 'onetool\\[scrape]'"
  ```
  to:
  ```python
              "[red]Playwright is required. Install with:[/red] pip install 'onetool-mcp\\[scrape]'"
  ```
  (Keep the `\\[` escaping exactly as-is — it prevents `rich`'s console
  markup from interpreting `[scrape]` as a style tag.)

## 12. README canonical tool count

- [x] 12.1 In `README.md`, standardize every tool-count mention on
  `240+`. Change:
  - Line 9: `100+ tools including Brave, ...` → `240+ tools including Brave, ...`
  - Line 81: `That's it. All 100+ tools work out of the box.` → `That's it. All 240+ tools work out of the box.`
  - Line 117: `| **100+ Built-in Tools**  | ...` → `| **240+ Built-in Tools**  | ...`
  - Line 132: `27+ packs, 230+ tools ready to use:` → `27+ packs, 240+ tools ready to use:`
  - Line 161: `... full summary table with all 230+ tools` → `... full summary table with all 240+ tools`
  - Line 220: `- [Tools Reference](...) - All 100+ tools` → `- [Tools Reference](...) - All 240+ tools`
  Do not change the pack count (`27+`), only the tool count. Before
  finishing, run `grep -n "100+\|230+" README.md` and confirm it returns
  nothing.

## 13. README ot.status row

- [x] 13.1 In `README.md`'s Tools table (line ~153), change:
  ```
  | `ot`          | `help`, `tools`, `stats`, `skills`             |          | Introspection                  |
  ```
  to:
  ```
  | `ot`          | `help`, `tools`, `stats`, `status`, `skills`   |          | Introspection                  |
  ```

## 14. Secrets pack guidance-drift fix

**Do NOT add `pyrage`/`keyring` to `ot_secrets.md`'s Requires section in
this task group** — `p14-guided-encrypted-secrets` already owns that exact
edit (its own task 14.1 targets `docs/reference/tools/ot_secrets.md:33-35`
for the same content, as part of rewriting that page's Functions table for
its new `set`/`get` tools). Adding it here too would conflict. This task
group is scoped to the `ot/config/secrets.py` guidance-drift fix only,
which p14 does not touch (p14's `config/secrets.py` edits are at
different lines: `:129-132`, the "no age identity in keychain" message,
and `:137`, `b64decode(validate=True)` — not the `:116,124`
missing-package `ImportError` strings this task group fixes).

- [x] 14.1 Fix guidance drift in `src/ot/config/secrets.py`. Two
  `ImportError` messages there currently tell the user to run a bare
  reinstall (`pip install onetool-mcp`) instead of naming the actually
  missing package, unlike the pack's own equivalent checks in
  `src/ottools/ot_secrets.py:46,57` (`pip install keyring` /
  `pip install pyrage`). Change:
  - Line 116 (inside the `keyring` `ImportError` block, ~line 111-117):
    `"Run: pip install onetool-mcp"` → `"Run: pip install keyring"`
  - Line 124 (inside the `pyrage` `ImportError` block, ~line 119-125):
    `"Run: pip install onetool-mcp"` → `"Run: pip install pyrage"`
- [x] 14.2 Update the two existing tests in
  `tests/unit/core/test_secrets.py` that pin the old message text (they
  will otherwise fail after 14.1):
  - `test_missing_keyring_raises_import_error` (line ~467):
    `pytest.raises(ImportError, match="pip install onetool-mcp")` →
    `pytest.raises(ImportError, match="pip install keyring")`
  - `test_missing_pyrage_raises_import_error` (line ~481):
    `pytest.raises(ImportError, match="pip install onetool-mcp")` →
    `pytest.raises(ImportError, match="pip install pyrage")`
  Run `uv run pytest tests/unit/core/test_secrets.py -m unit -v` and
  confirm both tests pass.

## 15. Marketing claims reconciliation

- [x] 15.1 In `dev/project/brand/claims.md`, replace the "96% reduction in
  token usage (25x)" section (lines 27-45) with corrected numbers sourced
  from `docs/learn/comparison.md` (one-shot: `47,660 → 1,131` at
  `comparison.md:7`; 3-shot: `119,258 → 2,947` at `comparison.md:19`).
  Current:
  ```
  ### 96% reduction in token usage (25x)

  OneTool reduces input token usage by 96% compared to multiple MCP servers.

  **Assumptions:**

  - One-shot: 46,130 → 1,999 tokens = 95.7% reduction (23x)
  - Multi-turn (3 turns): 146,387 → 5,152 tokens = 96.5% reduction (28x)
  - Gap widens with more turns (tool definitions resent each turn)
  - 18 MCP servers vs OneTool (single tool)
  - Source: [compare.md](../../../docs/learn/comparison.md)

  **Comparison** (industry data from [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)):

  | Technique                 | Token Reduction |
  | ------------------------- | --------------- |
  | **OneTool**               | **96%**         |
  | Tool Search Tool          | 85%             |
  | Programmatic Tool Calling | 37%             |
  ```
  Replace with:
  ```
  ### 97% reduction in token usage (~40x)

  OneTool reduces input token usage by ~97% compared to multiple MCP servers.

  **Assumptions:**

  - One-shot: 47,660 → 1,131 tokens = 97.6% reduction (42x)
  - Multi-turn (3 turns): 119,258 → 2,947 tokens = 97.5% reduction (40x)
  - Gap widens with more turns (tool definitions resent each turn)
  - 18 MCP servers vs OneTool (single tool)
  - Measured: February 2026 (raw data: `docs/results/result-20260223-0334.csv`). The benchmark harness (OT Bench) now lives outside this repository; these are the last figures generated from it before externalization.
  - Source: [comparison.md](../../../docs/learn/comparison.md)

  **Comparison** (industry data from [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)):

  | Technique                 | Token Reduction |
  | ------------------------- | --------------- |
  | **OneTool**               | **97%**         |
  | Tool Search Tool          | 85%             |
  | Programmatic Tool Calling | 37%             |
  ```
- [x] 15.2 Do **not** edit `claims.md:14-23` (the "$30 per MCP server per
  month" section, which cites a `$485/month` figure). Its provenance could
  not be verified against `comparison.md`'s current numbers (`$395/month`
  total, `$385/month` waste) within this change's scope
  (`claims.md:33-34` vs `comparison.md:7,19`). Leave it as-is and note it
  in your final report to the user as an unresolved finding, not a task to
  complete here.
- [x] 15.3 Verify: `grep -n "46,130\|146,387\|1,999\|5,152" dev/project/brand/claims.md`
  returns nothing (the stale numbers are gone).

## 16. R8 S4/S5 — proxy env broadcast + Direct API trust boundary docs

- [x] 16.1 In `docs/reference/cli/onetool-config.md`, in the "### Stdio
  Servers" section (after the existing `tool_prefix` paragraph, currently
  ending around line 375), add:
  ```
  **Environment variables:** the root-level `env:` block (see [YAML
  Schema](#yaml-schema)) is merged into **every** stdio server's
  environment, including third-party proxied servers — a value meant for
  one server is visible to all of them. Prefer per-server `env:` (shown
  above) for secrets or values that should not be shared across servers.
  Reserve root-level `env:` for genuinely global settings (e.g. `LANG`).
  ```
- [x] 16.2 In the same file's "## YAML Schema" code block (line 55),
  change the inline comment on `env:` from:
  ```
  env:                          # Default subprocess environment variables
  ```
  to:
  ```
  env:                          # Default subprocess env vars — broadcast to every proxied stdio server, see External MCP Servers
  ```
- [x] 16.3 (optional) In the same file's "## Direct API Configuration"
  section (after the existing field table, ~line 471), add a short trust-
  boundary note:
  ```
  The Direct API key grants full command execution to any process running
  as the same OS user that started the OneTool server — this is inherent
  to the same-user trust boundary (a malicious process running as that
  user already has equivalent access), not a vulnerability of the API
  itself. Treat the key file (`0600`) like any other local secret.
  ```

## 17. Verification

- [x] 17.1 `rg -n "3\.11" docs README.md` returns empty (no stale Python
  version references remain in touched docs).
- [x] 17.2 `rg -n "onetool\\\[" src/` returns empty (no more bare
  `onetool[...]` package-name references; all say `onetool-mcp[...]`).
- [x] 17.3 `grep -n "database\"" src/otdev/tools/db.py` and
  `grep -n "web-fetch\"" src/otdev/tools/webfetch.py` both return empty
  (doc_slug values fixed).
- [x] 17.4 `grep -n "100+\|230+" README.md` returns empty; `grep -c "240+"
  README.md` returns `6`.
- [x] 17.5 `grep -n "46,130\|146,387" dev/project/brand/claims.md` returns
  empty; every number in the "97% reduction" section of `claims.md` is
  present verbatim in `docs/learn/comparison.md`.
- [x] 17.6 `uv run python scripts/check_docs_registry.py` passes (still
  passes — this change does not touch `docs/reference/tools/index.md`, but
  confirms nothing was broken).
- [x] 17.7 `uv run pytest tests/otutil/unit/tools/test_ground.py tests/otutil/unit/tools/test_knowledge.py tests/unit/core/test_secrets.py -v`
  passes, including the 3 new/updated tests from tasks 7.2, 8.2, 14.2. (No
  `-m` filter needed — pointing pytest at these three files already scopes
  the run; each test's own markers, `unit`+`tools` or `unit`+`core`, are
  unchanged from the surrounding file's convention.)
- [x] 17.8 `just check` passes (full lint + type + test gate).
- [x] 17.9 Spot-check that generated help doc URLs resolve: with the server
  running (or by inspecting `_get_doc_url("db")` / `_get_doc_url("webfetch")`
  return values directly, e.g. via a quick Python REPL import), confirm
  they produce `https://onetool.beycom.online/reference/tools/db/` and
  `.../webfetch/` — not `/database/` or `/web-fetch/`.
