# OT Core

Core tools for OneTool introspection and management.

## Highlights

- List and filter available tools, packs, servers, aliases, and snippets
- Check runtime status, API connectivity, and security rules
- Query stored large outputs with pagination and search
- Unified `ot.help()` entry point for discovery across all resource types
- `ot.help(ask="...")` answers a natural-language question using only the deterministic help text narrowed by `query`

## Functions

| Function | Description |
|----------|-------------|
| `ot.help(query, info, ask)` | Unified help - search tools, packs, servers, snippets, aliases; optional ask mode |
| `ot.tools(pattern, info)` | List tools, filter by pattern |
| `ot.tool_info(name, pattern, info)` | Get detailed info (signature, args) for one or more tools |
| `ot.packs(pattern, info)` | List packs (local + MCP), filter by pattern |
| `ot.pack_info(name, info)` | Get detailed info for a specific pack |
| `ot.servers(pattern, info)` | List MCP proxy servers, filter by pattern |
| `ot.server(status)` | Read-only runtime proxy server view |
| `ot_servers.enable(name)` | Enable and connect one proxy server |
| `ot_servers.disable(name)` | Disable and disconnect one proxy server |
| `ot_servers.restart(name)` | Reconnect one proxy server |
| `ot_servers.status(name)` | Detailed status for one proxy server |
| `ot.aliases(pattern, info)` | List aliases, filter by pattern |
| `ot.snippets(pattern, info)` | List snippets, filter by pattern |
| `ot.snippet_info(name, pattern, info)` | Get full definition for a specific snippet |
| `ot.config()` | Show aliases, snippets, and server names |
| `ot.debug(verbose, env_vars, dependencies, prompts)` | Show debug diagnostics |
| `ot.status()` | Check runtime status |
| `ot.version()` | Show OneTool version information |
| `ot.stats(period, tool, output, info)` | Get runtime usage statistics |
| `ot.result(handle, ...)` | Query stored large output with pagination and search |
| `ot.reload()` | Force configuration reload |
| `ot.security(check)` | Check security rules and allowlists |

## Configuration

### Required

- No required `tools.ot` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.ot`.
- `ot.*` reads global OneTool config such as `alias`, `snippets`, `servers`, `prompts`, `security`, and `stats`.

### Defaults

- OneTool uses the global config defaults for aliases, snippets, servers, security, and statistics when those sections are omitted.

## Info Levels

All discovery functions (`help`, `tools`, `tool_info`, `packs`, `pack_info`, `aliases`, `snippets`, `snippet_info`) support an `info` parameter:

| Level | Description |
|-------|-------------|
| `min` | Names only (minimal context) |
| `default` | Name + short description (default) |
| `full` | Complete details |

**List vs Detail functions:**

- **List functions** (`tools`, `packs`, `aliases`, `snippets`): return many items compactly; `default` gives `{name, description}`.
- **Detail functions** (`tool_info`, `pack_info`, `snippet_info`): return deep info like signatures, args, body; `default` gives `{name, signature, args, description, source}`.

When called through `run` with no explicit `__format__`, results default to compact JSON (`json`).
Set `__format__` explicitly to override (for example `json_h`, `yml`, or `yml_h`).

## ot.help()

Unified help entry point - search across tools, packs, servers, snippets, and aliases.

```python
# General help overview
ot.help()

# Exact tool lookup
ot.help(query="brave.search")

# Exact pack lookup
ot.help(query="brave")

# Exact server lookup (MCP proxy servers)
ot.help(query="chrome_devtools")
ot.help(query="github")

# Snippet lookup (prefix with :)
ot.help(query=":b_q")

# Alias lookup
ot.help(query="ws")

# Fuzzy search across all types
ot.help(query="web fetch")
ot.help(query="search", info="min")
```

**Behaviour:**

- No query: Returns general help overview with discovery commands and examples
- Exact server match: Returns server help with status, source, instructions, and tool list
- Exact tool match (contains `.`): Returns detailed tool help with signature, args, returns, example
- Exact pack match: Returns pack help with instructions and tool list
- Snippet match (starts with `:`): Returns snippet definition with params and body
- Alias match: Returns alias mapping and target description
- Fuzzy matches: Groups results by type (Tools, Packs, Snippets, Aliases, Servers) and matches name + description intent
- No matches: Suggests `ot.tools()`, `ot.packs()`, `ot.servers()`, etc. to browse; server/proxy intent also includes `ot_servers.enable(name="...")` recovery

The `info` parameter controls detail level for all search results. `ask` optionally answers a question using the narrowed deterministic help text; it does not call an LLM when `ask` is empty.

**Documentation URLs:**

Help output includes documentation URLs for tools and packs:
`https://onetool.beycom.online/reference/tools/{pack}/`

## ot.tools() / ot.tool_info()

List tools or get detailed info for specific tools.

```python
# List all tools (default: info="default" → {name, description})
ot.tools()

# Filter by name pattern (substring match)
ot.tools(pattern="search")

# Names only
ot.tools(info="min")

# Full details (name, description, source)
ot.tools(pattern="brave.", info="full")

# Get signature + args for a specific tool
ot.tool_info(name="brave.search")

# Get detailed info for all tools in a pack
ot.tool_info(pattern="brave.")

# Minimal: name, signature, args only
ot.tool_info(name="brave.search", info="min")
```

`tools()` returns list-mode info (compact). `tool_info()` returns detail-mode info (signatures, args, returns, examples).

## ot.packs() / ot.pack_info()

List packs or get detailed info for a specific pack.

```python
# List all packs (default: info="default" → {name, description})
ot.packs()

# Filter by pattern
ot.packs(pattern="brav")

# Names only
ot.packs(info="min")

# Full details: {name, source, description, instructions, tool_names}
ot.packs(pattern="brave", info="full")

# Get full markdown detail for a pack
ot.pack_info(name="brave")

# MCP server packs show source="mcp:..."
ot.packs(pattern="chrome_devtools")
```

MCP proxy servers appear as packs with `source: "mcp:{server_name}"`.

## ot.servers()

List configured MCP proxy servers with connection status.

```python
# List all servers (default: info="default" → {name, status, enabled, [call_as], [tool_count]})
ot.servers()

# Filter by pattern
ot.servers(pattern="git")

# Names only
ot.servers(info="min")

# Full structured dicts (status, source, tool_count, tools list)
ot.servers(pattern="chrome_devtools", info="full")
```

Returns server information (operational view):

- `name` - Server name from config
- `status` - Connection status (connected/disconnected)
- `enabled` - Whether server is enabled
- `call_as` - Python-safe identifier (only when name has hyphens, e.g. `billing-service` -> `billing_service`)
- `tool_count` - Number of available tools (only when connected)
- `error` - Connection error (only when disconnected with error)

With `info="full"`, returns structured dicts also including `source` and `tools` list.
For guidance, instructions, and examples, use `ot.help(query="<server_name>")` instead.

## ot.server()

Read-only runtime proxy server view.

```python
# List all servers with status
ot.server()

# Show detailed status for a server
ot.server(status="devtools")

```

For state changes, use `ot_servers`:

```python
ot_servers.enable(name="devtools-auto")
ot_servers.disable(name="devtools")
ot_servers.restart(name="playwright")
ot_servers.status(name="playwright")
```

## ot.aliases()

List aliases, filter by pattern.

```python
# List all aliases (default: info="default" → [{name, target}])
ot.aliases()

# Filter by pattern (matches alias name or target)
ot.aliases(pattern="search")

# Names only
ot.aliases(info="min")
```

Aliases are defined in config:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: webfetch.fetch
```

## ot.snippets() / ot.snippet_info()

List snippets or get the full definition for one or more snippets.

```python
# List all snippets (default: info="default" → [{name, description}])
ot.snippets()

# Filter by pattern (matches name or description)
ot.snippets(pattern="search")

# Names only
ot.snippets(info="min")

# Include params in listing — params are dicts with required/default/description
ot.snippets(info="full")

# Get full definition for a specific snippet (exact name → single dict)
ot.snippet_info(name="rg")

# Get full definition for multiple snippets (pattern → list of dicts)
ot.snippet_info(pattern="mem")
```

Params in `snippet_info` output use an explicit `required` flag:

```yaml
# Required param — no default key, required: true
p: {required: true, description: "Regex pattern to search for"}

# Optional param — has default, no required key
path: {default: ".", description: "Search path"}
```

The `example` field includes required params plus the first optional param with a
meaningful (non-empty, non-false) default, e.g. `:tool name="..." info=default`.

Snippets are defined in config:

```yaml
snippets:
  multi_search:
    description: Search multiple queries
    params:
      queries: { required: true }
    body: |
      results = []
      for q in {{ queries }}:
          results.append(brave.search(query=q))
      "\n---\n".join(results)
```

## ot.config()

Show key configuration values including aliases, snippets, and servers.

```python
ot.config()
```

Returns JSON with:
- `aliases` - configured command aliases
- `snippets` - available snippet templates
- `servers` - configured MCP server names

## ot.status()

Check runtime status.

```python
ot.status()
```

Returns status of:
- OneTool version and Python version
- Config, storage, root MCP transport, and direct API state
- Registry status and tool count
- Proxy status and server connections
- Warnings for degraded runtime components

## ot.debug()

Show installation and runtime diagnostics.

```python
ot.debug()
ot.debug(verbose=True)
ot.debug(env_vars=True, dependencies=True)
ot.debug(prompts=True)
```

## ot.version()

Show current OneTool version and build metadata.

```python
ot.version()
```

## ot.stats()

Get runtime statistics for OneTool usage.

```python
# All-time stats
ot.stats()

# Filter by time period
ot.stats(period="day")
ot.stats(period="week")

# Filter by tool
ot.stats(tool="brave.search")

# Generate HTML report
ot.stats(output="stats.html")

# Control detail level
ot.stats(info="min")      # summary only
ot.stats(info="default")  # summary + top tools (default)
ot.stats(info="full")     # complete details
```

The `info` parameter controls the detail level of the output:

| Level | Description |
|-------|-------------|
| `min` | Summary only — no tools breakdown |
| `default` | Summary + top 10 tools (default) |
| `full` | Complete details with per-tool breakdown |

Returns JSON with:
- `total_calls` - Total number of tool calls
- `success_rate` - Percentage of successful calls
- `context_saved` - Estimated context tokens saved
- `time_saved_ms` - Estimated time saved in milliseconds
- `tools` - Per-tool breakdown (info="default" or "full")

## ot.result()

Query stored large output with pagination, search, and filtering. When a tool output exceeds `max_inline_size`, OneTool stores it through the configured result-store backend and returns a handle. The default backend is `ctx`, so stored summaries include `ctx.toc`, `ctx.ask`, and `ctx.read` follow-up commands.

```python
# First 100 lines (default)
ot.result(handle="abc123")

# Paginate
ot.result(handle="abc123", offset=101, limit=50)

# Filter to matching lines only
ot.result(handle="abc123", search="error")

# Matches + 3 lines of context around each (like grep -C 3)
ot.result(handle="abc123", search="fail", context=3)

# Fuzzy match instead of regex
ot.result(handle="abc123", search="config", fuzzy=True)

# Last 20 lines (useful for logs/output)
ot.result(handle="abc123", tail=20)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `handle` | str | required | Result handle from stored output |
| `offset` | int | 1 | Starting line (1-indexed, like Claude's Read tool) |
| `limit` | int | 100 | Max lines to return |
| `search` | str | `""` | Regex pattern to filter lines |
| `fuzzy` | bool | `False` | Use fuzzy matching instead of regex |
| `tail` | int | 0 | Return last N lines (ignores offset/search when set) |
| `context` | int | 0 | Lines before/after each search match |

**Response fields:**

| Field | Description |
|-------|-------------|
| `content` | Matching lines as a single newline-separated string |
| `total_lines` | Total lines in stored result (after search filter) |
| `returned` | Number of lines returned in this chunk |
| `offset` | Starting offset used |
| `has_more` | True if more lines exist after this chunk |
| `progress` | Human-readable position, e.g. `"lines 1-50 of 343 (15%)"` |
| `total_size_bytes` | Full size of stored result in bytes |
| `next_query` | Ready-to-run call to fetch the next chunk (omitted when `has_more=False`) |

## ot.reload()

Force reload of all configuration.

```python
ot.reload()
```

Clears cached configuration and reloads from disk. Use after modifying config files during a session.
It also resets selected tool runtime caches that depend on config/secrets so subsequent calls pick up current values immediately.

## ot.security()

Check security rules and allowlists.

```python
# Summary of all security rules
ot.security()

# Check specific pattern
ot.security(check="json")         # → allowed (in imports.allow)
ot.security(check="pickle.load")  # → blocked (matches calls.block)
ot.security(check="exec")         # → blocked (not in builtins.allow)
ot.security(check="brave.search") # → allowed (tool namespace)
```

Returns:

- Without `check`: Summary with counts and samples for each category (builtins, imports, calls, dunders, tool namespaces)
- With `check`: Status dict with `pattern`, `status` (allowed/blocked/warned), `category`, and `reason`

Use this to understand why code is being blocked or to verify security configuration.
