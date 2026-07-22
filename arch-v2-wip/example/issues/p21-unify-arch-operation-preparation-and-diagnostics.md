# P21 — Unify architecture operation preparation and preserve diagnostics

## Problem

Explorer generation and export independently implement workspace loading, validation, selection normalization, roadmap replay, projection, and presentation resolution.

The flows have already drifted: validation warnings are discarded by generate and export, while some selection warnings are converted into unstructured explorer strings.

## Expected

Extract one shared application-level preparation path used by validate, generate, and export where applicable. It must return:

- the loaded workspace and root;
- normalized requests and stable selection mapping;
- replayed/projected/presented graphs;
- structured errors and warnings with source trace; and
- any renderer/export prerequisites required by the requested operation.

Every public operation must preserve the common result envelope and reconcile summary counts with the issue arrays.

## Actual

`frontend.prepare_explorer_data` and `exporter._prepare_graphs` duplicate orchestration. Both call validation but retain only its errors.

## Acceptance Criteria

- Validation warnings survive generate and export unchanged.
- Source and identity details remain structured.
- Equivalent selections deduplicate consistently across explorer and export.
- Generate/export cannot diverge in replay, projection, or presentation semantics.
- Result summary counts exactly match returned issues and artifacts.
- Tests cover warnings, errors, duplicated selections, and YAML/Excel parity.

## Context

Review:

- `src/otdev/tools/_arch/v2/frontend.py`
- `src/otdev/tools/_arch/v2/exporter.py`
- `src/otdev/tools/_arch/v2/api.py`
- `src/otdev/tools/_arch/v2/result.py`
- `src/otdev/tools/_arch/v2/validation.py`
- `openspec/specs/otdev/tool-arch-validation/spec.md`

Use `$p-fix`; this is an internal consolidation with contract-correctness fixes.
