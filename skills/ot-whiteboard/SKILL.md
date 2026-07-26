---
name: ot-whiteboard
description: Use when creating, editing, laying out, annotating, saving, restoring, screenshotting, or sharing a live Excalidraw whiteboard through OneTool. Use ot-diagram for source-based static rendering without a live editable canvas.
user-invocable: false
---

# OneTool Whiteboard

Use `whiteboard` for live editable visual work.

## Capability boundary

Check `__ot ot.packs(pattern='whiteboard', info='min')`, then inspect `whiteboard.boards()` or
`whiteboard.help()`. If `[util]`, Chrome/Chromium, or a live session is missing, stop and offer
installation or configuration guidance; do not install, configure, or start services without a
separate request.

State-only drawing/board operations can work without a live browser; render/screenshot/share/layout
work needs the headed Chrome/Chromium session. Use named boards for alternate scenes, the additive
graph/note DSL for concise creation, and `read_scene`/`sync` for state reconciliation. Load the
complete DSL only when needed with `ot.help(query='whiteboard', topic='dsl')`.

## Workflow

1. Inspect the current scene before editing.
2. Choose graph DSL for connected diagrams and note DSL for structured text.
3. Draw a small first pass, inspect or screenshot it, then refine.
4. Use stable IDs, then refine with style/alignment/layout; sync before reasoning from browser state.
5. Save named state before disruptive changes and verify via `read_scene` or screenshot.
6. Distinguish `clear` (scene), `erase` (targets), `hard_reset` (state/session reset), and
   board/load restore semantics before acting.

## Safety and side effects

Browser lifecycle calls can launch/close a visible session. Drawing is additive unless an explicit
erase/clear/reset/load changes state. `save`, screenshot, and share have different outputs and
privacy effects; inspect exact signatures and never publish/share without authorization. Keep
labels and embedded content free of secrets.

## Verification and recovery

Inspect scene structure, confirm expected IDs/edges/notes, and use a screenshot for rendered layout.
If browser state diverges, call `sync` once; preserve named board state before reset/reload and
avoid repeated browser relaunch loops.

Use stable element IDs for later edits. Keep labels short and never claim the user saw a change
until the rendered scene or screenshot confirms it.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `whiteboard` | `[util]` | `overview`, `workflow`, `setup`, `config`, `dsl` | [reference](https://onetool.beycom.online/reference/tools/whiteboard/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
