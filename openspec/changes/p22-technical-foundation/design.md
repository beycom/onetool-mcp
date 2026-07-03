## Context

Three parallel V3 reviews (security, architecture/maintainability, performance) fact-checked the
OneTool codebase against its own documentation and found the core sound but flagged seven items in
this change's scope, verified against `main`@`151a52b3` (2026-07-04):

- **S1** — `dev/project/arch/security-model.md:34-42` overclaims the `exec()` sandbox.
- **S2** — Two LLM call families lack an untrusted-content system boundary.
- **S3** — Secret-shaped literals in commands/prepared-code/errors reach logs unredacted, through
  more than one logging code path (see Decision 3 below — this was found during verification and
  widens the fix beyond the report's literal citation).
- **M1** — Byte-identical/near-identical helper functions duplicated across `brave.py`, `tavily.py`,
  `ground.py` with no shared-code channel except `otpack`.
- **M2** — Frontmatter parsing duplicated in up to four places; two of the four are deleted by
  `p11-skills-standard-layout` (Wave 1), leaving two for this change to consolidate.
- **M3** — `src/ot/display/` is dead `__pycache__`/`assets` from an already-removed feature.
- **M5** — `tests/conftest.py`'s marker-enforcement gate silently skips instead of failing.

V3 is the designated breaking window for shared/public-surface renames and removals: no compatibility
shims, no deprecation aliases.

## Goals / Non-Goals

**Goals:**
- Make `dev/project/arch/security-model.md` truthful about the `exec()` trust boundary.
- Add a real (testable) untrusted-data system-message boundary to every helper-LLM call that
  currently lacks one, without changing the observable response contract of `kb.ask()`, `ctx.ask()`,
  or `mem.ask()`.
- Make secret-shaped literals unrenderable in emitted logs regardless of which logging code path
  (`LogSpan` or direct `LogEntry`) produced them.
- Delete duplication that has already drifted once (search-pack helpers) or is at risk of drifting
  (frontmatter parsers), consolidating into the one channel (`otpack`) that isolated-subprocess packs
  can actually share code through.
- Delete verified-dead code (`src/ot/display/`).
- Make the test-marker gate fail loud instead of failing silent.

**Non-Goals:**
- Building an actual exec() sandbox, narrowing the builtins allowlist, or adopting a Monty-style
  sandbox — explicitly deferred to V4 (see Deferrals) and out of scope here; S1's only action is the
  doc fix.
- Any of R8's P1-P4 (event-loop offload, memoize cache bound, serialization perf, double AST parse) —
  owned by `p12-core-flow-hardening`.
- M4 (god-module splits) — explicitly deferred post-V3.
- M6 (dependency refresh) — owned by `p32-dependency-refresh`.
- Repurposing `_build_pack_summary()`/`{pack_summary}` in `src/ot/server.py:208-237` — owned by
  `p21-run-contract-and-command-index`. This change's M3 scope is strictly `src/ot/display/` deletion.

## Decisions

### Decision 1 — S1: doc-only fix, no code change, no builtins narrowing

**Decision**: Rewrite only the Layer 3 section of `dev/project/arch/security-model.md`. Do not touch
`runner.py`'s `__builtins__` exposure or `validator.py`'s allowlist/subscript-bypass logic.

**Rationale**: Maintainer ruling (recorded in the source report) is that OneTool is intentionally not
a sandbox — a real exec sandbox was evaluated pre-V1 and dropped as added complexity. The security
boundary is process/user/environment isolation for a trusted local user. The bug is the doc's false
claim, not the implementation. Changing the implementation now would be scope creep against an
explicit maintainer decision.

**While rewriting Layer 3, also check (same task, not a separate line item)**: Layer 2's example
`security.yaml` snippet in the doc shows `calls: block: [pickle.*, subprocess.*]`, but the shipped
`src/ot/config/global_templates/security.yaml` has no `calls:` key at all (verified: the shipped file
only has `builtins`, `imports`, `dunders`, and `sanitize` keys). If the Layer 2 example is left as-is
while Layer 3 is corrected for truthfulness, the doc still contains one inaccurate claim immediately
adjacent to the fixed section. Either update the Layer 2 example to match the shipped config, or add
a note that it is illustrative and not the shipped default. Do not expand this into changing the
shipped `security.yaml` itself — that's a behavior change outside S1's scope.

**Alternative considered and rejected**: Narrow the builtins to a curated allowlist now, as a "belt
and suspenders" hardening alongside the doc fix. Rejected because the report explicitly defers this
to V4 pending a threat-model change, and doing it here would require a compatibility-breaking pass
over every existing glue script that currently relies on the full builtin set — undocumented,
untested scope this change does not own.

### Decision 2 — S2: two independent boundary fixes, not one shared helper

**Decision**: Fix the untrusted-data system message in two places independently:
1. `ottools/ot_llm.py::transform()`'s existing system prompt (extend the string).
2. `otutil/tools/_knowledge/retrieval.py`'s `_synthesise()` and `_llm_rerank()` (add a `system`
   message where none exists — currently both build a single `user`-role message).

**Rationale**: These are separate code paths with separate LLM clients (`transform()` uses
`ottools.ot_llm`'s cached `OpenAI` client; `retrieval.py` uses its own `_get_llm_client()`). Report
confirms `transform()` backs both `ctx.ask()` and `mem.ask()` (verified: `src/ot/ctx/ask.py` and
`src/otutil/tools/_mem/ask.py:106` both call `ottools.ot_llm.transform`), so fixing `transform()`
covers those two callers for free. `kb.ask()` does not call `transform()` — it calls
`_synthesise()`/`_llm_rerank()` directly — so it needs its own fix.

**Alternative considered and rejected**: Extract a single shared `build_untrusted_boundary_message()`
helper used by both call sites. Rejected for this change because the two call sites live in different
packages under different import-boundary rules (`ottools` is core; `otutil/tools/_knowledge` is a
pack) and the actual boundary text is short enough (2-3 sentences) that a shared helper adds an import
dependency for no real duplication savings. If a third call site needing this boundary appears later,
revisit.

### Decision 3 — S3: redaction must cover both the LogSpan and direct-LogEntry logging paths

**Decision**: Add `src/ot/logging/redact.py` with the ten regex patterns moved verbatim from
`src/otutil/tools/_mem/config.py:18-29` (`_BUILTIN_REDACTION_PATTERNS`) and a `redact_secrets(value:
str) -> str` function. Wire it into **two** places, not one:
1. `sanitize_for_output()` in `src/ot/logging/format.py` — call `redact_secrets()` on every string
   value (not just URL-named fields), in addition to the existing URL-credential masking. This covers
   the `LogSpan` path (`span.py:54` calls `format_log_entry` → `sanitize_for_output` on exit).
2. `LogEntry.__str__()` in `src/ot/logging/entry.py` — currently this method JSON-dumps
   `self._fields` directly with **no** call into `format_log_entry`/`sanitize_for_output` at all.
   Change `__str__()` to build its output through `format_log_entry(self.to_dict(), verbose=
   is_log_verbose())` (the same call `span.py:54`'s `_format_for_output()` already makes), matching
   the existing lazy-import pattern in `span.py` (`from ot.config import is_log_verbose` inside the
   method body, to avoid a circular import — `span.py:50-51` already does this) — rather than
   reimplementing redaction separately in `__str__`.

**Why this is not scope creep**: The report's own anchor for S3 is `src/ot/executor/runner.py:606-624`
— that line range spans *both* the `LogSpan(span="runner.execute", command=..., ...)` context manager
(lines 606-614) *and* the immediately following direct `logger.debug(LogEntry(event=
"runner.execute.prepared", preparedCode=stripped, ...))` call (lines 615-624). Verification during
design showed the second call bypasses `format_log_entry` entirely today — it is not a hypothetical
gap, it is the literal code the report cited. Fixing only `format_log_entry`/`sanitize_for_output`
would leave the `preparedCode` field — the exact field named in the report — unredacted. Routing
`__str__()` through `format_log_entry` is the minimal fix that actually closes the anchor's gap.

**Side effect to note, not fix separately**: Because `LogEntry.__str__()` currently has no truncation
or URL-credential masking either (only `format_log_entry` had that, and only `LogSpan` called it),
routing `__str__()` through `format_log_entry` also gives direct `logger.debug(LogEntry(...))` calls
truncation and URL masking for the first time. This is a beneficial, in-scope consequence of unifying
the two paths through one sanitization funnel — do not attempt to preserve the old unformatted
behavior for `__str__()`.

**`_mem` pack behavior must not change**: `src/otutil/tools/_mem/content.py:64` currently imports
`_BUILTIN_REDACTION_PATTERNS` from `_mem/config.py` to redact secrets in *stored memory content* at
write time (`mem.write()`) — this is `openspec/specs/ottools/tool-mem/spec.md`'s existing "Secret
Redaction" requirement, unrelated to logging. When the patterns move to `ot.logging.redact`, update
`_mem/config.py`/`_mem/content.py` to import from the new shared location, but do not change
`mem.write()`'s observable redaction behavior (same patterns, same replacement strings, same
`redaction_enabled` config toggle). No spec change is needed for `tool-mem` — this is a pure
implementation relocation. Existing `mem.write()` redaction tests must still pass unmodified.

### Decision 4 — M1: hoist by generalizing signatures, not by picking one file's version

**Decision**:
- `_validate_batch_retry_controls(retries: int, retry_delay_ms: int) -> str | None` is byte-identical
  across `brave.py:406`, `tavily.py:455`, `ground.py:76` (diff-verified) — move it verbatim to
  `otpack.batch`, delete all three local copies, update call sites to import it.
- `_format_sources()` in `brave.py:136` and `tavily.py:188` are functionally identical (docstring
  differs slightly); `ground.py:304`'s version indexes `source["url"]` directly instead of
  `source.get("url", "")` and uses different local variable names but the same dedup/numbering logic.
  Add `otpack.text.format_sources(results, *, max_sources=None) -> str` using `.get()` access
  (matching brave/tavily's more lenient behavior); update all three call sites. Flag in the task: this
  changes `ground.py`'s behavior from raising `KeyError` on a source dict missing `"url"` to silently
  treating it as absent — verify (by reading `ground.py`'s source-dict construction) that `"url"` is
  always present before treating this as safe, and note the finding either way.
- `_create_http_client()`/`_build_client()` differ in `base_url`, `timeout`, and `headers` per pack —
  add `otpack.http.create_json_http_client(base_url: str, *, timeout: float | httpx.Timeout, headers:
  dict[str, str] | None = None) -> httpx.Client` as a parameterized factory; each pack calls it with
  its own config and continues to wrap the result in the existing `otpack.factory.lazy_client()`.
- `_extract_structured_data()` in `ground.py:118` and `tavily.py:329` are identical except: (a)
  `ground.py` does `sources[0]["url"]`, `tavily.py` does `sources[0].get("url")`, and (b) `tavily.py`
  additionally computes `confidence = sources[0].get("score")` and threads it into `provenance[name]
  ["confidence"]`, while `ground.py` always sets `"confidence": None`. Add
  `otpack.text.extract_structured_data(*, text, sources, extract_schema, return_provenance,
  confidence_key: str | None = None) -> dict[str, Any]` where `confidence = sources[0].get
  (confidence_key) if (confidence_key and sources) else None` and `source_url = sources[0].get("url")
  if sources else None` (using `.get()` uniformly — same `ground.py` behavior-change caveat as
  above). `ground.py` calls it with `confidence_key=None` (default); `tavily.py` calls it with
  `confidence_key="score"`.

**Rationale**: `otpack` is documented as the only shared-code channel for these isolated-subprocess
packs (M1's own stated rationale in the source report). Parameterizing rather than picking one
pack's version preserves each pack's existing observable behavior (verified via each pack's existing
unit tests, which must still pass unmodified after the hoist) while eliminating the duplication.

**Alternative considered and rejected**: Leave `_extract_structured_data` and `_format_sources`
pack-local since they are "near" not "byte" identical, and only hoist the byte-identical
`_validate_batch_retry_controls`. Rejected — the report explicitly lists all four functions as an M1
target ("value 8"), and the near-identical functions are exactly the ones most likely to silently
drift further (as `_validate_batch_retry_controls` almost certainly did originate from a single
copy-paste that then diverged in the other two). Hoisting now, while the divergence is still small and
diffable, is cheaper than hoisting later.

### Decision 5 — M2: target `otpack.text`, wait on p11, verify precondition rather than assume it

**Decision**: Add `otpack.text.parse_frontmatter(content: str) -> tuple[dict[str, Any], str]` using
the regex + `yaml.safe_load` fallback path already proven in `src/otutil/tools/_knowledge/chunker.py`
(lines 52-61) — not the optional `python-frontmatter` library path (lines 44-51), since `otpack`'s
dependencies are `loguru`, `httpx`, `pydantic`, `pyyaml` only, and adding `python-frontmatter` as a new
otpack dependency is unnecessary when the regex+`pyyaml` fallback already handles the same frontmatter
format losslessly for this codebase's use (YAML `---`-delimited blocks). Update `chunker.py` and
`ot_forge.py` to import `parse_frontmatter` from `otpack.text` and delete their local
`_parse_frontmatter`/inline-parsing implementations.

**Precondition check (mandatory, first task in this group)**: Before touching `chunker.py` or
`ot_forge.py`, verify `src/ottools/skills.py` and `src/ot/meta/_skills_services.py` no longer exist
(both are `p11-skills-standard-layout`'s deletion targets, Wave 1, which this change depends on). If
either file still exists, **stop this task group and report** — do not proceed with a partial
consolidation or work around the missing precondition by also deleting those files here (that is
`p11`'s job, not this change's).

**Rationale**: `otpack` can be imported freely by `ot_forge.py` (core, same-process) and by
`chunker.py` (an `otutil` pack) — the import-boundary restriction runs one way: `otpack` itself must
not import `ot.*` (except `config`/`logging`), but core/pack code may always import `otpack`. This
matches the pattern already established by `otpack.factory.lazy_client` being used across
`brave.py`/`tavily.py`/`ground.py`.

### Decision 6 — M3: delete only `src/ot/display/`; do not touch `_build_pack_summary`

**Decision**: `rm -rf src/ot/display/`. Nothing else.

**Verification before deleting**: confirm (already done during design verification) that
`src/ot/display/` contains only `__pycache__/*.pyc` and `assets/__pycache__/*.pyc` — no `.py` source
files — and that no source file anywhere in `src/`, `tests/`, `docs/`, `openspec/`, or `dev/`
references `ot.display` or `ot/display` (a grep for `react-dom` build artifacts under
`src/ottools/_panel/app/node_modules/` will false-positive on the substring "display" in unrelated
minified JS — exclude `node_modules/` when checking).

**Explicit boundary**: `server.py:208-237`'s `_build_pack_summary()`/`{pack_summary}` is a live,
referenced function (not dead code) that `p21-run-contract-and-command-index` has already decided to
repurpose as the build-time generator for the ot-ref skill's pack-map section. Do not delete it, stub
it, or modify it in this change — even though it is a candidate for the same "M3 dead code" report
line, it is explicitly carved out to `p21` ownership in the wave map.

### Decision 7 — M5: reuse the existing `--allow-skips` contract instead of inventing a second one

**Decision**: `tests/conftest.py` already has a `require()` helper (lines 33-60) with a documented
contract: missing requirements **fail by default**, and only **skip** when `--allow-skips` is passed.
The marker-enforcement code in `pytest_collection_modifyitems` (lines 141-167) currently does neither
consistently — it unconditionally skips regardless of `--allow-skips`, contradicting the module's own
docstring ("By default, tests with missing requirements will error (fail fast)"). Change
`pytest_collection_modifyitems` to follow the same contract as `require()`: when a test is missing a
speed marker or component marker, **fail collection** (e.g. via `pytest.exit()` with a summary of
every offending test, or by turning the missing-marker case into a collection error) unless
`--allow-skips` was passed, in which case skip with a warning exactly as today.

**Alternative considered**: Add a separate CI-only gate script that runs `pytest --collect-only`,
parses skip counts, and fails the build if `skipped > 0`. Rejected as the primary fix (may still be
added as a defense-in-depth CI step, but is not a substitute) because it requires CI to specifically
invoke this extra script — a new contributor running `just test` locally without CI would still see
green output with silently skipped tests. Fixing the default behavior in `conftest.py` itself, using
the pattern already established by `require()` in the same file, makes local runs match the previously
documented (but not implemented) "fail fast" contract.

## Implementation guardrails

- **No compatibility shims or aliases.** V3 is a breaking window. When `_validate_batch_retry_controls`,
  `_format_sources`, `_create_http_client`, `_extract_structured_data`, and the frontmatter parsers
  move to `otpack`, delete the pack-local definitions completely — do not leave a
  `from otpack.batch import validate_batch_retry_controls as _validate_batch_retry_controls` shim
  "for compatibility." Update every call site to the new name/location directly.
- **No stubbing or TODO-deferral.** If a task cannot be completed as specified — e.g. the M2
  precondition check finds `p11` has not yet deleted `skills.py`/`_skills_services.py`, or a search
  pack's existing unit tests fail after the M1 hoist because behavior genuinely changed — stop and
  report the blocker. Do not comment out a failing test, do not leave a partial hoist with one pack
  still on its local copy, and do not add a `# TODO: fix later` marker in place of the fix.
- **Every code task includes tests.** Unit tests (`@pytest.mark.unit`) for pure functions (redaction,
  frontmatter parsing, batch-retry validation, source formatting, structured-data extraction); the
  existing search-pack, mem, knowledge, and llm test suites must still pass unmodified after the
  refactors in this change. `just check` (lint + typecheck + test) MUST pass before any task in this
  change is marked complete.
- **Every `rg` acceptance check that must return empty MUST actually be run**, and its output pasted
  or reproduced in the task's completion evidence — not asserted from reading the diff. This applies
  in particular to `rg "_validate_batch_retry_controls" src/otutil/tools/` (must show only the new
  import, not a redefinition) and `ls src/ot/display` (must fail / show nothing).
- **Anchor drift**: all file:line anchors in this design and in `tasks.md` were verified against
  `main`@`151a52b3` (2026-07-04) by direct `Read`/`grep`, not copied blind from the source report. No
  drift was found during this verification pass — every anchor cited matched the report exactly. If a
  later anchor has drifted by the time this change is implemented (e.g. a line shifted because of an
  unrelated intervening commit), re-locate the target by function/symbol name, note the drift in the
  task's completion evidence, and proceed — do not silently skip the task because the line number no
  longer matches exactly.

## Risks / Trade-offs

- **[Risk]** Routing `LogEntry.__str__()` through `format_log_entry` (Decision 3) changes the output
  shape of every direct `logger.debug(LogEntry(...))` call site in the codebase (adds truncation and
  URL masking that weren't applied before) → **Mitigation**: this is intentional and in-scope (see
  Decision 3's rationale); run the full test suite and specifically check
  `tests/unit/core/test_log_format.py`, `tests/unit/core/test_runner_logging.py`, and
  `tests/unit/serve/test_mcp_logging.py` for any test asserting the old unformatted `__str__` output
  and update those assertions to expect the formatted/redacted output instead.
- **[Risk]** Generalizing `_format_sources`/`_extract_structured_data` to use `.get()` uniformly
  (Decision 4) changes `ground.py`'s behavior from a `KeyError` on a malformed source dict to a
  silent `None`/empty value → **Mitigation**: explicitly called out as a task-level check in Decision
  4; verify `ground.py`'s source-construction path always populates `"url"` before treating the
  behavior change as safe, and note the finding in the task's completion evidence either way.
- **[Risk]** M2's precondition (p11 having deleted `skills.py`/`_skills_services.py`) may not hold if
  waves are implemented out of order → **Mitigation**: explicit precondition check as the first M2
  task (Decision 5); stop-and-report contract, no silent workaround.
- **[Trade-off]** M5's fix (fail-by-default on missing markers) will break `just test` locally for
  anyone with an in-flight branch containing an unmarked test, immediately upon merge → accepted:
  that is the entire point of the fix (the gap it closes is exactly "a typo'd marker means the test
  silently never runs"), and `--allow-skips` remains available as an explicit opt-out for anyone who
  needs to keep working through it.

## Migration Plan

No user-facing migration — every item in this change is either a documentation correction, an
internal-only API relocation (no public tool-facing contract changes), a logging-behavior tightening,
or dead-code deletion. No `onetool.yaml`/`security.yaml`/`secrets.yaml` schema changes. No rollback
plan beyond standard git revert, since nothing here is a one-way data migration.

## Open Questions

None outstanding — all decisions above were resolved during design verification against the current
`main` branch. The one dependency that could block implementation (M2 on `p11`) has an explicit
stop-and-report contract rather than an open question.
