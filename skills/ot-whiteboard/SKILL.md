---
name: ot-whiteboard
description: Use when creating, editing, laying out, annotating, saving, restoring, screenshotting, or sharing a live Excalidraw whiteboard through OneTool. Use ot-diagram for source-based static rendering without a live editable canvas.
user-invocable: false
---

# OneTool Whiteboard

Use `whiteboard` for live editable visual work.

## Availability

Check `__ot ot.packs(pattern='whiteboard', info='min')`, then inspect `whiteboard.boards()` or
`whiteboard.help()`. If `[util]`, Chrome/Chromium, or a live session is missing, stop and offer
installation or configuration guidance; do not install, configure, or start services without a
separate request.

## Workflow

1. Inspect the current scene before editing.
2. Choose graph DSL for connected diagrams and note DSL for structured text.
3. Draw a small first pass, inspect or screenshot it, then refine.
4. Save named state before disruptive changes and verify the final canvas.
5. Clear or restore only with explicit intent.

Use stable element IDs for later edits. Keep labels short and never claim the user saw a change
until the rendered scene or screenshot confirms it.
