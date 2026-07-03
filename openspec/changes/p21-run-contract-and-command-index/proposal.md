# Proposal: run contract rewrite + three-layer command index

## Why

The `run` tool description and connection-time instructions are the one prompt surface shipped to
every session, and they have verified weaknesses: the first runnable example
(`brave.search(query='AI news')`) fails on a fresh install without an API key; the colon rule is
stated three times; the two invocation forms (literal call vs natural-language intent) are never
spelled out side by side; the engine's forgiveness (param prefixes, pack aliases, proxy-name
aliasing) is under-taught; and the advanced reference is wired to a removed surface
(`ot.skills(name='ot-ref')`, removed by `p11-skills-standard-layout`). Meanwhile maintainer field
experience shows an upfront command list materially improves how well an LLM uses OneTool — but
the connection-time prompt must stay lean. The resolution is a deliberate three-layer delivery
model decided by the maintainer on 2026-07-04.

## What Changes

- **Rewrite `src/ot/config/global_templates/prompts.yaml`** (exact target content in
  `design.md` §A — do not redraft it): zero-config examples, colon rule stated once with a
  right/wrong pair, the two invocation forms stated explicitly with a contrasting example,
  affirmative forgiveness line, `ot.skills` pointer replaced with an installed-skill pointer,
  `localhist` added to the pack descriptions. Connection-time instructions stay lean — **no pack
  list is inlined; the `{pack_summary}` placeholder mechanism is removed** (maintainer ruling).
- **Rewrite the ot-ref skill content** at `skills/ot-ref/` (layout created by
  `p11-skills-standard-layout`): trigger-forward frontmatter `description`, a body structured by
  trigger-time (pack map, call conventions, forgiveness, discovery, how to grep the command
  index), an optional deep-dive `reference/recovery.md`, and a Codex sidecar
  `agents/openai.yaml` with implicit invocation allowed. Exact contents in `design.md` §B–§D.
- **Layer 3 — generated command index**: the build step that produces
  `docs/reference/tools/tool-index.md` (`src/otdev/docsgen/tool_index.py`) also emits
  `skills/ot-ref/reference/tool-index.md` so the full 246-tool signature index installs alongside
  the skill as a greppable file. Never hand-maintained.
- **`ot.tools(info='signatures')`**: new info level returning `pack.tool(sig)  # description`
  one-liners — the same format as the index file — for mid-session pulls of a single pack
  (~200 tokens).
- **Repurpose `_build_pack_summary()`** (`src/ot/server.py:208-238`) as the build-time generator
  for the skill's pack-map section (marker-injected), then delete it and the `{pack_summary}`
  handling from `server.py`. **DECIDED: repurpose, not delete; never re-wire into prompts.yaml.**

## Capabilities

### New Capabilities

- `skill-ot-ref`: content and distribution contract for the ot-ref skill — trigger posture,
  body structure, generated pack map, greppable command-index file, recovery deep-dive.

### Modified Capabilities

- `serve-prompts`: run-description content requirements change (two invocation forms, single
  colon rule, zero-config examples, forgiveness line, skill pointer instead of `ot.skills`,
  no pack-summary injection).
- `tool-ot`: `ot.tools` gains the `signatures` info level.

## Impact

- Files: `src/ot/config/global_templates/prompts.yaml`, `skills/ot-ref/**`,
  `src/ot/meta/_discovery.py` (+ `_constants.py` InfoLevel), `src/ot/server.py` (remove
  `_build_pack_summary`/`{pack_summary}`), `src/otdev/docsgen/tool_index.py` (+ a pack-map
  generator module), docsgen sync scripts, prompt/discovery unit tests.
- **Depends on `p11-skills-standard-layout`** (creates the `skills/ot-ref/` layout and removes
  `ot.skills`). Where p11's serve-prompts delta and this change overlap, **this change's wording
  is the final state**.
- **Depends on `p13-recovery-seams`** only in spirit (ot-ref documents `ot.result` as the primary
  handle idiom, which p13 makes the universal runtime hint); no code dependency.
- `p17-pack-api-consistency` adds the `excalidraw` alias — the generated pack map picks it up
  automatically at regeneration time.
- History (do not re-litigate): `{pack_summary}` was added in `74aba311`, removed in `84f52c14`
  (Apr 30, "improve help discovery") in favor of pull-based discovery; the helper was left dead.
  Field experience since favors an upfront index, but delivered via the skill layer, not the
  connection prompt.
