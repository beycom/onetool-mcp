# P32 — Complete the final architecture v2 release review

## Problem

Architecture v2 is a subsystem replacement spanning Python APIs, replay and projection, frontend runtime, renderer integration, exports, portable bundles, tests, specifications, documentation, and skills.

Individual issues can pass while the combined product remains undistributable, inconsistent, unsafe, or mixed with unrelated roadmap and tooling work.

## Expected

After P11-P24 and P31 are complete, perform a final evidence-based review of the combined implementation.

Verify:

1. Clean checkout, source distribution, and wheel workflows.
2. Every public operation and common result envelope.
3. YAML/Excel parity and deterministic replay.
4. Explorer generation and offline browser behaviour.
5. Renderer-neutral topology, geometry, caching, and stale-request handling.
6. SVG, Draw.io, YAML, Excel, and bundle fidelity.
7. Attachment and bundle security boundaries.
8. Transactional publication and ownership protection.
9. Complete scenario-to-test traceability.
10. Documentation and `ot-arch` skill accuracy.
11. No compatibility aliases, legacy paths, or hidden fallbacks.
12. React provider boundaries and render performance remain acceptable.

Separate unrelated roadmap, proxy, installer, and OneSkill work from the architecture v2 delivery so each change set is independently reviewable.

## Acceptance Criteria

- All earlier architecture-v2 issues are complete and re-verified against current code.
- `just lint`, `just typecheck`, `just test`, `just arch-frontend-check`, and `just check` pass from a clean checkout.
- Built-package smoke tests pass in an isolated environment.
- Browser tests prove offline operation and observable diagram behaviour.
- Security and publication failure-injection tests pass.
- All architecture specs validate and every normative scenario is mapped.
- The final diff contains only the intended architecture-v2 delivery units.
- Completion records remaining risks or explicitly states that none remain.

## Context

Review the final repository state rather than relying on issue status or earlier line numbers. Primary areas include:

- `src/otdev/tools/arch.py`
- `src/otdev/tools/_arch/v2/`
- `src/otdev/tools/_arch/frontend/`
- `tests/otdev/`
- `openspec/specs/otdev/tool-arch-*/`
- `docs/reference/tools/arch.md`
- `skills/ot-arch/`
- packaging and project command configuration

Use `$p-fix` for the review and contained corrections. Do not begin another user-facing capability as part of this gate.
