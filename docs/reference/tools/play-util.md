# Play Util

Visual element annotation for a Playwright MCP server - highlight elements, guide users through workflows, and read user selections.

Short alias: `play`

## Highlights

- Inject overlays onto any page and highlight elements with labelled, coloured boxes
- `enable_auto_inject()` persists annotations across page navigations for multi-page sessions
- Multi-step workflow guidance — all steps visible at once via `guide_user`
- Manual selection mode (Ctrl+I) lets users point Claude to page elements

## Functions

| Function | Description |
|----------|-------------|
| `play_util.inject_annotations()` | Load inject.js into the current page (idempotent) |
| `play_util.enable_auto_inject()` | Register inject.js as an init script for all future pages |
| `play_util.highlight_element(selector, ...)` | Highlight elements matching a CSS selector |
| `play_util.scan_annotations()` | Return all current annotations on the page |
| `play_util.clear_annotations()` | Remove all annotations and overlays |
| `play_util.guide_user(task, steps)` | Highlight a sequence of elements for a workflow |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `selector` | str | CSS selector to match elements |
| `label` | str | Text label for the highlight overlay |
| `color` | str | Overlay colour: `"orange"` (default), `"red"`, `"blue"`, `"green"` |
| `element_id` | str | Optional ID for the annotation |
| `task` | str | Description of the guided workflow |
| `steps` | list[dict] | List of `{selector, label, color}` dicts for `guide_user` |
| `server` | str | Playwright-compatible MCP server name. Defaults to `playwright`. |

## Requires

- A Playwright-compatible MCP server must be enabled. By default this pack uses `playwright`; pass `server="..."` to target a compatible server configured under another name.
- When you configure your own external `playwright` MCP server that drives a real Chrome, launch it with `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`, `--disable-component-update`, and `--disable-background-networking` — this avoids an unexpected ~4GB on-device Gemini Nano model download and background networking the first time Chrome is driven over CDP.

## Relationship to the Proxied Server

`play_util` is a thin annotation/highlight layer over the Playwright MCP
server it proxies to — it does not replace that server's own tools.
Calls like `play_util.highlight_element()` and `play_util.guide_user()`
forward to the proxied server via `call_tool_sync(server, tool, ...)`
(see `src/otdev/_inject_base.py`), using the browser eval tool that
server exposes. For anything outside annotation/highlighting
(navigation, screenshots, waiting, network inspection, etc.), call the
underlying server's own tools directly under its proxy name — by default
`playwright`, or whatever name you configure under `servers:` in
`onetool.yaml` and pass as `server=` to `play_util` functions.

## Configuration

### Required

- No required `tools.play_util` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.play_util`.

### Defaults

- OneTool uses the built-in defaults for annotation behavior.
- Requires the `playwright` MCP server. Enable it in `servers.yaml` (persistent):

```yaml
playwright:
  enabled: true
```

Or enable for the current session only: `ot_servers.enable(name="playwright")`

## Examples

```python
# Inject annotations and highlight an element
play_util.inject_annotations()
play_util.highlight_element(selector="button.submit", label="Click here")

# Target a compatible non-default server name
play_util.inject_annotations(server="playwright_proxy")

# Enable auto-inject for multi-page sessions
play_util.enable_auto_inject()

# Guide a user through a multi-step form
play_util.guide_user(
    task="Complete checkout",
    steps=[
        {"selector": "input[name='email']", "label": "1. Enter email"},
        {"selector": "input[name='card']",  "label": "2. Card number"},
        {"selector": "button.pay",          "label": "3. Pay now", "color": "green"},
    ],
)

# Read user selections after Ctrl+I
annotations = play_util.scan_annotations()

# Clear all overlays
play_util.clear_annotations()
```
