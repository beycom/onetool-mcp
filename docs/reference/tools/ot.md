# ot.* Internal Tools

**Introspect. Configure. Manage. OneTool from the inside.**

Internal tools for OneTool introspection and management.

## Highlights

- List and filter available tools and packs
- Check system health and API connectivity
- Access configuration, aliases, and snippets
- Publish messages to configured topics

## Functions

| Function | Description |
|----------|-------------|
| `ot.tools(name, pattern, pack, compact)` | List tools, filter by pattern, or get one by name |
| `ot.packs(name, pattern)` | List packs, filter by pattern, or get one with instructions |
| `ot.aliases(name, pattern)` | List aliases, filter by pattern, or get one by name |
| `ot.snippets(name, pattern)` | List snippets, filter by pattern, or get one by name |
| `ot.config()` | Show aliases, snippets, and server names |
| `ot.health()` | Check tool dependencies and API connectivity |
| `ot.stats(period, tool, output)` | Get runtime usage statistics |
| `ot.notify(topic, message)` | Publish message to configured topic |
| `ot.reload()` | Force configuration reload |

## ot.tools()

List all available tools with signatures, filter by pattern, or get a specific tool.

```python
# List all tools
ot.tools()

# Get specific tool by name (includes full documentation)
ot.tools(name="brave.search")

# Filter by name pattern (substring match)
ot.tools(pattern="search")

# Filter by pack
ot.tools(pack="brave")

# Compact output (name and description only)
ot.tools(compact=True)
```

Returns a list of tool dicts, or a single tool dict when using `name=`.

## ot.packs()

List all packs or get detailed pack info with instructions.

```python
# List all packs
ot.packs()

# Get specific pack by name (includes instructions and tool list)
ot.packs(name="brave")

# Filter by pattern
ot.packs(pattern="brav")
```

Returns a list of pack summaries, or detailed pack info when using `name=`.

## ot.aliases()

List aliases, filter by pattern, or get a specific alias.

```python
# List all aliases
ot.aliases()

# Get specific alias by name
ot.aliases(name="ws")

# Filter by pattern (matches alias name or target)
ot.aliases(pattern="search")
```

Aliases are defined in config:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: web.fetch
```

## ot.snippets()

List snippets, filter by pattern, or get a specific snippet definition.

```python
# List all snippets
ot.snippets()

# Get specific snippet by name (shows full definition)
ot.snippets(name="multi_search")

# Filter by pattern (matches name or description)
ot.snippets(pattern="search")
```

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

## ot.health()

Check system health and API connectivity.

```python
ot.health()
```

Returns status of:
- OneTool version and Python version
- Registry status and tool count
- Proxy status and server connections

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
```

Returns JSON with:
- `total_calls` - Total number of tool calls
- `success_rate` - Percentage of successful calls
- `context_saved` - Estimated context tokens saved
- `time_saved_ms` - Estimated time saved in milliseconds
- `tools` - Per-tool breakdown

## ot.notify()

Publish a message to a configured topic.

```python
ot.notify(topic="notes", message="Remember to review PR #123")
```

Configure topics in `ot-serve.yaml`:

```yaml
tools:
  msg:
    topics:
      - pattern: "notes"
        file: .notes/inbox.md
      - pattern: "ideas"
        file: .notes/ideas.md
```

## ot.reload()

Force reload of all configuration.

```python
ot.reload()
```

Clears cached configuration and reloads from disk. Use after modifying config files during a session.

## Source

OneTool internal implementation
