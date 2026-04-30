# Playwright MCP

Browser automation via Playwright accessibility tree. No vision or screenshots required — Playwright represents pages as a structured accessibility snapshot that Claude can navigate directly.

**Source:** [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)

## Enabling

The server is included in `servers.yaml` with `enabled: false`. To activate it permanently:

```yaml
playwright:
  enabled: true
```

Or enable for the current session only:

```python
ot_servers.enable(name="playwright")
```

## Server Config

```yaml
playwright:
  type: stdio
  command: npx
  args:
    - "@playwright/mcp@latest"
  timeout: 120
  enabled: true
```

### Options

Add to the `args` array to customise behaviour:

| Option | Description |
|--------|-------------|
| `--headless` | Run without a visible browser window |
| `--browser=firefox` | Use Firefox or WebKit instead of Chromium |
| `--viewport=WxH` | Set viewport size (e.g., `1280x720`) |

## Tools

- **Navigation**: `browser_navigate`, `browser_back`, `browser_forward`, `browser_wait`
- **Interaction**: `browser_click`, `browser_type`, `browser_select_option`, `browser_press_key`
- **State**: `browser_snapshot`, `browser_screenshot`, `browser_evaluate`
- **Tabs**: `browser_tab_list`, `browser_tab_new`, `browser_tab_select`, `browser_tab_close`

## Element Annotations (`play_util`)

The `play_util` pack adds visual annotation tools on top of this server — highlight elements, guide users through workflows, and let users point Claude to elements with ++ctrl+i++.

See [play_util reference](../tools/play-util.md) for the full API.

## Usage Patterns

- Prefer `browser_snapshot` over `browser_screenshot` — it's faster and doesn't require vision
- Standard flow: `browser_navigate` → `browser_snapshot` → `browser_click/type` → `browser_snapshot`
- Use `browser_evaluate` for custom JS execution
- Use `browser_screenshot` only for visual verification when the accessibility tree is insufficient

## Verification Checklist

Use these checks after enabling the server:

```python
ot.servers(pattern="playwright", info="full")
ot.packs(pattern="play")
ot.tool_info(pattern="playwright.")
```

## Examples

### 1. Read a page without vision

Use the accessibility snapshot to understand page structure without a screenshot.

```python
playwright.browser_navigate(url="https://en.wikipedia.org/wiki/Anthropic")
playwright.browser_snapshot()
# Returns structured YAML accessibility tree — headings, links, buttons, text
```

### 2. Extract all headings from a page

Pull structured content with JavaScript — no selectors library needed.

```python
playwright.browser_navigate(url="https://en.wikipedia.org/wiki/Anthropic")
playwright.browser_evaluate(
    function="() => Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim())"
)
# Returns: ["Contents", "History", "Business structure", "Product", ...]
```

### 3. Fill and submit a login form

Automate authentication flows end-to-end.

```python
playwright.browser_navigate(url="https://myapp.com/login")
playwright.browser_snapshot()  # Check form field names first
playwright.browser_fill_form(fields=[
    {"selector": "input[name='email']", "value": "user@myapp.com"},
    {"selector": "input[name='password']", "value": "secure123"},
])
playwright.browser_click(element="Submit button", ref="...")
playwright.browser_snapshot()  # Verify logged in
```

### 4. Scrape a data table

Extract all rows from an HTML table as a list of records.

```python
playwright.browser_navigate(url="https://myapp.com/pricing")
playwright.browser_evaluate(
    function="""() => {
        const rows = Array.from(document.querySelectorAll('table tr'));
        return rows.map(r => Array.from(r.querySelectorAll('td,th')).map(c => c.textContent.trim()));
    }"""
)
```

### 5. Test a multi-step checkout flow

Walk through a user journey and verify state at each step.

```python
playwright.browser_navigate(url="https://shop.myapp.com/product/1")
playwright.browser_snapshot()
playwright.browser_click(element="Add to cart button")
playwright.browser_snapshot()  # Verify cart updated
playwright.browser_navigate(url="https://shop.myapp.com/cart")
playwright.browser_snapshot()  # Verify item in cart
playwright.browser_take_screenshot()
```

### 6. Test mobile viewport rendering

Check how a page looks at phone dimensions.

```python
playwright.browser_navigate(url="https://myapp.com")
playwright.browser_resize(width=390, height=844)   # iPhone 14
playwright.browser_snapshot()
playwright.browser_take_screenshot()
playwright.browser_resize(width=1280, height=720)  # Reset to desktop
```

### 7. Highlight page elements for user guidance

Use the annotation overlay to visually guide a user through a workflow.

```python
playwright.browser_navigate(url="https://myapp.com/settings")
play_util.inject_annotations()
play_util.guide_user(
    task="Update your profile",
    steps=[
        {"selector": "input[name='display_name']", "label": "1. Edit name"},
        {"selector": "input[name='email']", "label": "2. Confirm email"},
        {"selector": "button[type='submit']", "label": "3. Save", "color": "green"},
    ],
)
playwright.browser_take_screenshot()
```

### 8. Monitor console errors during navigation

Detect JavaScript errors thrown during page load.

```python
playwright.browser_navigate(url="https://myapp.com")
playwright.browser_console_messages()
# Look for level="error" entries — useful for regression checks
```

## Common Mistakes to Avoid

- Don't assume elements exist — use `browser_snapshot` first
- Don't skip snapshots between actions
- Don't use `browser_screenshot` when `browser_snapshot` is sufficient
