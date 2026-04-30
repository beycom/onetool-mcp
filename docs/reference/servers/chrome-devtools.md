# Chrome DevTools MCP

Browser automation, debugging, and element annotation via Chrome DevTools Protocol.

**Source:** [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)

## Enabling

The server is included in `servers.yaml` with `enabled: false`. To activate it permanently:

```yaml
chrome_devtools:
  enabled: true
```

Or enable for the current session only:

```python
ot_servers.enable(name="chrome_devtools")
```

## Server Config

```yaml
chrome_devtools:
  type: stdio
  command: npx
  args:
    - "-y"
    - "chrome-devtools-mcp@latest"
    - "--isolated"
    - "--viewport=1280x720"
  timeout: 120
  enabled: true
```

### Options

Add to the `args` array to customise behaviour:

| Option | Description |
|--------|-------------|
| `--isolated` | Temporary Chrome profile, auto-cleaned on close (default) |
| `--browserUrl=http://localhost:9222` | Connect to an existing Chrome instance |
| `--autoConnect` | Attach to any Chrome with remote debugging enabled |
| `--headless=true` | Run without a visible browser window |
| `--viewport=WxH` | Set viewport size (e.g., `1280x720`) |

!!! note
    Chrome 136+ requires `--user-data-dir` when launching with `--remote-debugging-port`.

## Tools

- **Navigation**: `navigate_page`, `new_page`, `select_page`, `close_page`, `list_pages`, `wait_for`
- **Interaction**: `click`, `fill`, `fill_form`, `press_key`, `hover`, `drag`, `upload_file`, `handle_dialog`
- **Inspection**: `evaluate_script`, `list_console_messages`, `list_network_requests`, `get_network_request`, `take_screenshot`, `take_snapshot`
- **Performance**: `performance_start_trace`, `performance_stop_trace`, `performance_analyze_insight`
- **Viewport**: `resize_page`, `emulate`

## Element Annotations (`chrome_util`)

The `chrome_util` pack adds visual annotation tools on top of this server — highlight elements, guide users through workflows, and let users point Claude to elements with ++ctrl+i++.

See [chrome_util reference](../tools/chrome-util.md) for the full API.

## Usage Patterns

- Standard flow: `navigate_page` → `take_screenshot` → `click/fill` → `take_screenshot`
- Use `take_snapshot` for a text/accessibility view instead of a screenshot
- Use `evaluate_script` for custom JS — takes a `function` string: `"() => document.title"`
- Use `list_network_requests` after navigation to inspect all HTTP traffic
- Use remote mode (`--browserUrl`) to preserve an existing logged-in session

## Verification Checklist

Use these checks after enabling the server:

```python
ot.servers(pattern="chrome_devtools", info="full")
ot.packs(pattern="chrome")
ot.tool_info(pattern="chrome_devtools.")
```

## Examples

### 1. Scrape structured data from a page

Extract article headings from any web page as a Python list.

```python
chrome_devtools.navigate_page(url="https://en.wikipedia.org/wiki/Anthropic")
chrome_devtools.wait_for(text="Contents")
chrome_devtools.evaluate_script(
    function="() => Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim())"
)
# Returns: ["Contents", "History", "Business structure", "Product", ...]
```

### 2. Audit all network requests on a page

See every HTTP request a page makes — useful for mapping API endpoints or auditing third-party calls.

```python
chrome_devtools.navigate_page(url="https://myapp.com/dashboard")
chrome_devtools.list_network_requests()
chrome_devtools.evaluate_script(
    function="() => performance.getEntriesByType('resource').map(r => ({url: r.name, duration: Math.round(r.duration)}))"
)
```

### 3. Detect and read JavaScript console errors

Capture any errors thrown during page load — useful for debugging or regression checks.

```python
chrome_devtools.navigate_page(url="https://myapp.com")
chrome_devtools.list_console_messages()
# Look for type="error" entries in the output
```

### 4. Emulate a mobile device

Test how a page renders on a phone without a physical device.

```python
chrome_devtools.navigate_page(url="https://myapp.com")
chrome_devtools.resize_page(width=390, height=844)   # iPhone 14 dimensions
chrome_devtools.take_screenshot()
chrome_devtools.resize_page(width=1280, height=720)  # Reset to desktop
```

### 5. Multi-tab comparison

Open two pages and compare their state — useful for A/B testing or before/after checks.

```python
chrome_devtools.navigate_page(url="https://myapp.com/pricing?plan=free")
chrome_devtools.new_page(url="https://myapp.com/pricing?plan=pro")
chrome_devtools.take_screenshot()
chrome_devtools.select_page(index=1)
chrome_devtools.take_screenshot()
```

### 6. Extract all links from a page

Collect every anchor href — useful for link audits or crawl preparation.

```python
chrome_devtools.navigate_page(url="https://docs.myapp.com")
chrome_devtools.evaluate_script(
    function="() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(h => h.startsWith('https'))"
)
```

### 7. Profile page load performance

Measure how long a page takes to load and identify bottlenecks.

```python
chrome_devtools.performance_start_trace()
chrome_devtools.navigate_page(url="https://myapp.com")
chrome_devtools.wait_for(text="Example Domain")
chrome_devtools.performance_stop_trace()
chrome_devtools.performance_analyze_insight()
```

### 8. Guide a user through a workflow

Visually walk the user through a multi-step process with labelled overlays.

```python
chrome_devtools.navigate_page(url="https://myapp.com/settings")
chrome_util.inject_annotations()
chrome_util.guide_user(
    task="Update profile",
    steps=[
        {"selector": "input[name='display_name']", "label": "1. Edit name"},
        {"selector": "input[name='email']", "label": "2. Confirm email"},
        {"selector": "button.save", "label": "3. Save", "color": "green"},
    ],
)
chrome_devtools.take_screenshot()
```

## Common Mistakes to Avoid

- Don't interact with elements before the page has loaded — use `wait_for` first
- Don't use `expression=` with `evaluate_script` — the parameter is `function=` and takes a JS function string
- Use remote mode (`--browserUrl`) when you need to preserve an existing session; isolated mode always starts fresh
