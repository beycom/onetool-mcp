<!-- Generated from skills/ot-diagram/SKILL.md; do not edit. -->
# OneTool Diagram

Use `diagram` for source-controlled static diagram artifacts.

## Capability boundary

Check `__ot ot.packs(pattern='diagram', info='min')`, then inspect
`diagram.get_output_config()`. If `[dev]`, Kroki, D2, or another renderer is missing, stop and
offer installation or configuration guidance; do not install, configure, or start services
without a separate request.

Use help topics before guessing policy or providers:
`ot.help(query='diagram', topic='policy'|'providers'|'templates'|'config')`. Generate/review source
before rendering. Provider choice determines syntax; backend choice determines whether source is
sent to remote Kroki or a self-hosted service. Batch/directory rendering is self-hosted-only.

## Workflow

1. Choose the simplest supported syntax for the intended diagram.
2. Generate or edit source before rendering.
3. Inspect policy, provider instructions, template metadata, and output config.
4. Validate source and render one representative diagram; use async mode only when polling is useful.
5. Inspect SVG/PNG/PDF visually and correct semantics, labels, and layout.
6. Poll async IDs with `get_render_status`; batch/directory render only after representative output
   is sound and the self-hosted backend is selected.

## Safety and side effects

Source/output generation writes files. Remote rendering sends diagram source to an external
service; obtain authorization for confidential architecture/data. Configured templates and
provider instructions are trusted project inputs that still require review. Bound directory
patterns, concurrency, and output paths.

## Verification and recovery

Inspect generated source, final file type/size, and the rendered image. For async work, require a
terminal success state. On syntax/provider failure, retain source, inspect the provider topic, make
one correction, and retry; on backend failure, inspect setup/config and do not loop remote calls.
