## Why

Pack APIs are inconsistent in ways that actively break agent calls today. `kb.search(query=...)` raises a param error because the underlying parameter is literally named `q` (no prefix match possible), while the semantically identical `mem.search(q=...)` works fine because mem's parameter is already named `query`. `mem.search`'s non-vector mode is spelled `mode="pattern"` while `kb.search`'s equivalent mode is spelled `mode="keyword"`, forcing agents to remember per-pack vocabulary for the same concept. `brave.search`'s result-count parameter (`count`) diverges from `tavily.search`'s (`max_results`) for the same concept, breaking the pattern where `max=` works as a universal prefix across search packs. `db.query()` has no way to enforce read-only execution, even though its own docs (fixed separately, see Impact) claim it is read-only by default — it is not. And roughly 18 documented `excalidraw.`-prefixed docstring examples inside the whiteboard pack raise `NameError` today, because the pack registers only `whiteboard`/`wb`, not `excalidraw`, despite `excalidraw` being the tool's actual product name and the maintainer's explicit intent that `excalidraw` = `whiteboard`.

V3 is a declared breaking-change window (renames, not aliases; removals, not deprecations — maintainer rule). This is the right time to land these fixes cleanly, without compatibility shims.

A key mechanical fact makes most of these renames far less disruptive than they look: `src/ot/executor/param_resolver.py:113` resolves any provided keyword argument that is a *prefix* of a real parameter name to that parameter (see `resolve_kwargs`, e.g. `q=` resolves to `query` if `query` is the only parameter starting with `q`). Standardizing on the *long* canonical parameter names therefore keeps every shorter, natural prefix working for free. Renaming `kb.search`'s `q` to `query` is consequently close to non-breaking. Value renames (`mode="pattern"` → `mode="keyword"`) are not covered by this mechanism — a bare string value is never prefix-matched — so those are clean breaks, deliberately accepted inside the V3 window.

## What Changes

- **BREAKING**: `knowledge.search()` / `kb.search()` and `knowledge.ask()` / `kb.ask()` rename their `q` parameter to `query`. Because of prefix matching, callers already using `q=...` keep working unchanged; only callers passing the exact string `query=...` today (which currently fails outright) newly succeed.
- **BREAKING**: `mem.search()`'s `mode="pattern"` value is renamed to `mode="keyword"` to match `kb.search`'s vocabulary for the same FTS/non-vector search mode. `mode="pattern"` is removed outright — no fallback. (`mem.grep()`'s unrelated `pattern` parameter, the regex/literal search string, is untouched.)
- **BREAKING**: the `count` result-count parameter is renamed to `max_results` across ALL brave functions — `search()`, `news()`, `image()`, `video()`, and `search_batch()` — matching `tavily.search()`. Pack-wide scope is deliberate: the report's intent is "unify result-count param across search packs … `max=` then works everywhere via prefix"; a search-only rename would leave brave internally inconsistent (`search(max_results=)` next to `news(count=)`). `count=` no longer works anywhere in brave; `max=` (and any other prefix of `max_results`) works everywhere. Function defaults are unchanged (10 for the single searches, 2 per query for `search_batch`).
- **NEW**: `db.query()` gains an opt-in `read_only: bool = False` parameter. When `True`, the call is rejected with an error unless the statement's first keyword is `SELECT`, `EXPLAIN`, or `PRAGMA`. Default behavior (`read_only=False`, the current behavior) is unchanged.
- **NEW**: the whiteboard pack gains a second alias: `pack_aliases = ("wb", "excalidraw")` in `src/otdev/tools/excalidraw.py`. The pack becomes reachable as `whiteboard.*`, `wb.*`, or `excalidraw.*`. This is a first-class product-naming feature (the tool's docstrings and public identity already call it "excalidraw"), not a backward-compatibility shim.
- **OPTIONAL** (include if capacity allows): `ot_llm.transform_file()` stops using `result.startswith("Error:")` to classify the underlying `transform()` call as failed. This string-sniffing has a false-positive risk: if the LLM's legitimate transformed output happens to start with the literal text "Error:", `transform_file()` today misreports success as failure and refuses to write the output file. The fix threads a structured success/failure signal instead.

Deferred (evaluated, not V3 — no tasks in this change for these):
- Brave `extract_schema` parity with Tavily.
- Batch-support parity for secondary Brave search functions (news/image/video gaining batch variants). Note: the `count` → `max_results` rename on those functions is NOT deferred — it lands in this change (pack-wide rename above).
- Search time-filter vocabulary unification (e.g. Brave `freshness` vs Tavily `time_range`).
- `ot_llm`/convert in-memory return mode.

## Capabilities

### New Capabilities
(none — all changes below modify existing tool-pack capabilities)

### Modified Capabilities
- `knowledge-pack`: `kb.search`/`kb.ask` (and their `knowledge.` full-name equivalents) rename parameter `q` → `query`.
- `otutil/tool-brave`: all brave functions rename parameter `count` → `max_results`; the shared Query Validation requirement's count-validation scenario becomes `max_results` across all functions; the Batch Search requirement's forwarding scenario is updated accordingly.
- `ottools/tool-mem`: `mem.search()`'s `mode` value `"pattern"` is renamed to `"keyword"`.
- `otdev/tool-db`: `db.query()` gains an opt-in `read_only` guard.
- `otdev/tool-excalidraw`: the whiteboard pack gains `excalidraw` as a second registered alias (alongside `wb`).
- `ottools/tool-llm` (optional item): `transform_file()`'s failure-detection mechanism changes; adds one new observable scenario (legitimate output starting with "Error:" is written normally, not misclassified as a failure).

## Impact

**Code:**
- `src/otutil/tools/_knowledge/retrieval.py` — `search()`/`ask()` parameter and internal variable rename (`q` → `query`), docstrings, examples, `LogSpan` field.
- `src/otutil/tools/_mem/search.py` — `mode` value rename (`"pattern"` → `"keyword"`), docstring, error message, dispatch branch, `_search_pattern` → `_search_keyword` rename (private helper).
- `src/otutil/tools/brave.py` — pack-wide parameter rename (`count` → `max_results`) in `search()`, `news()`, `image()`, `video()`, `search_batch()`; `_validate_count()` helper renamed to `_validate_max_results()` (message shape mirrors `tavily._validate_max_results`); docstrings, examples, request-params dicts (the Brave API's own `"count"` query-string field stays — external contract).
- `src/ottools/ot_llm.py` — 3 docstring examples reference `brave.search(..., count=...)`; must be updated to `max_results=...` as a direct consequence of the brave rename (not optional, regardless of whether the optional transform_file item is picked up).
- `src/otdev/tools/db.py` — `query()` gains `read_only` parameter and a new `_is_read_only_sql()` helper.
- `src/otdev/tools/excalidraw.py` — one-line `pack_aliases` change.
- `src/ottools/ot_llm.py` (optional) — `transform()`/`transform_file()` internal refactor to a shared structured-result helper.

**Docs:**
- `docs/reference/tools/knowledge.md`, `docs/reference/tools/mem.md`, `docs/reference/tools/brave.md`, `docs/reference/tools/db.md` — updated parameter tables/examples for the above renames and new parameter.
- `docs/learn/explicit-calls.md`, `tests/explore/sanity.md` — example snippets using `brave.search(..., count=...)`.
- `docs/reference/tools/tool-index.md` — auto-generated; regenerated via `just docs-sync`, not hand-edited.
- **Explicitly excluded**: `docs/learn/whats-new-v2.md` documents the v2 release's API surface as it was at the time (including `kb.search(q=...)`); it is historical changelog content and must NOT be rewritten to reflect the V3 rename.
- **Coordination with `p18-docs-debt-sweep`**: `docs/reference/tools/db.md:112` falsely claims "Queries are read-only by default" — fixing that false claim is owned by `p18`, not this change. This change only adds the new `read_only` parameter's own documentation row; it does not touch the false claim itself. Similarly, the rest of the R5 docs-only sweep table (doc_slug 404s, package.md wrong param, webfetch positional-arg examples, etc.) is entirely owned by `p18` — this change touches only the excalidraw alias row of that table.

**Tests:**
- `tests/otutil/unit/tools/test_knowledge.py` — one `q="test"` call site.
- `tests/otutil/unit/tools/test_mem.py`, `tests/integration/tools/test_mem.py` — `mode="pattern"` call sites.
- `tests/otutil/unit/tools/test_brave.py`, `tests/integration/tools/test_brave.py` — every `count=` call site on any brave function, plus the `_validate_count` unit-test class (renamed helper) and the `search_batch` invalid-count test.
- `tests/integration/tools/test_db.py` — new `read_only` guard tests.
- `tests/unit/core/test_pack_proxy.py` — new assertion that `excalidraw` resolves alongside `wb`.

**Specs:** `openspec/specs/knowledge-pack/spec.md`, `openspec/specs/otutil/tool-brave/spec.md`, `openspec/specs/ottools/tool-mem/spec.md`, `openspec/specs/otdev/tool-db/spec.md`, `openspec/specs/otdev/tool-excalidraw/spec.md`, `openspec/specs/ottools/tool-llm/spec.md` (optional item).

**Verification gate:** `just check` (lint + type + test) must pass. `uv run python scripts/check_docs_registry.py` (also run via `just docs-sync`) must pass after `docs-sync` regenerates `tool-index.md`.
