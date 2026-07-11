# Tasks: arch-generation-refactor

## 1. Extract generation orchestration into `_arch/generate.py` (mechanical, no behavior change)

- [x] 1.1 Move `_error_payload` from `src/otdev/tools/arch.py` to `src/otdev/tools/_arch/models.py` as `error_payload`; update the facade's five tools to import it from there
- [x] 1.2 Create `src/otdev/tools/_arch/generate.py`; move verbatim from `arch.py`: `_WorkbookDiagramSpec` (→ `WorkbookDiagramSpec`), `_collect_workbook_diagram_specs` (→ `collect_workbook_diagram_specs`), `_build_model_payload` (→ `build_model_payload`), `_clean_diagram_rows` (→ `clean_diagram_rows`), `_build_render_context`, `_template_context`, `_execute_render_engine`, `_execute_render_jobs`, `_unsafe_id_error`, `_render_view_diagrams`, `_render_workbook_diagrams`, `_generate_solution` (→ `generate_solution`), `_validate_system_id_fragment`, `_validate_path_fragment`, `_now_timestamp`, and the constants `_MAX_RENDER_WORKERS`, `_RENDER_TIMEOUT_SECONDS`, `_SAFE_ID_FRAGMENT_RE`, `_UNSAFE_PATH_CHARS_RE`
- [x] 1.3 Slim `arch.py`: keep pack metadata, `__ot_requires__`, the five public tools, `_resolve_generation_profile`, `_resolve_drawio_export_toggle`, `_resolve_list_cell_separator`; import `generate_solution` / `collect_workbook_diagram_specs` / `build_model_payload` / `clean_diagram_rows` from `_arch.generate`; prune the now-unused `_arch.system_model` import block, `subprocess`/`shlex`/`shutil`/`ThreadPoolExecutor` imports
- [x] 1.4 Re-target unit tests in `tests/otdev/unit/tools/test_arch.py`: monkeypatches of `arch.subprocess.run` → `otdev.tools._arch.generate.subprocess.run`; references to `arch._RENDER_TIMEOUT_SECONDS` → `generate._RENDER_TIMEOUT_SECONDS` (no assertion changes)
- [x] 1.5 Run `uv run pytest tests/otdev -m "unit and tools" -k arch` and `just lint`; all existing tests pass with unchanged assertions

## 2. Dedupe render loops and block builders

- [x] 2.1 In `system_model.py`, add frozen dataclass `ProjectScope` (`explicit_system_ids`, `included_app_ids`, `included_cmp_ids`, `change_lookup`); merge `_build_project_system_block` (line ~1386) into `_build_system_block` (line ~805) via optional `scope: ProjectScope | None = None`, preserving both placeholder rules and change-class decoration exactly (design D3); update `build_project_view` call site; delete `_build_project_system_block`
- [x] 2.2 In `_arch/generate.py`, introduce internal `_PageKind` (row source + skip predicate, per-page key iterator, view builder, d2 builder, output stem pattern, page-context builder, page-name fn, card fields) and one `_generate_pages(...)` routine; replace the systems loop and projects loop in `generate_solution` with two `_PageKind` instances (design D2), keeping card list shapes and sort order identical
- [x] 2.3 Verify parity: full arch unit + integration suites pass with zero assertion changes (`uv run pytest tests/otdev -m "tools" -k arch`)

## 3. Incremental generation

- [x] 3.1 Add `_write_if_changed(path: Path, text: str) -> bool` helper in `_arch/generate.py`; route all d2/HTML/svg writes in `generate_solution` through it; delete the `shutil.rmtree(solution_dir)` pre-clean
- [x] 3.2 Implement the render skip rule in the unified page loop: skip an engine job when not `force`, new `.d2` text equals existing file, `.svg` exists, and the svg's draw.io-embed state (presence of `content="..."` attribute) matches the run's `drawio_export` toggle; reuse the existing `.svg` for markup extraction and skip re-injection (design D4)
- [x] 3.3 Implement mtime-based skip for workbook diagrams in `_render_workbook_diagrams`: skip when not `force`, output `.svg` exists, and svg mtime >= source mtime
- [x] 3.4 Implement the stale-file sweep: collect the expected-file set from `generated_files` + `index.html`; after a fully successful run, delete files under `solution/` not in the set and prune empty dirs; never sweep on error
- [x] 3.5 Add `force: bool = False` parameter to `arch.generate` (docstring included), threaded to `generate_solution` and `_render_workbook_diagrams`; add `summary.renders = {"executed": N, "skipped": M}` to the success payload
- [x] 3.6 Unit tests (`tests/otdev/unit/tools/test_arch.py`): unchanged rerun skips all engine renders (`summary.renders.skipped` > 0, subprocess mock not re-invoked); model change re-renders only affected diagram; stale files from a prior run removed on success; stale files retained on failed run; `force=True` re-renders everything; `drawio_export` toggle flip forces re-render despite unchanged `.d2`
- [x] 3.7 Integration test (`tests/otdev/integration/tools/test_arch.py`): generate twice with the real d2 engine; second run reports skipped renders and directory content matches a fresh `force=True` run

## 4. Validation warnings

- [x] 4.1 In `_arch/validate.py`, add `_collect_warnings(...)` producing `Issue` items for `orphan_system`, `duplicate_name` (case-insensitive trimmed name, same node sheet, distinct ids), and `self_interface` (design D5); wire into `validate_entities`: `issues.warnings` populated, `summary.warnings` = count, `valid` still errors-only
- [x] 4.2 Verify pass-through: `arch.validate` payload carries warnings with `ok=true`/`valid=true` when no errors; `arch.generate` proceeds and includes warnings in its validation-derived fields
- [x] 4.3 Unit tests: one per warning code (flag case + non-flag case per spec scenarios, e.g. system connected via owned app's interface not flagged; same name across different sheets not flagged); warnings alongside errors keeps `valid=false` with both channels populated; warning-only input generates successfully

## 5. Finalize

- [x] 5.1 Run `just check` (lint + mypy + tests) clean; confirm `arch.py` facade is ~500 lines and contains no render/orchestration logic
- [x] 5.2 Run `openspec validate --strict --change "arch-generation-refactor"` and confirm scenarios map to implemented behavior; update `wip/issues/1-new/[spec-needed]-arch-pack-fixes.md` status note (deferred items now covered by this change)
