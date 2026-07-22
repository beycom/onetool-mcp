# P23 — Complete direct SVG semantic fidelity

## Problem

The direct SVG exporter does not preserve all semantics required by the export contract. It always emits an end arrow, uses fixed status colours and rectangular nodes, does not render resolved icons or links, and does not fully apply presentation styles.

Its viewBox also assumes a fixed negative origin rather than incorporating the actual layout bounds.

## Expected

Render SVG directly from the resolved `ViewGraph`, presentation, diagram metadata, and renderer-neutral layout while preserving:

- stable view, node, edge, and interface IDs;
- hierarchy and exact geometry;
- forward, reverse, and bidirectional arrows;
- contextual status;
- supported node and edge styles;
- resolved icons and links;
- dynamic/sequence semantics; and
- bounds that cannot clip translated layouts.

Reject or explicitly diagnose unsupported semantic loss before publication.

## Actual

`exporter.py::_svg` applies fixed status styling and `marker-end` to every edge. Existing SVG tests primarily assert IDs, endpoints, XML parsing, and non-placeholder content.

## Acceptance Criteria

- Independent SVG parsing verifies all required semantics.
- Fixtures cover every edge direction, style family, icon, link, hierarchy, and contextual status.
- Layouts with non-zero and negative bounds are not clipped.
- Generated and authored diagram classes use the intended geometry.
- Unsupported fidelity produces a structured failure rather than silent degradation.

## Context

Review:

- `src/otdev/tools/_arch/v2/exporter.py::_svg`
- `src/otdev/tools/_arch/v2/models.py`
- `src/otdev/tools/_arch/v2/presentation.py`
- `tests/otdev/integration/tools/test_arch_v2_export.py`
- `openspec/specs/otdev/tool-arch-multi-format-export/spec.md`

Use `$p-fix`; retain the renderer-neutral export boundary.
