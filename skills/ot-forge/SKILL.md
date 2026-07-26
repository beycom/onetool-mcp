---
name: ot-forge
description: Use when scaffolding, validating, or activating an in-process OneTool extension pack. Use for local OneTool extensions, not general Python package scaffolding or new built-in packs.
user-invocable: false
---

# OneTool Forge

Use `ot_forge` for the local extension lifecycle.

## Capability boundary

Check `__ot ot.packs(pattern='ot_forge', info='min')`. If unavailable, stop and offer OneTool
installation guidance; do not install or change configuration without a separate request.

The current callable lifecycle is exact: `create_ext(...)` scaffolds an extension and
`validate_ext(path=...)` performs static validation. Forge does not expose template inspection,
generic generation, extension execution, or behavioral testing operations.

## Workflow

1. Choose a normalized extension name, pack name, initial function, description, and API-key name.
2. Call `create_ext` once and inspect every generated file before editing.
3. Implement keyword-only typed tools, explicit `pack`/`__all__`, docstrings, normalized
   requirements, and an explicit config hook when applicable.
4. Call `validate_ext(path=...)`; fix every static error before activation.
5. Review/approve any config change, reload with `ot.reload()`, then confirm discovery with
   `ot.tool_info(name='pack.tool')`.

## Safety and side effects

Scaffolding writes source files. Do not overwrite an existing extension implicitly or activate
untrusted generated code. In-process extensions run as trusted Python with full builtins; static
validation is a guardrail, not a sandbox. Use the developer pack-authoring guide for built-in
packs and `otpack`; Forge is not the contribution workflow.

## Verification and recovery

Require `validate_ext` success, exact discovery, a signature check, and a representative
non-destructive call. On failure, inspect the validation path and generated source once; do not
claim activation because files exist. Hand missing requirements/config to `ot-setup`.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `ot_forge` | `core` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/ot_forge/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
