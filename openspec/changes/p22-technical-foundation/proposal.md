## Why

Three parallel V3 reviews (security, architecture/maintainability, performance) found the OneTool
core to be sound, but flagged a set of "technical foundation" defects that are cheap to fix now and
expensive to leave for later: a developer-facing security doc that overclaims the `exec()` sandbox
(actively misleading anyone deciding whether to trust the tool), two LLM call sites that hand
untrusted retrieved/stored content to a model with no system-level "this is data, not instructions"
boundary, secret-shaped literals that can land in local logs unredacted, ~hundreds of lines of
byte-identical/near-identical code duplicated across three search packs with no shared-code channel
other than `otpack`, four drifted copies of frontmatter parsing, an orphaned dead-code directory, and
a test-marker gate that silently skips tests instead of failing when a marker is missing or wrong.
V3 is the designated breaking window for shared/public-surface changes, so this is the moment to fix
the doc-truth gap, wire the cheap hardening in, hoist the duplicated pack infrastructure into the one
channel packs can actually share code through, and delete what's already dead.

## What Changes

- **BREAKING (doc correction)** — Rewrite `dev/project/arch/security-model.md`'s Layer 3 section so
  it no longer claims the executor exposes "only allowlisted builtins" and excludes
  `eval`/`__import__`/filesystem/network access. State plainly that `exec()` is not a sandbox:
  validation blocks casual mistakes and known-dangerous imports/calls but does not contain a
  determined escape, and the security boundary is process/user/environment isolation for a trusted
  local user running a trusted agent session — not `exec()` itself. No code changes; this is a
  documentation-honesty fix.
- Add a system-message boundary that frames retrieved/stored context as untrusted, non-instructional
  data to the two LLM call families that currently lack one:
  - `ottools.ot_llm.transform()` (backs `ctx.ask()` and `mem.ask()`) — extend its existing system
    prompt.
  - `otutil.tools._knowledge.retrieval._synthesise()` and `_llm_rerank()` (used by `kb.ask()`) — add a
    system message where none exists today.
- Add a shared secret-literal redaction utility and wire it into the log-formatting path so that
  secret-shaped literals (API keys, tokens, passwords, connection strings) inlined into a command,
  prepared code, or an error message are redacted before they reach any emitted log line — including
  the direct `logger.debug(LogEntry(...))` call path that today bypasses the existing
  `format_log_entry` masking entirely.
- **BREAKING (internal API removal, not deprecation)** — Hoist the duplicated search-pack helper
  functions (`_validate_batch_retry_controls`, `_create_http_client`/`_build_client`,
  `_extract_structured_data`, `_format_sources`) out of `brave.py`, `tavily.py`, and `ground.py` into
  shared `otpack` helpers; delete the local copies (no compatibility re-exports).
- **BREAKING (internal API removal, not deprecation)** — Consolidate the remaining frontmatter parser
  duplicates (`_knowledge/chunker.py`, `ot_forge.py`) into one `otpack.text.parse_frontmatter()`;
  delete the local implementations. Depends on `p11-skills-standard-layout` having already deleted the
  other two duplicates (`src/ottools/skills.py`, `src/ot/meta/_skills_services.py`).
- Delete the orphaned `src/ot/display/` directory (stale `__pycache__`/`assets` from an already-deleted
  feature on `main` — not the `feature/display` branch).
- Fix the test-marker enforcement gate in `tests/conftest.py` so a test missing a speed or component
  marker fails (or is caught by a CI gate), rather than silently skipping while CI stays green.

## Capabilities

### New Capabilities
- `security-model-docs`: Documentation-accuracy requirements for `dev/project/arch/security-model.md`
  — verifies the doc's exec-boundary claims match the implementation (validated via `rg`/content
  checks, not runtime behavior).

### Modified Capabilities
- `ottools/tool-llm`: `transform()`'s system prompt requirement gains an untrusted-data framing
  clause (system message instructs the model to treat `data` as untrusted content and ignore
  instructions embedded within it).
- `knowledge-pack`: `kb.ask()`'s retrieval-augmented synthesis requirement gains an untrusted-context
  boundary — the LLM calls backing re-ranking and synthesis now send a system message that frames
  retrieved context as untrusted, non-instructional reference material.
- `_nf-observability`: The "Sensitive Data Protection" requirement's credential-masking scenario is
  extended from URL-embedded credentials only to also cover secret-shaped literals (API keys, tokens,
  passwords, connection strings) appearing anywhere in a logged field, not just fields named `url`.

## Impact

- **Affected code**: `dev/project/arch/security-model.md`; `src/ottools/ot_llm.py`;
  `src/otutil/tools/_knowledge/retrieval.py`; `src/ot/logging/format.py`; `src/ot/logging/entry.py`;
  new `src/ot/logging/redact.py`; `src/otutil/tools/_mem/config.py` and `_mem/content.py`;
  `src/otutil/tools/brave.py`, `tavily.py`, `ground.py`; `packages/onetool-pack/src/otpack/batch.py`,
  `http.py`, `text.py`; `src/otutil/tools/_knowledge/chunker.py`; `src/ottools/ot_forge.py`;
  `src/ot/display/` (deleted); `tests/conftest.py`.
- **Dependencies**: M2 (frontmatter consolidation) depends on `p11-skills-standard-layout` having
  already deleted `src/ottools/skills.py` and `src/ot/meta/_skills_services.py` — if those files still
  exist when this change is applied, stop and report rather than working around it.
- **Explicit non-scope (owned elsewhere, do not implement here)**:
  - R8 P1–P4 (event-loop offload, unbounded memoize cache, serialization perf, double AST parse) —
    owned by `p12-core-flow-hardening`.
  - R8 M4 (god-module splits: `excalidraw.py`, `file.py`, `cli.py`) — explicitly deferred post-V3, not
    implemented in this change.
  - R8 M6 (dependency lock refresh, `fastmcp>=3.4.1` floor bump, `lxml` major-bump evaluation) — owned
    by `p32-dependency-refresh`.
  - The `_build_pack_summary()` / `{pack_summary}` repurpose in `src/ot/server.py:208-237` — owned by
    `p21-run-contract-and-command-index` (do not touch; `src/ot/display/` deletion in this change is
    unrelated dead code, not the same thing).
  - S4 (root `env:` secrets broadcast to proxied servers) and S5 (Direct API key = full command
    execution) — both marked "V3 docs" / "accepted, no change" in the source report and assigned to
    R8's doc-notes bucket (`p18-docs-debt-sweep`), not this change.
- **No runtime dependency changes**: all fixes reuse existing dependencies (`re`, `pyyaml` already in
  `otpack`); no new packages.
