# P22 — Render external diagrams safely and offline

## Problem

PlantUML and Mermaid attachments are advertised as supported diagrams but are encoded as `text/plain` and displayed in an iframe. Users see source text rather than a rendered diagram.

SVG and HTML attachment safety relies on a regex that does not robustly cover CSS imports, external SVG resources, meta refresh, parser edge cases, or every network-capable construct.

## Expected

- Render supported PlantUML and Mermaid inputs locally into a safe display format.
- Keep generation and viewing fully offline.
- Sanitize SVG and HTML with parser-based, allowlist-oriented processing.
- Apply a restrictive content security policy and sandbox.
- Reject external resources, navigation, scripts, active content, and unsupported markup with source-located diagnostics.
- Preserve size and total-bundle limits.

## Actual

`diagram.py::_safe_attachment` assigns PlantUML and Mermaid `text/plain`. `App.tsx::ExternalDiagram` renders every non-SVG attachment through a sandboxed iframe without compiling diagram source.

## Acceptance Criteria

- PlantUML and Mermaid fixtures render as diagrams, not source text.
- Browser tests run with networking blocked.
- CSS URLs/imports, external SVG references, meta refresh, scripts, events, and unsafe data URLs are rejected.
- Safe SVG, HTML, PDF, PlantUML, and Mermaid fixtures remain usable.
- Output remains self-contained and deterministic.

## Context

Review:

- `src/otdev/tools/_arch/v2/diagram.py::_safe_attachment`
- `src/otdev/tools/_arch/frontend/src/App.tsx::ExternalDiagram`
- diagram catalog browser and validation tests
- `openspec/specs/otdev/tool-arch-diagram-catalog/spec.md`

Use `$p-fix`; do not add network-backed rendering services.
