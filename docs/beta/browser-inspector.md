# Browser Inspector Tool

Observe and debug frontend applications. User controls the browser, LLM observes.

## Setup

```bash
# Install Playwright browser (one-time)
playwright install chromium
```

## Quick Start

```bash
# Start the client
just client
```

Then ask the LLM to use the browser tools:

```text
You: Open https://example.com in a browser

__onetool__run browser_open(url="https://en.wikipedia.org/wiki/The_Age")


```

## Available Tools

| Tool                        | Purpose                                  |
| --------------------------- | ---------------------------------------- |
| `browser_open(url)`         | Launch browser and navigate to URL       |
| `browser_close()`           | Close browser session                    |
| `browser_capture()`         | Take screenshot, get HTML, accessibility |
| `browser_selection()`       | Get element user selected                |
| `browser_inspect(selector)` | Deep CSS/box model inspection            |
| `browser_console()`         | Get console errors                       |
| `browser_network()`         | Get network requests                     |
| `browser_api()`             | Get XHR/fetch API calls                  |
| `browser_resources()`       | List page resources                      |
| `browser_changes(action)`   | Track DOM mutations                      |

## Example Workflows

### Debug a page

```text
You: Open my app at localhost:3000 and check for errors

# LLM opens browser, captures console errors and network failures
```

### Inspect an element

```text
You: Enable selection mode so I can pick an element

# LLM enables selection, you click element in browser

You: What styles are applied to my selection?

# LLM inspects element, shows computed CSS and matched rules
```

### Track API calls

```text
You: Open the app and show me all API requests

# LLM opens browser, you interact with the app

You: What API calls were made?

# LLM shows XHR/fetch requests with request/response bodies
```

### Connect to existing Chrome

```bash
# Start Chrome with debugging enabled
google-chrome --remote-debugging-port=9222

# Or on macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

```text
You: Connect to my existing Chrome browser

LLM: __onetool__run browser_open(connect=True)
```

## Direct Python Usage

```python
from tools.browser_inspector import browser_open, browser_capture, browser_close

# Open browser
browser_open(url="https://en.wikipedia.org/wiki/The_Age")

# Take screenshot
result = browser_capture(screenshot=True, html=True)

# Clean up
browser_close()
```