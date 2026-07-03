# Chrome Util

Visual element annotation for a Chrome DevTools MCP server - highlight elements, guide users through workflows, and read user selections.

Short alias: `chrome`

## Highlights

- Inject overlays onto any page and highlight elements with labelled, coloured boxes
- Multi-step workflow guidance — all steps visible at once via `guide_user`
- Manual selection mode (Ctrl+I) lets users point Claude to page elements
- Read back all annotations (programmatic and user-created) with `scan_annotations`

## Functions

| Function | Description |
|----------|-------------|
| `chrome_util.inject_annotations()` | Load inject.js into the current page (idempotent) |
| `chrome_util.highlight_element(selector, ...)` | Highlight elements matching a CSS selector |
| `chrome_util.scan_annotations()` | Return all current annotations on the page |
| `chrome_util.clear_annotations()` | Remove all annotations and overlays |
| `chrome_util.guide_user(task, steps)` | Highlight a sequence of elements for a workflow |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `selector` | str | CSS selector to match elements |
| `label` | str | Text label for the highlight overlay |
| `color` | str | Overlay colour: `"orange"` (default), `"red"`, `"blue"`, `"green"` |
| `element_id` | str | Optional ID for the annotation |
| `task` | str | Description of the guided workflow |
| `steps` | list[dict] | List of `{selector, label, color}` dicts for `guide_user` |
| `server` | str | Chrome DevTools-compatible MCP server name. Defaults to `chrome_devtools`. |

## Requires

- A Chrome DevTools-compatible MCP server must be enabled. By default this pack uses `chrome_devtools`; pass `server="..."` to target a compatible server configured under another name.

## Configuration

### Required

- No required `tools.chrome_util` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.chrome_util`.

### Defaults

- OneTool uses the built-in defaults for annotation behavior.
- Requires the `chrome_devtools` MCP server. Enable it in `servers.yaml` (persistent):

```yaml
chrome_devtools:
  enabled: true
```

Or enable for the current session only: `ot_servers.enable(name="chrome_devtools")`

## Examples

```python
# Inject annotations and highlight an element
chrome_util.inject_annotations()
chrome_util.highlight_element(selector="button.submit", label="Click here")

# Target a compatible non-default server name
chrome_util.inject_annotations(server="chrome_devtool_connect")

# Guide a user through a multi-step form
chrome_util.guide_user(
    task="Complete checkout",
    steps=[
        {"selector": "input[name='email']", "label": "1. Enter email"},
        {"selector": "input[name='card']",  "label": "2. Card number"},
        {"selector": "button.pay",          "label": "3. Pay now", "color": "green"},
    ],
)

# Read user selections after Ctrl+I
annotations = chrome_util.scan_annotations()

# Clear all overlays
chrome_util.clear_annotations()
```
