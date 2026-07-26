# Skill Development

Canonical guide for OneTool skills under `skills/`.

## Roles

- **Shared reference (`ot-ref`)** owns generic call mechanics, discovery, aliases, recovery, the
  generated stable-pack map, and the complete greppable stable-pack tool index.
- **Capability guide** owns operating judgment for one capability: selection, sequencing,
  availability, safety, verification, and pack-specific recovery.
- **Cross-pack selection guide** chooses among overlapping packs without duplicating their tool
  references.
- **Catalog router (`ot-ask`)** routes a user situation to an exact skill or `ot-ref`; it does not
  repeat capability workflows.

Create a dedicated capability skill only when it changes how an agent should operate a pack.
Small wrappers and packs already covered by a shared selection boundary do not need another skill.

## Naming and invocation

Use a globally unique lowercase hyphenated name beginning with `ot-`. Every skill has:

```yaml
---
name: ot-capability
description: Use when ... State the nearest boundary.
user-invocable: false
---
```

Model-invoked skills set `user-invocable: false` and omit
`disable-model-invocation`. Codex allows implicit invocation by default, so omit
`agents/openai.yaml` unless the skill needs UI metadata, tool dependencies, or another
Codex-specific setting. If a model-invoked skill has a sidecar, it must not disable implicit
invocation.

The user-invoked router needs the non-default Codex policy:

```yaml
policy:
  allow_implicit_invocation: false
```

The user-invoked router sets `user-invocable: true`,
`disable-model-invocation: true`, and ships that sidecar.
Do not add `tags`, version metadata, or alternative invocation fields.

Descriptions should identify a positive trigger and the nearest competing capability. Keep
explicit-pack and outcome-oriented prompts in scope while excluding native-host work and another
OneTool capability when those are better fits.

## Ownership and profiles

Typed records in `src/ot/catalog.py` are the reviewed source for pack ownership,
skill roles, invocation, stability, help topics, and selectable installation
profiles. Runtime registry data is joined to those authored records; neither
docs generators nor validators maintain another inventory.

Every stable built-in pack has exactly one guidance owner. Cross-catalog skills
such as setup, runtime operations, and the router may own a workflow without
owning a pack. Dynamically proxied MCP servers are discovered live and are
outside static pack ownership.

Profiles are derived from catalog roles and pack extras:

- **Foundation** — call/reference, router, and setup.
- **Core** — Foundation plus core-pack owners and runtime operations.
- **Core + `[util]`** and **Core + `[dev]`** — Core plus owners for the selected
  Python extra.
- **`[all]`** — every distributed OneTool skill.

The Python package extra named `[all]` is a separate concept: it expands to
`[util,dev]` and deliberately excludes separately opt-in `[scrape]`.

## Capability body

Write enough operating guidance for a less-capable model to use the whole pack
without guessing. Every skill must have these exact semantic sections:

1. `## Capability boundary`
2. `## Workflow`
3. `## Safety and side effects`
4. `## Verification and recovery`

Within them, cover meaningful modes, selection and sequencing, availability,
completion evidence, material mutation/cost/privacy/secret concerns, and
pack-specific recovery. A generous validation ceiling prevents reference-doc
duplication without rewarding shallow prose.

Do not copy signatures, aliases, generic call syntax, or user reference documentation. Do not add
a generated tool index per skill. A local reference is justified only for genuinely pack-specific
material that cannot stay lean in the body.

## Availability and advisory behavior

Use topic-scoped help as the first pack-specific lookup:

```python
ot.help(query="<pack>", topic="workflow")
ot.help(query="<pack>", topic="setup")
```

Use `ot.tool_info(name="<pack>.<tool>")` or
`ot.tools(pattern="<pack>.", info="signatures")` when the next decision needs an
exact callable contract. Selectively installed skills must work without a
physical `ot-ref` directory or repository checkout.

When a pack, extra, credential, executable, server, connection, or renderer is unavailable:

1. stop before attempting the capability;
2. state the missing requirement plainly;
3. offer installation or configuration guidance; and
4. do not install, configure, start services, or add credentials without a separate request.

Interpret a more specific prerequisite error once and follow the same advisory flow. Do not retry
blindly.

## Authored and generated content

Humans author skill bodies, optional sidecars, and genuine pack-specific
references. `just docs-sync` updates only named managed blocks or generated
files:

- every skill's `CATALOG_COVERAGE` block;
- packaged workflow projections under `src/ot/help_resources/workflows/`;
- the stable-only `ot-ref` pack map and tool index;
- public runtime/tool projections and pack summaries.

Never edit between generated markers. Public and skill tool indexes may differ:
the public reference includes documented beta packs, while all skill artifacts
exclude beta packs that have no owner.

Installed skill paths vary, so capability guides refer to `ot-ref` by name and fall back to live
discovery. Do not use repository-root links, sibling traversal, or symlinks to its index.

## Router maintenance

`ot-ask` routes by user situation, names every guidance owner, distinguishes missing runtime packs
from missing skill guides, and offers short ordered sequences only when order matters. Route missing
requirements/config to `ot-setup`, runtime operations to `ot-runtime`, and outbound MCP lifecycle
work to `ot-mcp-proxy`. It must not name stale skills or duplicate capability workflows.

## Review checklist

- Description has explicit-pack and outcome triggers plus native-host and competing-capability
  exclusions.
- Frontmatter and any present `agents/openai.yaml` agree with the invocation role.
- Every affected pack still has exactly one owner.
- All semantic sections contain enough pack-specific operating judgment.
- Runtime mutations, cost, privacy, and secrets have proportionate guardrails.
- Authored prose stays outside generated markers.
- Router, typed catalog, tests, specs, and docs stay aligned.

Run:

```bash
just docs-sync
just skills-check
just check
```
