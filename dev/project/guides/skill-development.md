# Skill Development

Canonical guide for OneTool skills under `skills/`.

## Roles

- **Shared reference (`ot-ref`)** owns generic call mechanics, discovery, aliases, recovery, the
  generated pack map, and the complete greppable tool index.
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

## Ownership

`src/otdev/docsgen/metadata.py` is the reviewed catalog source:

- `PackDocs.skill_owner` assigns every built-in pack exactly one guidance owner.
- `CURATED_SKILLS` defines the 20 distributed skills.
- `PROFILE_SKILLS` is the acceptance oracle for public profile membership.

Do not create another pack-owner mapping. Additions, renames, and removals must update the skill
directory, metadata, router, tests, and affected specs together. Dynamically proxied MCP packs are
outside static ownership.

## Lean capability body

Aim for the shortest useful operating guide, normally 15–40 lines:

1. capability boundary;
2. availability preflight when runtime support is conditional;
3. shortest safe workflow;
4. verification where success is not obvious;
5. material mutation, cost, privacy, or secret guardrails; and
6. pack-specific recovery not already in `ot-ref`.

Do not copy signatures, aliases, generic call syntax, or user reference documentation. Do not add
a generated tool index per skill. A local reference is justified only for genuinely pack-specific
material that cannot stay lean in the body.

## Availability and advisory behavior

Use the smallest relevant live lookup:

```python
__ot ot.packs(pattern="<pack>", info="min")
```

After confirming a pack, use `ot.pack_info`, `ot.status`, a server status call, or
`ot.tool_info(name="<pack>.<tool>")` only when the next decision needs it. Selectively installed
skills must work without a physical `ot-ref` directory.

When a pack, extra, credential, executable, server, connection, or renderer is unavailable:

1. stop before attempting the capability;
2. state the missing requirement plainly;
3. offer installation or configuration guidance; and
4. do not install, configure, start services, or add credentials without a separate request.

Interpret a more specific prerequisite error once and follow the same advisory flow. Do not retry
blindly.

## Authored and generated content

Humans author skill bodies, optional sidecars, and genuine pack-specific references.
`just docs-sync` regenerates the `ot-ref` pack map and central index. The runtime registry is canonical; the
`docs/reference/tools/tool-index.md` and `skills/ot-ref/reference/tool-index.md` copies must remain
byte-identical.

Installed skill paths vary, so capability guides refer to `ot-ref` by name and fall back to live
discovery. Do not use repository-root links, sibling traversal, or symlinks to its index.

## Router maintenance

`ot-ask` routes by user situation, names every guidance owner, distinguishes missing runtime packs
from missing skill guides, and offers short ordered sequences only when order matters. It must not
name stale skills or duplicate capability workflows.

## Review checklist

- Description has explicit-pack and outcome triggers plus native-host and competing-capability
  exclusions.
- Frontmatter and any present `agents/openai.yaml` agree with the invocation role.
- Every affected pack still has exactly one owner.
- Capability body is lean, advisory, and avoids shared mechanics.
- Runtime mutations, cost, privacy, and secrets have proportionate guardrails.
- Router, metadata, tests, specs, and docs stay aligned.

Run:

```bash
just docs-sync
just skills-check
just check
```
