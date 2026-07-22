# P14 — Enforce the version-pinned view-only LikeC4 subset

## Problem

`VIEW_ONLY_ALLOWLIST` documents the permitted LikeC4 subset but is never enforced. Current validation rejects only `model`, `specification`, and `deployment` declarations, then performs reference and participant checks.

Other unsupported or unsafe statements can pass the validator despite the contract promising a version-pinned allowlist.

## Expected

Parse authored view-only LikeC4 sufficiently to enforce the declared subset:

- accept only supported view predicates, groups, layout, notes, navigation, local styles, and static/dynamic interactions;
- reject every logical or unsupported declaration;
- preserve exact file, line, diagram, statement, and identifier diagnostics;
- validate navigation and generated canonical references; and
- tie the accepted grammar to `VIEW_ONLY_VERSION`.

Do not use substring or broad regex matching as the grammar boundary.

## Actual

`diagram.py::validate_view_only_source` does not consult `VIEW_ONLY_ALLOWLIST`. Existing tests primarily prove rejection of a deployment block.

## Acceptance Criteria

- Every allowlisted statement has a positive executable fixture.
- Representative non-allowlisted statements are rejected with exact locations.
- Comments and strings cannot evade or falsely trigger validation.
- Dynamic participant and generated-ID validation still pass.
- The implementation and spec share one authoritative subset/version definition.

## Context

Review:

- `src/otdev/tools/_arch/v2/diagram.py`
- `tests/otdev/integration/tools/test_arch_v2_validation.py`
- `openspec/specs/otdev/tool-arch-diagram-catalog/spec.md`
- the pinned LikeC4 version and compiler boundary

Use `$p-fix`; do not broaden the supported language unless explicitly approved.
