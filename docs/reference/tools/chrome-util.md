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

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[dev]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `server` | `chrome_devtools` | Provide the Chrome evaluation tool used by annotations | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Relationship to the Proxied Server

`chrome_util` is a thin annotation/highlight layer over the Chrome
DevTools MCP server it proxies to — it does not replace that server's
own tools. Calls like `chrome_util.highlight_element()` and
`chrome_util.guide_user()` forward to the proxied server via
`call_tool_sync(server, tool, ...)` (see `src/otdev/_inject_base.py`),
using the browser eval tool that server exposes. For anything outside
annotation/highlighting (navigation, screenshots, network inspection,
etc.), call the underlying server's own tools directly under its proxy
name — by default `chrome_devtools`, or whatever name you configure
under `servers:` in `onetool.yaml` and pass as `server=` to
`chrome_util` functions.

## Configuration

### Required

- No required `tools.chrome_util` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.chrome_util`.

### Defaults

- OneTool uses the built-in defaults for annotation behavior.
- Requires a compatible MCP server. Verify the current publisher docs, add the
  persistent entry disabled, validate it, then enable it after approval:

```yaml
chrome_devtools:
  enabled: false
```

After validation, enable for the current session with
`ot_servers.enable(name="chrome_devtools")`.

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
