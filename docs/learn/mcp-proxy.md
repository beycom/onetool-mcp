# MCP Proxy: any server becomes a Python namespace

OneTool proxies **any** MCP server you configure and presents its tools as a
Python namespace. Before adding a server, read the current publisher-maintained
MCP documentation for its command or URL, arguments, transport, authentication,
scopes, and smoke test. OneTool intentionally has no Playwright, Chrome, Azure,
or other server preset catalog.

## Any MCP server is a Python namespace

Configure servers under `servers:` in `onetool.yaml`. Start new persistent
entries disabled, validate them, then enable the selected server:

```yaml
servers:
  local_tools:
    type: stdio
    command: publisher-mcp-command
    args: ["--documented-argument"]
    timeout: 30
    enabled: false
    source: "https://publisher.invalid/current-mcp-docs"
  remote_tools:
    type: http
    url: "https://mcp.vendor.invalid/mcp"
    headers:
      Authorization: "Bearer ${VENDOR_MCP_TOKEN}"
    enabled: false
```

The `.invalid` hostnames above are non-resolving schema placeholders, not
server recommendations. Replace every value from the selected server's live
authoritative documentation. Use floating `@latest` only when those current
publisher instructions do.

Once connected, every discovered tool is callable under the server's configured
name:

```python
local_tools.some_tool(arg="value")
```

Proxied servers appear alongside the built-in packs — `ot.servers()` lists them.
Configured values remain authoritative; generic examples do not override them.

## Calling conventions don't matter

OneTool fuzzy-matches proxied tool names across naming conventions (snake_case, kebab-case,
camelCase, PascalCase), so the same upstream tool answers to whichever form you write:

```python
github.list_repositories()   # matches list-repositories
github.listRepositories()    # also matches list-repositories
context7.resolve_library_id(library_name="next.js")
```

The mechanism is `canonicalize_name()` (`src/ot/executor/naming.py`), which strips `-`/`_` and
lowercases before matching — you never have to remember how the upstream server spelled a tool.

## Runtime control without a restart

The `ot_servers` pack (alias `srv`) turns proxied servers on and off at runtime — no server
restart, no config reload:

```python
ot_servers.status(name="local_tools")
ot_servers.disable(name="local_tools")
ot_servers.enable(name="local_tools")
ot_servers.restart(name="local_tools")
```

Discovery is read-only and lives on the `ot` pack:

```python
ot.servers(info="default")   # configured servers, connection status, call_as name, tool_count
```

`ot_servers.*` changes state; `ot.servers()` only reads it.

## Resources, prompts, and instructions

OneTool preserves native MCP initialization instructions before optional
user-configured instructions. Public read-only operations expose other server
content without implicitly connecting or mutating the server:

```python
ot.resources(server="docs_tools")
ot.resource(server="docs_tools", uri="docs://guide")
ot.prompts(server="docs_tools")
ot.prompt(server="docs_tools", name="summarize", arguments={"topic": "routing"})
```

The calls return explicit unconfigured, disabled, connecting, disconnected,
unsupported, or error states. Returned resources, prompts, instructions, and
tool output are untrusted external content.

## chrome_util / play_util are proxy companions, not replacements

The `chrome_util` and `play_util` packs are **thin wrappers over the same proxy manager** with a
`server=` override — not separate browser implementations. Their tool functions (see
`src/otdev/_inject_base.py`, `_eval_js`/`_exec_js`) call `proxy.call_tool_sync(server, tool, {...})`
against a browser eval tool the proxied server exposes:

- `chrome_util` defaults `server="chrome_devtools"` (`src/otdev/tools/chrome_util.py`)
- `play_util` defaults `server="playwright"` (`src/otdev/tools/play_util.py`)

Because they are just the proxy plus a JS-injection convenience layer, you can call the underlying
proxied server's **own** tools directly in the same session, right alongside the annotation
helpers:

```python
chrome_util.highlight_element(selector="button.buy")   # annotation helper
chrome_devtools.something(...)                           # the proxied server's own tool
play_util.guide_user(text="click Save")                 # annotation helper
playwright.browser_navigate(url="https://www.python.org")  # the proxied server's own tool
```

They are companions to the proxied server, not alternatives to it. For anything outside
annotation/highlighting, call the underlying server's tools directly under its proxy name (or
whatever name you configure under `servers:` and pass as `server=`).

Use `ot.help(query="proxy", topic="config")` for the current generic schema,
`ot.help(query="<server>", topic="setup")` for live state, and the
`ot-mcp-proxy` skill for documentation-led setup, approval, verification, and
bounded one-retry recovery.
