# Proposal: Demos, proxy walkthrough, and framework-vs-product positioning

## Why

OneTool's roadmap positioning — "a programmable local control plane" — is currently *asserted*,
not *shown*: the pack surface is 27+ packs / 230+ tools, which overwhelms rather than sells. Three
of OneTool's best, most differentiating capabilities are undersold in public docs today:

1. There is no answer anywhere in the docs to the question every evaluator eventually asks —
   "how is this different from FastMCP's own Code Mode?" — even though the answer is sharp and
   already worked out (`wip/release-v3/core-flow-deep-dive.md` §E, quoted below).
2. The MCP-proxy story (any external MCP server becomes a Python namespace, with automatic
   name-aliasing and runtime enable/disable/restart control) has a real, working implementation —
   `chrome_util`/`play_util` are themselves thin proxy wrappers — but **zero walkthrough** in
   `docs/learn/`. `docs/reference/tools/chrome-util.md`/`play-util.md` never frame the two tools
   as companions to the underlying MCP server's own tools.
3. There are no runnable, narrated demonstrations of the undersold capabilities (forgiveness,
   ctx handles, encrypted secrets, proxy self-healing) that a prospective user or a release
   reviewer can watch end-to-end.

V3 is being positioned as "a significant release" (maintainer ruling, `release-v3-report-2.md`
Maintainer Rulings). Executive framing: "the undersold capabilities (encrypted secrets, MCP
proxy, explicit tool control) actually sold" is one of V3's five defining moves. This change is
the adoption-content half of that move: positioning copy, a proxy walkthrough, and a set of
scripted, voice-narrated, CI-replayable demos that double as manual release tests.

This change is **docs/content only** — no runtime behavior changes. It depends on Wave 1/2 changes
landing first (`p11`, `p13`, `p16`, `p17`, `p21`) because several demo scripts exercise their
post-fix behavior (see Impact).

## What Changes

- **Add framework-vs-product positioning content** to `README.md` and `docs/learn/comparison.md`:
  the "framework feature vs. installed product" contrast, adapted verbatim from
  `core-flow-deep-dive.md` §E, answering "how is this different from FastMCP Code Mode?" directly.
- **Add an MCP-proxy walkthrough** — a new `docs/learn/mcp-proxy.md` — covering: any configured MCP
  server as a Python namespace, automatic name-aliasing (`canonicalize_name`), the
  `server=` override pattern used by `chrome_util`/`play_util` as companions to the underlying
  server's own tools, and `ot_servers` (`srv`) runtime control (`enable`/`disable`/`restart`/
  `status`). Linked from `docs/learn/index.md` and added to `mkdocs.yml` nav.
- **Add `docs/learn/demos/`**: seven scripted demo scenarios (copied verbatim from the report, see
  Design), each driven by `onetool direct run` shell scripts (deterministic, replayable,
  CI-testable, and itself a demonstration of the Direct CLI) and voice-narrated through a
  proxied, zero-dependency macOS `say`-wrapping stdio MCP server (`docs/learn/demos/narrator/`) —
  the narrator itself demonstrates the proxy story from item 2. Each demo doubles as a manual
  release test. Per the report's "launch-pick first three" guidance, demos 1–3 are required for
  V3 launch; demos 4–7 ship as backlog/optional scenarios in the same directory.
- **Update `mkdocs.yml` nav** to surface the new proxy walkthrough and demos index under "Learn".

Not in scope (owned elsewhere, see Impact): claims reconciliation (`claims.md` vs
`comparison.md` number agreement) is `p18-docs-debt-sweep`; the rewritten ot-ref skill content
("tools-mastery" fold-in) is `p21-run-contract-and-command-index`.

## Capabilities

### New Capabilities

(none — no new observable runtime behavior)

### Modified Capabilities

- `_nf-docs`: gains new documentation-outcome requirements for capability demonstration content
  (demos), MCP-proxy walkthrough documentation, and framework-vs-product positioning disclosure.
  These are additive requirements (`## ADDED Requirements` in the delta spec) alongside the
  capability's existing requirements — no existing `_nf-docs` requirement's behavior changes.

## Impact

- New files: `docs/learn/mcp-proxy.md`, `docs/learn/demos/index.md`,
  `docs/learn/demos/narrator/say_server.py`, `docs/learn/demos/narrator/README.md`,
  `docs/learn/demos/01-forgiveness.sh` through `docs/learn/demos/07-five-packs-one-block.sh`.
- Modified files: `README.md`, `docs/learn/comparison.md`, `docs/learn/index.md`, `mkdocs.yml`.
- No source code under `src/` changes; no new runtime dependency (the narrator server uses
  `fastmcp`, already a core dependency at `pyproject.toml:23` — `fastmcp>=3.1.1,<4`).
- **Depends on `p11-skills-standard-layout`**: no direct code dependency, but the "launch OneTool
  as MCP" setup steps in each demo script must reference the post-p11 skill install story, not the
  removed `ot.skills()`/`install_skills` surface.
- **Depends on `p13-recovery-seams`**: the forgiveness demo (demo 1) includes a "typo → did-you-mean"
  beat that only works after `ot.tool_info` gains `did_you_mean` (R2 item 12).
- **Depends on `p16-extras-restructure`**: after p16, the `whiteboard` extra is deleted and folded
  into `all` (`all` becomes `util+dev`, which now includes whiteboard). The source report's
  acceptance check reads "fresh `[all]`+whiteboard install"; this proposal's acceptance check uses
  "fresh `[all]` install" only, reflecting that post-p16 state — **this is a deliberate correction
  for the wave dependency, not a silent drift fix** (flagged per workflow rule).
- **Depends on `p17-pack-api-consistency`**: the forgiveness demo's pack-alias beat
  (`wb.draw()`/`excalidraw.draw()`) requires `excalidraw` to gain `pack_aliases=("wb","excalidraw")`
  — as of `main`@`151a52b3`, `src/otdev/tools/excalidraw.py:19-20` only declares
  `pack = "whiteboard"` / `pack_aliases = ("wb",)`; `excalidraw.draw()` does not resolve until p17
  lands.
- **Depends on `p21-run-contract-and-command-index`**: not a code dependency for this change's
  deliverables, but p21 owns the rewritten ot-ref skill / tools-mastery content that the source
  report bundles into the same R4 section (out of scope here, see "What Changes").
- File:line drift flagged during verification: the report cites
  `src/otdev/tools/_inject_base.py:102-133` for the proxy `server=` override pattern; as of
  `main`@`151a52b3` this file lives at `src/otdev/_inject_base.py` (not under `tools/`) — one
  directory level up from the cited path. The cited line range (102-133) still matches the
  `_eval_js`/`_exec_js` functions that take `server: str` and call
  `proxy.call_tool_sync(server, tool, ...)`. Use the corrected path
  `src/otdev/_inject_base.py:102-133` when writing the proxy walkthrough.
