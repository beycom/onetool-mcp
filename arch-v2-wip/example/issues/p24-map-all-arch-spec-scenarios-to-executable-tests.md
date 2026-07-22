# P24 — Map every architecture specification scenario to executable coverage

## Problem

The seven architecture specifications contain substantially more normative scenarios than the 35-outcome acceptance matrix.

The acceptance registry proves only that each matrix entry names an existing test function or frontend test string. It does not prove that all normative scenarios are mapped or that the named test exercises the production path. OpenSpec `--all` discovery also does not currently validate the nested architecture specs.

## Expected

Create explicit, machine-checked traceability from every normative architecture scenario to one or more executable tests or production-path fixtures.

The check must verify scenario coverage, not only function-name existence, and the normal strict validation command must include every architecture spec.

## Actual

`test_arch_v2_acceptance.py` checks matrix length, uniqueness, file existence, and test-name text. Contract gaps such as allowlist enforcement, SVG direction, transactional failure, secret-file bundling, and rendered PlantUML/Mermaid were not detected.

## Acceptance Criteria

- Every normative scenario has a stable identifier and executable mapping.
- Missing, duplicate, stale, skipped, or non-production mappings fail CI.
- Strict OpenSpec validation discovers all seven architecture capability specs.
- The matrix covers all corrections from P11 through P23.
- Coverage includes clean-package execution, failure injection, security cases, and browser behaviour.
- `just check` runs the traceability validation.

## Context

Review:

- `tests/otdev/unit/tools/test_arch_v2_acceptance.py`
- `tests/otdev/fixtures/arch-v2/acceptance-matrix.json`
- `openspec/specs/otdev/tool-arch-*/`
- OpenSpec validation/discovery configuration
- Python and frontend acceptance suites

Use `$p-fix`; update existing specs and their verification infrastructure without creating a new capability.
