# Pack Guidance and Agent Skills

Canonical workflow for adding or changing a built-in OneTool pack, its runtime
help, and the agent skill that teaches effective use.

## Decide the integration type

Use this decision tree before editing:

1. If the capability is implemented in `src/ottools`, `src/otutil/tools`, or
   `src/otdev/tools`, it is an **in-process pack**. Follow this guide.
2. If OneTool connects to a separate MCP server, it is a **proxy-backed
   capability**. Follow [Proxy Server Integration](proxy-server-integration.md).
3. If a dev-only pack helps authors build or validate packs, document that
   developer workflow here or in the tool reference. Do not create a general
   runtime skill unless agents need distinct operating judgment.

`features/features.yaml` is historical change tracking. It is not an
authoritative inventory and must not be imported, parsed, validated, or used by
runtime code, docs generation, tests, builds, or releases.

## Sources of truth

Keep authored facts in the narrowest authoritative source:

| Fact | Authoritative source |
|---|---|
| Public functions and signatures | Pack `__all__`, function signatures, and docstrings |
| Install/library/CLI/secret/server/config requirements | Normalized `__ot_requires__` in the pack |
| Config schema and defaults | Declared Pydantic model named by `config_model` |
| Display name, install extra, summary, docs slug, skill owner, stability, profiles, help topics | Typed records in `src/ot/catalog.py` |
| User API detail and examples | `docs/reference/tools/<slug>.md` |
| Agent selection, workflow, safety, verification, and recovery | Owning `skills/<name>/SKILL.md` |
| Large stable operating reference such as a DSL | Packaged UTF-8 help resource registered by the catalog |
| Runtime aliases and loaded tools | Runtime registry |

Do not create a second pack list, skill list, ownership map, profile table, or
help-topic registry. Generated projections consume the typed catalog and runtime
registry.

## Implement an in-process pack

### 1. Define the runtime surface

Follow [Tool Development](tool-development.md). Export only public synchronous,
keyword-only functions. Add representative tests for success, invalid input,
side effects, and failures.

Use the bundled `otpack` SDK instead of rebuilding shared infrastructure:

- config/secrets and dependency checks;
- batch envelopes, bounded concurrency, retry validation, and normalization;
- embeddings, serialization, token chunking, and RRF merging;
- JSON HTTP clients, auth helpers, lazy clients, and caches;
- project cwd, artifacts, project-local state, and path validation;
- `LogSpan`, validation, truncation, structured extraction, and source formatting.

`otpack` is a developer dependency, not a runtime capability skill. Develop it
in `packages/onetool-pack/`, run its package tests and boundary check, then run
the root suite. The root wheel bundles `otpack`; a standalone release uses the
package's own `pyproject.toml` and `justfile`. Test both standalone configuration
and OneTool-hosted integration when changing its config or path boundary. Do not
publish/install it as a validation shortcut; build the distribution and inspect
the wheel contents before release.

### 2. Declare requirements and config

Use the normalized requirement records described in
[Tool Configuration](tool-configuration.md). Declare hard and conditional
requirements, their purpose, install extra, and activation condition. If the
pack has typed config, expose its model through `config_model`.

These declarations power registry validation, `ot.help(topic="setup")`,
redacted config inspection, and `ot-setup`. Do not reproduce setup facts in a
skill.

### 3. Add one catalog record

Add or update the reviewed `PackGuidanceEntry` in `src/ot/catalog.py`:

- runtime pack name and display name;
- `core`, `[util]`, or `[dev]` install extra;
- accurate default summary and canonical docs slug;
- exactly one owning skill for every stable pack;
- stability and a reason when a beta pack is intentionally excluded;
- standard and pack-specific help topics.

Add a `SkillCatalogEntry` only when the new capability needs a new agent
workflow. Prefer an existing capability owner or cross-pack selection guide
when its operating boundary already fits.

### 4. Design runtime help

Every stable pack gets deterministic `overview`, `workflow`, `setup`, and
`config` topics. Use:

- a dynamic catalog/config renderer for current runtime facts;
- a packaged resource for stable, sizeable material agents need remotely;
- an explicit read-only adapter when the pack already exposes canonical policy
  or template data.

`ot.help()` is the progressive-disclosure entry point. Keep its deterministic
topic useful without an LLM. `ask=` may synthesize from that selected topic;
`answer_only=True` returns only the synthesis on success and an explicit LLM
error plus narrowed deterministic help on failure.

Topic providers must be read-only, redact credentials and environment values,
identify provenance, and remain usable from an installed wheel without a
repository checkout.

`just docs-sync` projects authored skill operating sections into generated
`src/ot/help_resources/workflows/` files. Pack `workflow` help serves those
versioned resources remotely. Edit the owning skill, never the generated
Markdown resource.

### 5. Author agent guidance

Follow [Skill Development](skill-development.md). The owning skill explains how
to exploit the capability: selection boundaries, sequence, safety, completion
checks, and bounded recovery. It must contain:

- `## Capability boundary`
- `## Workflow`
- `## Safety and side effects`
- `## Verification and recovery`

Do not copy function tables, requirement lists, setup instructions, or large
DSLs into the skill. `just docs-sync` maintains its catalog coverage block and
the stable `ot-ref` indexes.

### 6. Maintain public docs

Follow [Tool Reference Documentation](tool-reference-docs.md). The page must
match current code, including defaults, return shapes, mutation behavior,
requirements, and any pack CLI. Link to online canonical docs when available;
runtime agents should use `ot.help()` because a local repository path may not
exist.

## Validation checklist

- [ ] Runtime registry finds exactly one pack declaration and every exported function.
- [ ] Every requirement uses the normalized schema; conditional requirements have activation conditions and on-demand workflow requirements are marked optional.
- [ ] Typed config has a valid explicit `config_model` hook and redaction tests.
- [ ] Typed catalog contains one accurate pack record, one owner, a valid docs slug, and registered topics.
- [ ] Stable packs have an owning skill; beta exclusions never enter skill artifacts.
- [ ] Skill provides workflow, safety, verification, and recovery without copying reference docs.
- [ ] Help topics work deterministically, remain read-only, and ship in the wheel.
- [ ] Public reference examples and claims match code.
- [ ] Router and derived installation profiles reach the skill.
- [ ] Tests cover catalog drift, help, setup degradation, and generated-marker preservation.

Run in order:

```bash
just docs-sync
just skills-check
just check
```

Run `just docs-sync` twice when changing a generator and confirm the second run
has no diff.
