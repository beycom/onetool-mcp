---
name: ot-diagram
description: Use when generating, reviewing, rendering, or batch-rendering source-based Mermaid, PlantUML, D2, Graphviz, or other Kroki diagrams through OneTool. Use ot-whiteboard for a live editable canvas.
user-invocable: false
---

# OneTool Diagram

Use `diagram` for source-controlled static diagram artifacts.

## Availability

Check `__ot ot.packs(pattern='diagram', info='min')`, then inspect
`diagram.get_output_config()`. If `[dev]`, Kroki, D2, or another renderer is missing, stop and
offer installation or configuration guidance; do not install, configure, or start services
without a separate request.

## Workflow

1. Choose the simplest supported syntax for the intended diagram.
2. Generate or edit source before rendering.
3. Validate source and render one representative diagram.
4. Inspect the output visually and correct labels or layout.
5. Batch-render only after the representative result is sound.

Treat the pack as experimental. Bound remote renderer inputs and do not send confidential diagram
source to a remote service without authorization.
