## Why

Agent-visible documentation actively misleads today: `db.md` claims queries are
read-only when `db.query()` runs arbitrary SQL under AUTOCOMMIT; `package.audit`
docs name a parameter (`packages`) that does not exist on the function (real
param is `path`) and call it a "security audit" when it is version-staleness
only; ~18 whiteboard docstring examples and 6 webfetch docstring examples call
functions in ways that raise `NameError`/`TypeError` if copy-pasted; two
`ot.help()` doc links 404 (`doc_slug` mismatches the published URL); the
whiteboard `draw()` docstring contradicts itself about how many shapes it
supports; `ground.search()` raises an unformatted `ImportError` if
`google-genai` is missing instead of returning the pack's normal error string;
`kb.search()` surfaces a raw internal error instead of an actionable message
when embeddings are missing or disabled. Separately, the install docs still
say Python 3.11 against a `pyproject.toml` floor of `>=3.12`; a CLI hint
prints the wrong PyPI package name (`onetool[scrape]` instead of
`onetool-mcp[scrape]`); the README states two different tool counts on the
same page; and the marketing claims file states different token-count numbers
than the benchmark doc it's sourced from. None of this requires new behavior
to design — it requires making the already-shipped behavior and the
already-collected benchmark data match what the docs say.

Two items in this sweep are small code bugs, not just prose fixes: `ground.py`
lets an `ImportError` escape its own error formatter, and `kb.search()`
surfaces a raw `sqlite-vec`/SQL error instead of following the friendly
guidance pattern `mem.search()` already uses. Both get code fixes + tests
alongside the doc fixes.

## What Changes

- Fix `docs/reference/tools/db.md`'s false "read-only by default" claim and
  `db.query()`'s docstring return-type description to match actual behavior.
- Fix `docs/reference/tools/package.md`'s `package.audit` parameter name and
  mislabeled "Security audit" description.
- Fix 6 keyword-only-called-positionally webfetch docstring examples that
  would raise `TypeError` if copy-pasted.
- Fix two `doc_slug` values (`db`, `webfetch`) so `ot.help()`-generated doc
  links resolve instead of 404ing.
- Fix the whiteboard `draw()` docstring's self-contradiction about supported
  shapes.
- Surface `ot.help(ask=...)` and `ctx.ask()` in their pack docs' Highlights
  sections (both are implemented but undersold in the docs).
- Add a "relationship to the proxied server's own tools" section to
  `chrome-util.md` and `play-util.md`.
- **BREAKING (message text only, not a contract)**: fix `ground.py`'s
  missing-`google-genai` `ImportError` so it no longer escapes the tool's
  error formatter — it now returns the same kind of formatted error string
  every other `ground.*` failure returns, instead of raising uncaught.
- Add missing-embeddings guidance to `kb.search()` (mirrors the existing
  `mem.search()` pattern): a disabled or ungenerated embeddings index now
  returns a clear, actionable message instead of a raw internal error.
- Bump documented Python floor from 3.11 to 3.12 across
  `docs/learn/installation.md` and `README.md`, matching
  `pyproject.toml`'s `requires-python = ">=3.12"`; state the Python 3.12+ /
  uv prerequisite explicitly; restructure `installation.md` to lead with the
  recommended install command instead of the prerequisite walkthrough.
- Fix the wrong PyPI package name in `src/onetool/kb.py`'s scrape-extra
  install hints (`onetool[scrape]` → `onetool-mcp[scrape]`).
- Standardize README.md on one tool-count figure (currently states both
  "100+" and "230+" on the same page) and add `ot.status` to the README's
  `ot` pack row (it's already documented as a function but missing from the
  summary table).
- Add `pyrage`/`keyring` to `ot_secrets.md`'s dependency disclosure and fix
  a guidance-drift bug where `ot/config/secrets.py`'s missing-dependency
  `ImportError` told the user to run a reinstall command that doesn't name
  the actual missing package (`pip install onetool-mcp`), while
  `ot_secrets.py`'s own equivalent check correctly names the package
  (`pip install keyring` / `pip install pyrage`) — unify on the specific
  form.
- Reconcile `dev/project/brand/claims.md`'s token-count numbers with its own
  cited source, `docs/learn/comparison.md`, which now reports different
  (correct, current) numbers; date-stamp the claim and note the benchmark
  harness now lives outside this repository.
- Document that root-level `env:` in `onetool.yaml` broadcasts to every
  proxied stdio server (a supply-chain consideration when mixing trusted and
  untrusted proxied servers); note the Direct API's same-user trust boundary.

## Capabilities

### New Capabilities

(none — this change corrects existing documentation and error-handling
behavior against already-established contracts; no new capability surface is
introduced)

### Modified Capabilities

- `_nf-docs`: extends "Tool Reference Accuracy" and "Security And Privacy
  Disclosure" with concrete, previously-unverified scenarios (doc-link
  resolution, db/package doc accuracy, webfetch example correctness,
  whiteboard docstring consistency, chrome/play proxy-relationship
  disclosure, root `env:` broadcast disclosure); adds new requirements for
  install-prerequisite accuracy, undersold-capability surfacing, canonical
  tool-count consistency, and marketing-claims traceability.
- `otutil/tool-ground`: extends "Error Handling" with a scenario covering the
  missing-`google-genai`-dependency case, which today bypasses the
  requirement's own formatting contract.
- `knowledge-pack`: adds a new requirement for `kb.search()` missing/disabled
  embeddings guidance (parallel to the existing "Error handling — missing
  sqlite-vec" requirement, which covers a different failure mode — the
  package not being installed at all).

## Impact

- **Affected files (docs)**: `docs/reference/tools/db.md`,
  `docs/reference/tools/package.md`, `docs/reference/tools/ot_core.md`,
  `docs/reference/tools/ot_context.md`, `docs/reference/tools/chrome-util.md`,
  `docs/reference/tools/play-util.md`, `docs/reference/tools/ot_secrets.md`,
  `docs/learn/installation.md`, `docs/reference/cli/onetool-config.md`,
  `README.md`, `dev/project/brand/claims.md`.
- **Affected files (code, docstrings only unless noted)**:
  `src/otdev/tools/db.py` (docstring + `doc_slug`),
  `src/otdev/tools/webfetch.py` (docstring examples + `doc_slug`),
  `src/otdev/tools/excalidraw.py` (docstring only — the shape line; does
  **not** touch `pack_aliases`, which is p17's),
  `src/onetool/kb.py` (CLI hint string, 2 lines),
  `src/ot/config/secrets.py` (error message string, 2 lines — plus 2 existing
  test assertions in `tests/unit/core/test_secrets.py` that pin the old
  string),
  `src/otutil/tools/ground.py` (moves 2 lines inside a `try:` block — behavior
  fix, not just docs),
  `src/otutil/tools/_knowledge/retrieval.py` (`search()` gains an early-return
  guard — behavior fix, not just docs).
- **Dependencies on sibling changes** (do not implement these here — mention
  only):
  - `p17-pack-api-consistency` owns the `excalidraw` pack-alias addition (the
    "18 whiteboard docstring examples use `excalidraw.` prefix" item is
    **not** in this change) and the `db.query(read_only=True)` guard. This
    change's `db.md` fix is written to work standing alone (it corrects the
    false "read-only by default" claim without asserting a guard param that
    may not exist yet); if p17 lands first, `db.md` additionally documents
    the guard (see task 1.1 for the exact conditional).
  - `p16-extras-restructure` owns the extras-naming outcome (`[whiteboard]`
    extra removal, `pydoll` moving into `[util]`). This change's tool-count
    and package-name fixes do not depend on extras naming and are safe to
    land independently.
  - `p14-guided-encrypted-secrets` owns the missing-secret-key error-string
    extension (`packages/onetool-pack/src/otpack/http.py:148,163`,
    `"Error: {SECRET} secret not configured"`) — a **different** string from
    the guidance-drift fix in this change (`ot/config/secrets.py`'s
    missing-`keyring`/`pyrage`-package `ImportError`). No overlap.
  - `p15-install-flow-and-mcp-config` owns `installation.md:37-73` (the
    `## Install` section) and `:146-167` (`## MCP Configuration`), which it
    rewrites around a bootstrap installer and `onetool init mcp-config`;
    its own task 5.5 explicitly excludes the Python-version prerequisite
    lines (`installation.md:3,11,19,26,33`) as this change's territory.
    This change therefore does **not** attempt to reorder
    `installation.md`'s sections (a "lead with the recommended install"
    reorder would collide with p15's rewrite of the same lines) — it only
    fixes the Python version number, and lets p15's rewrite of `## Install`
    naturally become the page's lead section.
  - `p14-guided-encrypted-secrets` owns adding `pyrage`/`keyring` to
    `ot_secrets.md`'s Requires section (its own task 14.1, as part of
    rewriting that page for its new `set`/`get` tools) — this change does
    **not** duplicate that edit. This change's `ot_secrets`-adjacent work is
    limited to the guidance-drift fix in `ot/config/secrets.py:116,124`
    (missing-package `ImportError` text), which is a different pair of
    lines from anything p14 touches in that file (p14 touches
    `config/secrets.py:129-132,137`).
  - `p16-extras-restructure` also edits `chrome-util.md`/`play-util.md`
    (Chrome-launch-flag guidance in `## Requires`) and
    `p31-demos-and-positioning` documents the same chrome/play-as-proxy-
    companion framing inside its new `docs/learn/mcp-proxy.md` walkthrough
    (cross-referencing, not duplicating, the reference pages). This
    change's chrome/play task is written to check for existing content
    before inserting, and to anchor on section boundaries rather than
    exact current text, so it is safe regardless of landing order relative
    to p16.
  - `p22-technical-foundation` also edits `src/otutil/tools/ground.py`
    (hoisting shared helpers `_validate_batch_retry_controls`,
    `_format_sources`, `_extract_structured_data` to `otpack`, at
    different line ranges: `:76,118,288,299,608`) and
    `src/otutil/tools/_knowledge/retrieval.py` (adding an untrusted-content
    system message to `_synthesise()`, a different function from this
    change's `search()` edit). Both changes touch the same two files in
    non-overlapping regions — a possible merge-order concern, not a scope
    conflict.
  - `p11-skills-standard-layout` also edits `docs/reference/tools/ot_core.md`
    (removing the `ot.skills` Functions-table row at line 30 and trimming
    the `info` parameter's discovery-function list at line 57). This
    change's `ot_core.md` edit is in the Highlights section near the top of
    the file — a different region.
  - `p31-demos-and-positioning` explicitly defers claims reconciliation to
    this change (confirmed in the wave map: "claims reconciliation is
    p18's") and does not edit `dev/project/brand/claims.md`; its own
    `comparison.md` edit adds a new positioning subsection near the
    benchmark tables without changing the numbers this change reads as the
    source of truth.
- **No version bump, no schema change, no new dependency.**
