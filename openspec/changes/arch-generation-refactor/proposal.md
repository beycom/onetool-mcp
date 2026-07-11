# arch-generation-refactor

## Why

The `arch` facade (`src/otdev/tools/arch.py`, ~1,480 lines) carries ~900 lines of generation
orchestration that belongs in `_arch/`, with near-clone systems/projects render loops one layer
up and duplicated system-block builders one layer down (`system_model.py`, 2,289 lines). On top
of the structural debt, every `generate()` run deletes the entire solution directory
(`shutil.rmtree`) and re-renders every diagram through the d2 subprocess — slow and wasteful for
iterative workbook editing — and the validation warnings channel exists in every payload but is
never populated, so non-blocking data-quality signals are silently dropped. The quick fixes from
the same issue (render timeout, exception-contract catch-alls) already landed (495ce5/60ceaa);
this change covers the deferred structural and behavioral items.

## What Changes

- **Facade decomposition (refactor, no behavior change)**: move generation orchestration out of
  `src/otdev/tools/arch.py` into a new `src/otdev/tools/_arch/generate.py` — `_generate_solution`
  (~330 lines), `_render_workbook_diagrams`, `_render_view_diagrams`, `_execute_render_engine`,
  `_execute_render_jobs`, `_collect_workbook_diagram_specs`, and their helpers. The facade keeps
  only the five public tools plus thin argument/config resolution.
- **Dedupe render loops**: collapse the near-clone systems and projects loops inside
  `_generate_solution` into a single parameterized page-generation routine; merge
  `_build_system_block` and `_build_project_system_block` in
  `src/otdev/tools/_arch/system_model.py` into one builder with optional project-scope
  filtering/change-class decoration.
- **Incremental generation**: replace the `shutil.rmtree`-every-run approach in
  `_generate_solution` with incremental output — write files only when content changed, skip d2
  subprocess renders whose `.d2` source is unchanged and whose `.svg` output is present and
  consistent, and remove only stale files afterwards. Add `force: bool = False` to
  `arch.generate` as a full-regeneration escape hatch.
- **Validation warnings**: populate the existing-but-empty warnings channel in
  `src/otdev/tools/_arch/validate.py` with non-blocking issues (orphan entities, duplicate
  display names). Warnings never affect `valid`; `summary.warnings` reports the count.

## Capabilities

### New Capabilities

- `otdev/tool-arch-validation-warnings`: non-blocking validation warnings — which conditions
  produce warnings, their payload shape, and that warnings never block validation or generation.

### Modified Capabilities

- `otdev/tool-arch-model-centric-rendering`: the "Regenerated solution output" requirement
  changes from clean-slate regeneration to incremental ownership — unchanged outputs are reused,
  stale files are still removed, and a new `force` parameter restores full re-render. Delegated
  rendering orchestration is unchanged in behavior (the decomposition itself is spec-invisible).

## Impact

- **Code**:
  - `src/otdev/tools/arch.py` — shrinks to public tools + input handling (~500 lines).
  - `src/otdev/tools/_arch/generate.py` — new module (orchestration moved here).
  - `src/otdev/tools/_arch/system_model.py` — merged system-block builder.
  - `src/otdev/tools/_arch/validate.py` — warning production.
- **API**: `arch.generate` gains optional `force: bool = False`; `validate`/`generate` payloads
  now carry populated `issues.warnings` and non-zero `summary.warnings`. No breaking changes:
  all existing parameters, payload keys, and error codes are preserved.
- **Tests**: existing arch unit/integration tests must keep passing unchanged apart from import
  paths for moved private helpers; new tests for incremental reuse/stale cleanup/`force` and for
  each warning condition.
- **Dependencies**: none added.
