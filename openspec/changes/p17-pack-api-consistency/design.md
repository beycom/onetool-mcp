## Context

This is a batch of five small, unrelated API-consistency fixes across five different tool packs, grouped into one change because they were identified together in `wip/release-v3/release-v3-report-2.md` §R5 ("Rename cluster") and its adjacent "Committed and optional small features" list, and because V3 is a declared breaking-change window (renames, not aliases; removals, not deprecations). There is no shared runtime mechanism between the five items — each is independent and can be implemented and verified in isolation. What they share is the *reasoning tool*: `src/ot/executor/param_resolver.py`'s `resolve_kwargs()` prefix-matching, which determines how "breaking" each rename actually is in practice.

### Param prefix matching (why some renames are nearly free)

`src/ot/executor/param_resolver.py:106-125` (function `resolve_kwargs`):

```python
for key, value in kwargs.items():
    # Exact match - use as-is
    if key in param_set:
        resolved[key] = value
        continue

    # Find prefix matches (preserve signature order)
    matches = [p for p in param_names if p.startswith(key)]

    if len(matches) == 1:
        resolved[matches[0]] = value
    elif len(matches) > 1:
        resolved[matches[0]] = value
    else:
        resolved[key] = value  # no match - passthrough (raises the function's own TypeError)
```

A caller-provided keyword argument that is a *prefix* of exactly one real parameter name is silently rewritten to that parameter name before the call executes. Consequence: once a parameter is named with a long, unambiguous canonical name, every shorter prefix a caller might type continues to work. This is why renaming `kb.search`'s `q` → `query` is not really breaking (any caller already typing `q=...` keeps working — `q` is a prefix of `query`), while renaming a *value* like `mode="pattern"` → `mode="keyword"` is a clean, unavoidable break (bare string values are never prefix-matched).

## Goals / Non-Goals

**Goals:**
- Land five independent, narrowly-scoped API fixes: `kb`/`knowledge` `q`→`query`, `mem.search` `mode="pattern"`→`mode="keyword"`, `brave.search` `count`→`max_results`, `db.query(read_only=...)`, and the `excalidraw` pack alias.
- Every rename lands with zero compatibility fallback for the removed name/value (V3 rule).
- Every doc, spec, and test that exercises the renamed surface is updated in the same change — no stale examples left behind that would `NameError`/`TypeError`/silently-wrong-error on the next reader.
- (Optional, include if capacity allows) Fix `ot_llm.transform_file()`'s false-positive-prone `"Error:"` string-sniffing.

**Non-Goals:**
- Adding batch support or `extract_schema` parity to secondary Brave functions (the report's genuinely deferred items). Note the `count` → `max_results` rename itself IS pack-wide (see D3) — the report's rename intent is "unify result-count param across search packs … `max=` then works everywhere via prefix", which a search-only rename would defeat by leaving brave internally inconsistent (`search(max_results=)` next to `news(count=)`).
- Fixing `docs/reference/tools/db.md:112`'s false "Queries are read-only by default" claim. That doc-only fix is owned by `p18-docs-debt-sweep`. This change only documents the *new* `read_only` parameter it adds.
- Any other item in the R5 "docs-only sweep" table (doc_slug 404s, `package.audit` docs, webfetch positional-arg examples, whiteboard `draw` docstring self-contradiction, `ot.help`/`ctx.ask` doc visibility, `ground` `ImportError` escaping the formatter, `kb.search` missing-embeddings error surfacing) — all owned by `p18-docs-debt-sweep`, except the excalidraw alias row, which is this change.
- Rewriting `docs/learn/whats-new-v2.md`. It documents the API surface as it existed at the v2 release (including `kb.search(q=...)`, which was correct at the time). It is historical changelog content, not current reference documentation, and must not be touched by this change.
- Adding batch-transform functionality to `ot_llm` (see Open Questions — the report's "batch `transform` parity" phrase has no corresponding function in the current codebase; treated as anchor drift, not implemented).

## Decisions

### D1 — kb/knowledge: rename `q` → `query` in `search()` and `ask()`

File: `src/otutil/tools/_knowledge/retrieval.py`. Rename the parameter and every internal reference to it, in both `search()` (currently lines 48-130) and `ask()` (currently lines 133-199): the parameter itself, the `Args:` docstring line, both `Example:` docstring lines, the `LogSpan(..., q=q, ...)` keyword, every call site that passes the local variable positionally (`search_hybrid(conn, q, ...)`, `search_vec(conn, q, ...)`, `search_fts(conn, q, ...)`), and every f-string that references `{q}` (`"No results found for: {q}"`, `"Found {len(results)} results for: {q}"`, `"No relevant entries found for: {q}"`). Do not touch `related()` (parameter is `topic`, unrelated) or the private `search_hybrid`/`search_vec`/`search_fts` functions in `search.py` (their own parameter names are internal implementation detail, unaffected by kb's public rename).

Alternative considered: keep `q` and add `query` as an accepted alias inside the function body. Rejected — violates the explicit V3 no-alias-fallback rule, and is unnecessary since prefix matching already gives callers `q=` for free once the canonical name is `query`.

### D2 — mem: rename mode value `"pattern"` → `"keyword"`

File: `src/otutil/tools/_mem/search.py`. This is a *value* rename, not a parameter rename — `resolve_kwargs()` prefix matching does not apply to string values, so there is no free backward compatibility here. Change:
- The mode validation tuple: `if mode not in ("semantic", "pattern", "hybrid")` → `("semantic", "keyword", "hybrid")`.
- The error message: `f"Error: Invalid mode '{mode}'. Must be 'semantic', 'pattern', or 'hybrid'"` → `'semantic', 'keyword', or 'hybrid'`.
- The dispatch branch: `elif mode == "pattern":` → `elif mode == "keyword":`.
- Docstring `mode:` line and the `Example:` line using `mode="pattern"`.
- The private helper `_search_pattern()` → `_search_keyword()` (rename the function and its two call sites — the dispatch in `search()` and the internal call inside `_search_hybrid()` — and its `__all__` entry), for naming consistency with the new public vocabulary. This is an internal identifier with no external contract implications; renaming it is a small consistency improvement, not a requirement, but keep it in the same commit to avoid a `_search_pattern` function implementing `mode="keyword"` reading confusingly in future diffs.

Do **not** touch `mem.grep(pattern=...)` — that `pattern` parameter is an unrelated concept (the regex/literal string to search for), not a search mode. Grepping the diff for `"pattern"` after this change will still show many legitimate hits in `mem.grep`, `mem.write_batch(glob_pattern=...)`, and `tools.mem.redaction_patterns`/`exclude_file_patterns` config — none of those are in scope.

### D3 — brave: rename `count` → `max_results` on ALL result-count parameters

File: `src/otutil/tools/brave.py`. Scope is pack-wide: `search()` (signature currently at line
467-478), `news()`, `image()`, `video()`, and `search_batch()` all rename their result-count
parameter `count` → `max_results` (defaults unchanged: 10 for the single searches, 2 per query
for `search_batch`). Rationale: the report's rename intent is "unify result-count param across
search packs" so that "`max=` then works everywhere via prefix" — renaming only `search()` would
leave brave internally inconsistent and defeat the unification. Rename the shared
`_validate_count()` helper to `_validate_max_results()`, mirroring `tavily._validate_max_results`
(same 1-20 range, same message shape):

```python
def _validate_max_results(max_results: int) -> str | None:
    """Validate max_results is in range 1-20. Returns error string or None if valid."""
    if 1 <= max_results <= 20:
        return None
    return f"Error: max_results must be between 1 and 20 (got {max_results})"
```

In each of `search()`, `news()`, `image()`, `video()`, and `search_batch()`: rename the `count`
parameter to `max_results` (keeping each function's existing default); update the `Args:`
docstring line and every `Example:` line (`brave.search(query="AI news", freshness="pw",
count=5)` → `max_results=5`); replace `_validate_count(count)` calls with
`_validate_max_results(max_results)`; in each outgoing Brave API request-params dict, change
`"count": count,` to `"count": max_results,` — the *Brave API's own* query-string field is still
literally called `count` (that's Brave's external contract, unrelated to our function's parameter
name), only the Python-side variable feeding it changes. `search_batch()` also forwards its
per-query value into each `search()` call — update that forwarding kwarg. Internal log/stats
field names (e.g. a `count` key in LogEntry/stats payloads) are NOT part of the tool contract and
stay unchanged.

Any other file that calls `brave.<fn>(..., count=...)` must be updated to `max_results=...` as a
mechanical consequence — this is not optional polish, the old call sites will raise
`TypeError: ... got an unexpected keyword argument 'count'` once the rename lands. Known call
sites to check (found via `rg -n 'brave\.(search|news|image|video|search_batch)\(' | grep
'count='`, plus `rg -n '"count"' tests/otutil/unit/tools/test_brave.py`) are enumerated in
`tasks.md`; do not rely on this list being exhaustive without re-running that `rg` search after
making the code change, since intervening edits by sibling changes could add new call sites.

### D4 — db: `read_only` guard is a first-keyword check, not a parser

File: `src/otdev/tools/db.py`. Add `read_only: bool = False` to `query()`'s signature (currently line 408). Implement with a simple first-token check, not a SQL parser or regex with comment-stripping — the report's decision is "rejects non-SELECT/EXPLAIN/PRAGMA", not "handles every SQL comment/whitespace edge case":

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

Insert the check in `query()` right after the existing `db_url`/`sql` emptiness checks (currently lines 442-448) and before the `try:` block that opens the engine connection:

```python
        if read_only and not _is_read_only_sql(sql):
            s.add(error="read_only_violation")
            return "Error: read_only=True but statement is not SELECT/EXPLAIN/PRAGMA"
```

No new import is required (no `re` needed — `str.split()` suffices). Alternative considered: parse and validate via `sqlalchemy`'s statement introspection. Rejected as overkill for a guard whose decided scope is "rejects non-SELECT/EXPLAIN/PRAGMA" — a first-keyword check is sufficient, auditable in one line, and has no SQL-dialect coupling.

### D5 — excalidraw: pack_aliases gains "excalidraw"

File: `src/otdev/tools/excalidraw.py:20`. One-line change: `pack_aliases = ("wb",)` → `pack_aliases = ("wb", "excalidraw")`. The alias-injection mechanism (`src/ot/executor/pack_proxy.py:316-320`, in `build_execution_namespace`) already iterates every alias in `registry.pack_aliases[full_name]` and injects each one into the execution namespace if not already present — no mechanism change needed, only the declaration. `registry.pack_aliases` is populated by `src/ot/executor/tool_loader.py:319-322`, which reads the module-level `pack`/`pack_aliases` tuple — also no change needed there, it already supports N aliases per pack.

This directly fixes the ~18 `excalidraw.`-prefixed docstring examples in `excalidraw.py` (currently `NameError` because only `whiteboard`/`wb` resolve). Those docstring examples are not doctests and are not executed by any test — "fixing" them is really just the alias addition making their existing text true. No docstring *text* edits are required by this item; the anchor lines exist only to prove the scope/value of the fix, not to be individually edited.

### D6 (optional) — ot_llm: replace string-sniffing with a structured internal result

File: `src/ottools/ot_llm.py`. Extract the body of `transform()` (validation + API call, currently everything from the prompt/data validation through building the return string) into a private helper that returns a structured result instead of always collapsing to a string:

```python
def _transform_core(
    *, data: Any, prompt: str, model: str | None, json_mode: bool
) -> tuple[bool, str]:
    """Run the transform; return (ok, content_or_error). Never raises."""
    # ... same body as today's transform(), except every `return "Error: ..."`
    # becomes `return False, "Error: ..."` and the final success path
    # becomes `return True, resp.choices[0].message.content or ""`
```

`transform()` becomes a two-line wrapper preserving today's exact external contract (always returns a string; "Error: ..." prefix on failure remains the documented public behavior — see `tool-llm/spec.md`'s unmodified "Error Handling" requirement):

```python
def transform(*, data: Any, prompt: str, model: str | None = None, json_mode: bool = False) -> str:
    """... (docstring unchanged) ..."""
    _ok, result = _transform_core(data=data, prompt=prompt, model=model, json_mode=json_mode)
    return result
```

`transform_file()` calls `_transform_core()` directly instead of `transform()`, and branches on the boolean instead of `result.startswith("Error:")`:

```python
    ok, result = _transform_core(data=in_content, prompt=prompt, model=model, json_mode=json_mode)
    if not ok:
        s.add(error="transform_failed")
        return result
    # ... proceed to write result to out_file, unchanged
```

This eliminates the false-positive risk (legitimate LLM output starting with the literal text "Error:" is no longer misclassified) while keeping `transform()`'s own external string-based contract byte-for-byte identical — no spec change needed for `transform()`'s "Error Handling" requirement, only the new scenario added to "File-Based Transformation" in this change's spec delta.

Alternative considered: have `transform_file()` catch a raised exception instead of checking a return tuple. Rejected — `transform()`'s existing contract explicitly promises it "SHALL NOT raise an exception" (see the unmodified "API error" scenario in `tool-llm/spec.md`); introducing an internal exception type for `_transform_core` while `transform()` still never raises adds an inconsistent internal control-flow style for no benefit over a plain tuple return.

## Risks / Trade-offs

- **[Risk] Renaming `brave.search`'s `count` breaks any caller relying on it, including 3 docstring examples inside `ot_llm.py` itself** → Mitigation: `tasks.md` enumerates every known call site found via `rg`; the verification section re-runs `rg -n 'brave\.search\(.*count='` across `src/` and `docs/` and requires it to return empty before the change is considered done.
- **[Risk] `mem.search(mode="pattern")` is a clean break with no equivalent of prefix-match rescue** → Accepted per the maintainer's explicit V3 no-alias-fallback rule; documented in proposal.md as BREAKING.
- **[Risk] The `read_only` first-keyword check can be bypassed by SQL injection tricks that don't start with a write keyword (e.g. a `SELECT` that triggers a side-effecting subquery, or dialect-specific write syntax)** → Accepted: the report's decided scope is a docs-truth guard ("makes the corrected db docs safety story real"), not a hardened SQL sandbox. Out of scope to build a full SQL-injection-proof allowlist parser here.
- **[Risk] Renaming `_search_pattern` → `_search_keyword` in `_mem/search.py` touches a private helper with no test coverage of its own** → Low risk: it's called only from within the same file (`search()` dispatch and `_search_hybrid()`), both of which are exercised by existing `mem.search(mode=...)` tests that will be updated in this change; a rename-with-no-remaining-reference would surface as an immediate `NameError` at import/call time, caught by `just check`.
- **[Trade-off] `ot_llm.transform_file` fix (D6) is optional** → If capacity does not allow it, all four required items (D1-D5) still ship independently; do not let D6 block completion of the rest of the change. If D6 is skipped, remove its task-group and its spec delta file (`specs/ottools/tool-llm/spec.md`) before completing the change — do not leave an un-implemented spec delta behind (per repo convention, delta specs describe *landed* behavior).

## Migration Plan

No data migration, no runtime feature flag, no rollout sequencing needed — these are five independent, synchronous code + doc + spec + test edits, each completed in a single commit-sized unit of work. Order does not matter across D1-D6; they touch disjoint files. Within each item, code changes and their tests/docs/spec updates land together (not as separate follow-up commits), so `just check` is green at every intermediate commit if the implementer chooses to commit per-item.

Rollback: revert the specific item's commit(s). Since there is no shared state or migration, reverting D1 does not affect D2-D6 or vice versa.

## Open Questions

- **"Batch `transform` parity" (report's optional-item phrase, `wip/release-v3/release-v3-report-2.md:240`)**: no batch-transform function exists anywhere in `src/ottools/ot_llm.py` (`__all__` is only `["transform", "transform_file"]`; confirmed via `grep -n "^def " src/ottools/ot_llm.py` at time of writing this design). This is flagged as **anchor drift** per the source brief's instruction to flag (not silently fix) drift — the phrase does not map to any current code. Do not invent a batch-transform feature to satisfy this phrase; it is out of scope for this optional item as written. If a future report clarifies the intent, it belongs in a new change.
