# Design: arch-generation-refactor

## Context

`src/otdev/tools/arch.py` (1,478 lines) is the facade for the `arch` pack. Its five public
tools (`validate`, `generate`, `export_yaml`, `import_yaml`, `bundle_solution`) are thin, but
the file also carries the whole generation pipeline: `_generate_solution` (lines 680–1009,
~330 lines), `_render_workbook_diagrams`, `_render_view_diagrams`, `_execute_render_engine`,
`_execute_render_jobs`, `_collect_workbook_diagram_specs`, and their helpers — ~900 lines of
orchestration that belongs in `_arch/`. Inside `_generate_solution`, the systems loop
(lines 763–870) and projects loop (lines 872–979) are near-clones (per-key view build → d2
write → render jobs → `_render_view_diagrams` → context build → HTML write). One layer down,
`_arch/system_model.py:805` `_build_system_block` and `:1386` `_build_project_system_block`
duplicate the same nesting logic, the project variant adding scope filtering and change-class
decoration.

Two behavioral gaps remain from the source issue (`wip/issues/1-new/
[spec-needed]-arch-pack-fixes.md`):

- `_generate_solution` deletes the entire `solution/` directory every run
  (`shutil.rmtree`, arch.py:720–721) and re-renders every diagram through the d2 subprocess —
  the dominant cost when iterating on a workbook.
- The validation warnings channel (`_arch/validate.py:385,392` — `"warnings": 0` /
  `"warnings": []`) exists in every payload but is never populated.

The quick fixes from the same issue (render timeout `_RENDER_TIMEOUT_SECONDS`, catch-alls on
`export_yaml`/`import_yaml`/`bundle_solution`) already landed in 495ce5e5/60ceaa8b and are out
of scope.

Unit tests (`tests/otdev/unit/tools/test_arch.py`, 3,133 lines) monkeypatch
`arch.subprocess.run` and read `arch._RENDER_TIMEOUT_SECONDS` — the extraction moves those
targets.

## Goals / Non-Goals

**Goals:**

- Facade `arch.py` shrinks to public tools + argument/config resolution (~500 lines);
  generation orchestration lives in a new `src/otdev/tools/_arch/generate.py`.
- One parameterized page-generation loop replaces the systems/projects clones; one block
  builder replaces `_build_system_block`/`_build_project_system_block`.
- `generate()` updates the solution directory incrementally: unchanged d2 renders are skipped,
  files are rewritten only when content differs, stale files are removed, and
  `force=True` restores full regeneration.
- `validate_entities` emits non-blocking warnings (`orphan_system`, `duplicate_name`,
  `self_interface`) through the existing warnings channel.
- No breaking changes: all existing parameters, payload keys, error codes, and rendered output
  content are preserved.

**Non-Goals:**

- No manifest/sidecar cache file; incrementality is derived from on-disk output state only.
- No invalidation on d2 CLI version or engine `cmd_template` changes (use `force=True`).
- No further split of `system_model.py`'s remaining responsibilities (graph build, d2
  building, report contexts) beyond the block-builder merge.
- No changes to `bundle`, `roundtrip`, `ingest`, `drawio`, or the config module.
- No new warning conditions beyond the three specified; the mechanism is extensible later.

## Decisions

### D1 — New module `_arch/generate.py`; shared payload helper moves to `_arch/models.py`

Move verbatim (public, un-underscored names since `_arch` is already private):
`_WorkbookDiagramSpec` → `WorkbookDiagramSpec`, `_collect_workbook_diagram_specs` →
`collect_workbook_diagram_specs`, `_build_model_payload` → `build_model_payload`,
`_clean_diagram_rows` → `clean_diagram_rows`, `_build_render_context`, `_template_context`,
`_execute_render_engine`, `_execute_render_jobs`, `_unsafe_id_error`, `_render_view_diagrams`,
`_render_workbook_diagrams`, `_generate_solution` → `generate_solution`, plus the constants
`_MAX_RENDER_WORKERS`, `_RENDER_TIMEOUT_SECONDS`, `_SAFE_ID_FRAGMENT_RE`,
`_UNSAFE_PATH_CHARS_RE`, `_validate_system_id_fragment`, `_validate_path_fragment`,
`_now_timestamp`.

`_error_payload` is used by both the facade (all five tools) and the moved orchestration;
`generate.py` must not import from the facade (layering), so `error_payload` moves to
`_arch/models.py` alongside `Issue`, and both `arch.py` and `_arch/generate.py` import it
from there. The facade keeps `_resolve_generation_profile`, `_resolve_drawio_export_toggle`,
and `_resolve_list_cell_separator` (argument/config resolution), and its `_arch.system_model`
import block collapses to the few names still used by `validate`/roundtrip paths.

*Alternative considered*: splitting render-engine execution into a separate `_arch/render.py`.
Rejected — `_execute_render_engine`/`_execute_render_jobs` are only called from the generation
pipeline; one module keeps the move mechanical and reviewable.

### D2 — Single parameterized page loop in `generate_solution`

The systems and projects loops differ only in: row source (`entities["sys"]` with
external-system skip vs `entities["project"]`), per-page key list (fixed levels
`(sys, app, cmp)` vs `project_stage_ids(...)`), view/d2 builders
(`build_system_view`/`build_system_d2` vs `build_project_view`/`build_project_d2`), output
stem (`{id}-{level}` vs `project-{id}-{safe_stage}`), page context builder
(`build_solution_system_context` vs `build_solution_project_context`), page name
(`system_page_name` vs `project_page_name`), and card extras (projects add `href`). Introduce
a small internal spec (frozen dataclass of callables + labels, e.g. `_PageKind`) and one
`_generate_pages(kind, ...)` routine; the two loops become two `_PageKind` instances. Card
lists keep their existing sort and field shapes so index rendering is byte-identical.

*Alternative considered*: leaving the loops and only extracting them. Rejected — the clones
are the main drift risk (the draw.io D1/D2 comments are already duplicated verbatim).

### D3 — Merged block builder with optional project scope

`_build_project_system_block` is a strict superset of `_build_system_block`: same
system/app/component nesting and linking, plus (a) child filtering by
`explicit_system_ids`/`included_app_ids`/`included_cmp_ids` and (b) `change_class`
decoration via `change_lookup`. Merge into one
`_build_system_block(*, system_id, level, graph, scope: ProjectScope | None = None)` in
`system_model.py`, where `ProjectScope` is a frozen dataclass carrying the four project
fields. `scope=None` reproduces current system behavior exactly, including the placeholder
rule difference: without scope, placeholder is `level == LEVEL_SYS or no children`; with
scope, placeholder starts as `level == LEVEL_SYS` and is re-set when filtering leaves no
children — the merged builder keeps both branches explicit. `_build_project_system_block`
call sites switch to the merged builder; no wrapper is kept.

### D4 — Incremental generation: content-compare + expected-file sweep, no manifest

- **No pre-clean**: drop the `shutil.rmtree(solution_dir)` (arch.py:720–721). All writes go
  through a `_write_if_changed(path, text) -> bool` helper (byte-compare against existing
  file; mkdir parents; returns whether it wrote).
- **Expected-file set**: generation already accumulates `generated_files`; the same paths
  (plus `index.html`) form the expected set. After a fully successful run, sweep
  `solution_dir` recursively, delete files not in the set, prune empty directories. On any
  error, no sweep runs — prior outputs are left in place (an improvement over rmtree-first,
  which destroyed outputs before failing).
- **Render skip rule** (generated system/project diagrams): a d2 render job is skipped when
  `not force` AND the newly built `.d2` text equals the existing `.d2` file AND the `.svg`
  exists AND the svg's draw.io-embed state matches the run's `drawio_export` toggle (detected
  by presence of the `content="..."` attribute, reusing the `_SVG_CONTENT_ATTR_RE` pattern
  from `system_model.py:785`). Skipped outputs reuse the existing `.svg` for `svg_markup`
  extraction and skip re-injection (the embedded mxfile derives from the same
  view/model as the d2 text, so an unchanged `.d2` implies an unchanged embedded model).
- **Workbook diagrams** (external source files, `_render_workbook_diagrams`): skipped when
  `not force` AND the output `.svg` exists AND its mtime is >= the source file's mtime
  (content-compare is impossible — the source is not copied into the output tree).
- **`force: bool = False`** on `arch.generate`, threaded through to `generate_solution` and
  `_render_workbook_diagrams`; `force=True` bypasses all skip checks and rewrites every file
  (semantically the old clean-slate run, without the delete-first window).
- **Observability**: `summary.renders = {"executed": N, "skipped": M}` is added to the
  `generate` success payload (additive) so tests and users can verify reuse.
- **HTML pages**: report pages embed `generated_at` timestamps, so they rewrite on every run
  by content-compare. Accepted — file writes are cheap; the incremental win is the d2
  subprocess renders. `files.solution` continues to list all current outputs, written or
  reused.

*Alternative considered*: a JSON manifest recording input hashes and render commands.
Rejected — a second source of truth that can desync from the directory; on-disk comparison
covers the dominant case (unchanged model rows between runs) with zero state.

### D5 — Warning production in `validate_entities`

`validate_entities` gains a parallel `warnings: list[Issue]` populated by a new
`_collect_warnings(entities, ...)` pass reusing the id sets already computed. Three
conditions, all reusing the existing `Issue` shape (`code`, `message`, `details` with
`sheet`/`row`/`id` keys):

- `orphan_system`: a `sys` row whose id appears in no interface `provider`/`consumer`
  (directly or via an owned app/component endpoint) and in no `project_scope` row. Scoped to
  systems only — apps/components nest inside a system and are visible regardless, so flagging
  them would be noisy.
- `duplicate_name`: two or more rows within the same node sheet (`sys`/`app`/`cmp`/`usr`)
  share a case-insensitive, whitespace-trimmed `name` with distinct ids — renders ambiguous
  diagram labels.
- `self_interface`: an `interface` row whose provider equals its consumer.

Return shape: `issues.warnings` = list of warning dicts, `summary.warnings` = count,
`valid` unchanged (errors only). `arch.generate` proceeds when only warnings exist and the
warnings ride along in the payloads it already passes through (`issues`, `summary`).

*Alternative considered*: warning on unknown extension columns. Rejected — extension columns
are preserved by design (round-trip requirement); warning on them contradicts the contract.

### D6 — Test migration

Monkeypatch targets move with the code: `arch.subprocess` →
`otdev.tools._arch.generate.subprocess`; `arch._RENDER_TIMEOUT_SECONDS` →
`generate._RENDER_TIMEOUT_SECONDS`. Public tool behavior tests are untouched. New tests
cover: render skip on unchanged rerun, re-render on model change, stale file removal,
`force=True` full re-render, `summary.renders` counts, `drawio_export` toggle flip forcing
re-render, and one test per warning code plus warnings-don't-block.

## Risks / Trade-offs

- [Loop/builder merge changes rendered output subtly] → The merged builder and page loop are
  refactors with explicit parity intent; existing unit tests assert d2/HTML content for both
  systems and projects (e.g. `test_generate_solution_emits_project_pages`,
  `test_generate_solution_applies_profile_data_to_system_d2`) and must pass unmodified apart
  from monkeypatch targets. Any assertion change is a red flag, not a test update.
- [Skipped render is stale after d2 CLI upgrade or `cmd_template` change] → Accepted;
  documented escape hatch `force=True`. Profile `data` changes flow into the d2 text and are
  caught by content-compare.
- [Stale sweep deletes user files placed inside `solution/`] → Not a regression — the spec
  already says generate fully owns the directory, and rmtree deleted them before. The sweep
  only runs after a fully successful generation.
- [Partial failure leaves mixed old/new outputs] → Old behavior left an *empty* directory on
  mid-run failure (rmtree ran first); mixed-but-mostly-valid is strictly better, and the next
  successful run converges via the sweep.
- [Warning noise on legitimately disconnected systems] → Warnings are non-blocking and scoped
  to three precise conditions; codes are stable so consumers can filter.

## Migration Plan

Single PR, mechanical-first ordering (extraction commit, then dedupe, then behavior). No data
or config migration. `force` is additive with a safe default; payload additions
(`summary.renders`, populated `warnings`) are additive keys. Rollback = revert.

## Open Questions

None — decisions above are final for this change.
