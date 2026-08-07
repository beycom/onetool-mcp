# MCP Proxy: any server becomes a Python namespace

OneTool doesn't just expose its own packs — it proxies **any** MCP server you configure and
presents its tools as a Python namespace you call the same way you call a built-in pack. No
OneTool-side code changes: register the server, call its tools.

## Any MCP server is a Python namespace

Configure servers under `servers:` in `onetool.yaml`:

```yaml
servers:
  local_tools:
    type: stdio
    command: npx
    args: ["-y", "some-mcp-server@latest"]
    timeout: 30
  docs_tools:
    type: stdio
    command: uvx
    args: ["docs-mcp-server"]
    tool_prefix: "docs_"     # Strip this prefix so docs_search.query() → search.query()
    inherit_env: true
```

Once connected, every tool the server exposes is callable under the server's name:

```python
local_tools.some_tool(arg="value")
```

Proxied servers appear alongside the built-in packs — `ot.servers()` lists them.

## OAuth authorization survives restarts

HTTP servers configured with `auth.type: oauth` use a public OAuth client with PKCE. OneTool
registers the client with `token_endpoint_auth_method: none`, keeping `client_id` in token-request
forms without also sending HTTP Basic credentials. This supports public PKCE MCP providers such as
Notion without provider-specific configuration.

OAuth client registration, access and refresh tokens, and expiry metadata are persisted in the OS
keychain. Storage is isolated by the OneTool configuration directory and exact MCP endpoint URL, so
restarting OneTool or reconnecting a server reuses valid authorization while separate projects and
endpoints remain isolated. Refresh-token rotation replaces the stored token set automatically.

OneTool refuses OAuth persistence when the active keyring is unavailable or insecure; it does not
fall back to in-memory or plaintext token storage. Connection status keeps safe OAuth diagnostics
such as HTTP status, error code, and description while redacting authorization headers and token
values.

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

## Interactive input stays optional

If a proxied tool requests standard MCP form or URL elicitation while handling `ot.run`, OneTool
forwards it to the client that invoked the request. Form answers and URL consent preserve the
client's accept, decline, or cancel outcome; concurrent callers remain isolated.

This works with interactive clients that advertise the corresponding MCP capability, including
Codex TUI, the Codex app, and interactive Claude Code. Headless clients such as `codex exec`,
`claude -p`, and SDK-driven sessions do not need elicitation: pass every required tool argument
explicitly and the same workflow remains available. If interactive input is required but
unavailable, the elicitation receives a cancel response promptly instead of hanging; the upstream
tool then decides whether its operation stops or continues. A failed operation advises retrying
with explicit arguments.

Elicitation forwarding applies only to proxied calls made during the active `ot.run` request.
Built-in packs do not elicit, and detached fire-and-forget proxy work cannot reuse an expired
request context.

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

A full `ot.reload()` keeps its immediate `"OK: Configuration reloaded"` return
while reconnecting proxy servers in the background on the server event loop.
During that transition readiness reports `connecting`; after cleanup and the
fresh connection attempt finish, readiness reports the real connected or failed
state. Cancelled startup generations are fully cleaned before a fresh generation
can register clients.

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
playwright.browser_navigate(url="https://playwright.dev/")  # the proxied server's own tool
```

They are companions to the proxied server, not alternatives to it. For anything outside
annotation/highlighting, call the underlying server's tools directly under its proxy name (or
whatever name you configure under `servers:` and pass as `server=`).
