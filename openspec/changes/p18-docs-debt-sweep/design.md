## Context

This change is a docs-correctness sweep plus two small, contained code fixes
that were folded in because they're the same "docs actively mislead the
agent" class of bug (an error message that should be helpful but isn't). It
was verified against `main`@`151a52b3` (2026-07-04), which is also this
repo's current `HEAD` at proposal time — all anchors below were re-checked
against the live files, not copied blind from the source report.

**Anchor drift found during verification** (the source report's line numbers
were correct at the time it was written but the file has since moved or the
exact line shifted slightly — flagged per the verification instructions,
not silently corrected):

- The report cites `src/otdev/tools/_inject_base.py:102-133` for the
  chrome/play "proxy relationship" evidence. The actual file is
  `src/otdev/_inject_base.py` (one directory up — not under `tools/`). The
  cited line range (102-133, `_extract_js`/`_exec_js` calling
  `get_proxy_manager().call_tool_sync(server, tool, ...)`) is correct at
  that corrected path.
- The report cites `src/ot/config/secrets.py:131` and `src/ottools/ot_secrets.py:126`
  for the guidance-drift item. The actual lines are `secrets.py:116,124`
  (the two `"Run: pip install onetool-mcp"` strings) and
  `ot_secrets.py:46,57` (the two `"Run: pip install keyring"` /
  `"Run: pip install pyrage"` strings this change aligns them with).

Everything else cited in tasks.md below was re-verified at the stated
line number.

**Cross-change file co-touches found during verification** (checked against
every sibling change's already-written `tasks.md`/`specs/` at proposal
time — not scope violations, just noted so an implementer isn't surprised
by a merge conflict or an already-partially-edited file):

- `docs/reference/tools/ot_secrets.md` — `p14-guided-encrypted-secrets`
  already owns the `pyrage`/`keyring` Requires-section addition (its task
  14.1). This change does not duplicate it (see tasks.md section 14).
- `docs/learn/installation.md` — `p15-install-flow-and-mcp-config` owns
  lines 37-73 and 146-167 (Install + MCP Configuration sections). This
  change only touches the Python-version lines (3,11,19,26,33), which p15's
  own task 5.5 explicitly excludes as this change's territory.
- `docs/reference/tools/chrome-util.md` / `play-util.md` —
  `p16-extras-restructure` adds Chrome-launch-flag guidance to the
  `## Requires` section; `p31-demos-and-positioning` documents the same
  proxy-companion relationship in a new `docs/learn/mcp-proxy.md`
  walkthrough (not by editing these two files). This change's task 9 checks
  for existing content and anchors on section boundaries to stay safe
  regardless of order.
- `src/otutil/tools/ground.py` and `tests/otutil/unit/tools/test_ground.py`
  — `p22-technical-foundation` hoists shared search-pack helpers out of
  `ground.py` at different line ranges (`:76,118,288,299,608`) than this
  change's `_grounded_search()` fix (`:384-388`), and both changes run the
  full `test_ground.py` suite as part of their own verification.
- `src/otutil/tools/_knowledge/retrieval.py` — `p22-technical-foundation`
  adds an untrusted-content system message to `_synthesise()`; this change
  edits `search()`. Different functions, same file.
- `docs/reference/tools/ot_core.md` — `p11-skills-standard-layout` removes
  the `ot.skills` Functions-table row (line 30) and trims the `info`
  parameter list (line 57); this change adds one bullet to the Highlights
  section near the top of the file.

**Unresolved finding, reported but not fixed here** (see design.md
Decisions, "claims.md gets targeted numeric edits"): `claims.md:14-23`'s
"$30 per MCP server per month" claim cites "$485/month overhead" for 18
servers, which does not match either number in `comparison.md`'s
corresponding 3-shot monthly-impact section (`$395/month` total multi-mcp
cost, `$385/month` in pure waste). This may be a genuine additional
inconsistency, or it may reference a valid, separately-sourced number this
change's two named anchors (`claims.md:33-34` vs `comparison.md:7,19`)
don't cover. **Do not silently fix this** — it is out of this change's
verified scope; report it back to the user/maintainer as a follow-up
finding when this change is done.

## Goals / Non-Goals

**Goals:**
- Every doc page and docstring touched by this change matches the runtime
  behavior it describes, verifiably (via `rg`, `check_docs_registry.py`, or
  a new/updated test).
- The two code fixes (`ground.py` ImportError escape, `kb.search()` raw
  error surfacing) get the same treatment as any other bug fix: a minimal
  diff, a test that fails before the fix and passes after.
- `claims.md` and `comparison.md` say the same thing about the same
  benchmark run.

**Non-Goals:**
- No new tool parameters, no new tools, no schema changes. (`db.query(read_only=True)`
  is p17's; this change's `db.md` fix is written to be correct whether or
  not that guard exists yet — see task 1.1.)
- No excalidraw `pack_aliases` change (p17's).
- No extras/`pyproject.toml` changes (p16's).
- No installer/bootstrap/`mcp-config` content (p15's).
- No missing-secret-key error string changes in `otpack/http.py` (p14's) —
  only the *different* `ot/config/secrets.py` guidance-drift strings are in
  scope here.
- No new demos, no proxy walkthrough content, no ot-ref skill content
  (p31's / p21's).

## Decisions

**Decision: `db.md` documents the guard conditionally, based on a grep check,
not a judgment call.** Because `db.query(read_only=True)` is p17's guard and
the two changes may land in either order, task 1.1 specifies a literal
`grep -n "read_only" src/otdev/tools/db.py` branch: if the guard already
exists, document it; if not, only fix the false "read-only by default"
claim. This keeps the task fully deterministic for an implementer who has
no visibility into p17's status.

**Decision: standardize the README tool count on "240+", not the exact
validated "243".** `docs/reference/tools/index.md`'s header ("27 Packs. 243
Tools.") is kept in sync with the runtime registry by
`scripts/check_docs_registry.py` and is the source of truth, but README.md
is not covered by that script and drifts with every pack/tool addition.
Rounding down to "240+" gives the README headroom before it goes stale
again, while still being consistent with (not exceeding) the validated
count. `27+ packs` (already used at README.md:132) stays as-is.

**Decision: `kb.search()`'s missing-embeddings guard is a function-local,
lazy import, not a new module-level dependency.** `_db_embeddings_enabled()`
already exists in `src/otutil/tools/_knowledge/indexer.py:162` and is reused
via a lazy `from .indexer import _db_embeddings_enabled` inside `search()`,
matching the codebase's existing pattern of avoiding module-level
cross-imports between `retrieval.py` and `indexer.py` (checked: no circular
import risk either direction).

**Decision: the missing-embeddings guard checks config before opening a
connection, but the has-any-embeddings check happens after.** The
`embeddings_enabled: false` case is a pure config check — no DB needed, so
it returns before `get_connection()`. The "never generated" case requires
querying `chunks_vec`, so it happens inside the existing `try:` block after
the connection is open, but still before calling `search_hybrid`/`search_vec`
(which is where the raw error currently originates).

**Decision: claims.md gets targeted numeric edits, not a full rewrite.**
Only the "96% reduction in token usage" section (the one the report
identifies as contradicting `comparison.md`) is edited: the two data lines,
the section heading's rounded figures, the comparison table's bolded "96%"
cell (which would otherwise be newly inconsistent with the corrected body
text), and a new date-stamp/harness-location line. The separate "$30 per MCP
server per month" section (`claims.md:14-23`) cites a `$485/month` figure
that does not obviously match any single number in the current
`comparison.md` (which shows `$395/month` total multi-mcp cost and
`$385/month` in pure waste) — **this is flagged here as a follow-up finding,
not fixed in this change**, because its provenance could not be verified
from the two files this change's scope names (`claims.md:33-34` vs
`comparison.md:7,19`); it may reference a still-valid, separately-sourced
number not captured in `comparison.md`. Do not touch `claims.md:14-23` in
this change. Report the finding back to the user/maintainer instead.

**Decision: the `ground.py` fix relocates two lines; it does not restructure
`_grounded_search`.** `_require_google_genai()` and `from google.genai import
types` move from before `with LogSpan(...):` to be the first two statements
inside the existing `try:` block, so the existing `except Exception as e:
return _format_error(e)` catches the `ImportError` like every other failure
mode in that function. No other line changes.

## Risks / Trade-offs

- [Risk] The `db.md` conditional fix (task 1.1) could land with the
  guard-absent wording, then p17 lands afterward without anyone updating
  `db.md` to add the guard mention → **Mitigation**: proposal.md's Impact
  section flags the dependency explicitly; p17's own tasks.md (not this
  change's concern) should include a `db.md` touch-up if it lands second.
- [Risk] Rounding the README tool count to "240+" could itself go stale
  (e.g. count drops below 240 after a removal) → **Mitigation**: this is a
  one-time correction, not a generated value; the existing
  `check_docs_registry.py` gate does not cover README.md, so this is a
  known, accepted gap (out of scope to add README.md to that script here).
- [Risk] Editing `ground.py`'s control flow could change behavior for a
  currently-passing test that relies on `_require_google_genai` being
  called outside the `LogSpan` (e.g. asserting on span-absence) →
  **Mitigation**: task 7.2 requires running the full existing
  `tests/otutil/unit/tools/test_ground.py` suite, not just the new test,
  before considering the fix done.
- [Risk] Changing `ot/config/secrets.py`'s error strings breaks the two
  existing tests that pin the old text (`tests/unit/core/test_secrets.py:467,481`)
  → **Mitigation**: task 14.2 explicitly updates both `match=` assertions in
  the same commit as the string change.

## Implementation guardrails

- **No compatibility shims or aliases.** This is corrective doc/message-text
  work; nothing here is being renamed or deprecated, so this guardrail
  mostly doesn't apply — but if any task's fix would naturally suggest
  "keep the old text too, just in case," don't. Replace it outright.
- **No stubbing, no TODO-deferral.** If a task turns out to be blocked (e.g.
  a cited file:line no longer exists, or content contradicts what's
  documented here), stop and report the discrepancy — do not guess, do not
  leave a `TODO`, do not mark the task done with partial work.
- **Tests are part of every code task.** Tasks 7 (`ground.py`) and 8
  (`kb.search()`) are behavior changes, not docs — both require new
  `@pytest.mark.unit @pytest.mark.tools` tests, run alongside the full
  existing suite for their module. Docs-only tasks do not need new tests but
  their `rg`/link-check verification commands (in the Verification section
  of tasks.md) must actually be run and must actually pass — "I edited the
  file" is not "the outcome is achieved."
- **`just check` must pass before this change is considered complete.**
- **Every acceptance `rg` command listed in tasks.md's Verification section
  that is specified to return empty MUST be run and MUST return empty**
  before checking off the final verification task. If one doesn't, the
  underlying task isn't done yet, even if its own checkbox was checked
  earlier — go back and fix it.
- **Do not touch anything owned by a sibling change** (see proposal.md
  Impact's dependency list): no `pack_aliases` edits in `excalidraw.py`, no
  `pyproject.toml` extras edits, no `onetool init` / `mcp-config` content, no
  `otpack/http.py` error string, no demos/walkthrough content.
