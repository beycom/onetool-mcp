---
name: ot-browser-guidance
description: Use when visually showing where to click, highlighting page elements, presenting a browser workflow, or reading a manually selected element through OneTool. Match Chrome DevTools or Playwright annotations to the active proxy.
user-invocable: false
---

# OneTool Browser Guidance

Use `chrome_util` with a Chrome DevTools proxy and `play_util` with a Playwright proxy. Use the
underlying proxy pack—not the annotation helper—for navigation, clicking, typing, and inspection.

## Availability

Inspect `__ot ot.status()` and `__ot ot.servers()`, then check
`__ot ot.packs(pattern='chrome_util', info='min')` or the same call for `play_util`. If `[dev]`,
a browser executable, helper pack, or configured proxy is missing, stop and offer installation
or configuration guidance; do not install, configure, or start services without a separate request.

1. Inspect the live page and verify stable selectors.
2. Inject the matching annotation layer.
3. Highlight one target or a short ordered sequence.
4. Use manual selection when the visual target is ambiguous.
5. Clear overlays after guidance or before unrelated screenshots.

Annotation is not interaction. Never claim a control was used because it was highlighted, and
recover a disconnected proxy at most once before surfacing the failure.
