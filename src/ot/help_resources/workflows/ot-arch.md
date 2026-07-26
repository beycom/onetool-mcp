<!-- Generated from skills/ot-arch/SKILL.md; do not edit. -->
# OneTool Architecture

Use `arch` for architecture-model validation and deliverable generation.

## Capability boundary

Check `__ot ot.packs(pattern='arch', info='min')`. If `[dev]`, Git, D2, a renderer, or an input
dependency is missing, stop and offer installation or configuration guidance; do not install or
configure anything without a separate request.

Use `arch.validate` for workbook model correctness, `generate` for reviewed deliverables,
`export_yaml`/`import_yaml` for controlled Excel↔YAML round trips, and `bundle_solution` only for a
verified generated directory. Filters and profiles change the delivered model; treat them as
explicit design decisions. D2 is needed only for workflows that render D2 output.

## Workflow

1. Inspect the input path and call `arch.validate(input_path=...)` before generation.
2. Resolve errors in the model source; record warnings that are intentionally accepted.
3. For round trips, export to YAML, review the semantic diff, then import into an explicit
   template/output path and validate again.
4. Select include/exclude tags and a reviewed profile. Use `force=False` first so incremental
   safeguards remain active.
5. Generate into an explicit output directory, inspect diagnostics, HTML pages, diagram source,
   and rendered artifacts.
6. Bundle only after links/assets and representative system/project pages pass verification.

## Safety and side effects

Generation writes a directory tree and can invoke external renderer commands from trusted profile
configuration. Review profile command templates and output paths before use; never render an
untrusted profile merely because the Pydantic model validates. Preserve unknown round-trip fields.
`force=True` may replace outputs that incremental generation protects.

## Verification and recovery

Re-run `arch.validate`, inspect generated file counts and representative SVG/HTML outputs, and open
the bundle before delivery. On a renderer failure, keep the generated source, inspect
`ot.help(query='arch', topic='setup')`, repair one prerequisite, and retry once. A rendered diagram
does not prove that the architecture model is valid.
