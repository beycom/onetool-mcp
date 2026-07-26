---
name: ot-forge
description: Use when scaffolding, validating, or activating an in-process OneTool extension pack. Use for local OneTool extensions, not general Python package scaffolding or new built-in packs.
user-invocable: false
---

# OneTool Forge

Use `ot_forge` for the local extension lifecycle.

## Availability

Check `__ot ot.packs(pattern='ot_forge', info='min')`. If unavailable, stop and offer OneTool
installation guidance; do not install or change configuration without a separate request.

## Workflow

1. Inspect available templates and choose the narrowest matching scaffold.
2. Generate into an explicit project path; never overwrite existing work implicitly.
3. Implement keyword-only typed tools with explicit exports.
4. Validate the extension before activation.
5. Reload with `ot.reload()` only after validation, then confirm discovery with `ot.tool_info`.

Treat generated code as a starting point requiring review. Do not use Forge to bypass the built-in
pack contribution process or activate untrusted source.
