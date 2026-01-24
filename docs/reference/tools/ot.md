# ot.* Internal Tools

**Introspect. Configure. Manage. OneTool from the inside.**

Internal tools for OneTool introspection and management.

## Highlights

- List and filter available tools with signatures
- Check system health and API connectivity
- Access configuration, aliases, and snippets
- Publish messages to configured topics

## Functions

| Function | Description |
|----------|-------------|
| `ot.tools(pattern, pack, compact)` | List all available tools and their signatures |
| `ot.push(topic, message)` | Publish message to configured topic |
| `ot.config()` | Show aliases, snippets, and server names |
| `ot.health()` | Check tool dependencies and API connectivity |
| `ot.help(tool)` | Get detailed help for a specific tool |
| `ot.instructions(pack)` | Get usage instructions for a pack |
| `ot.alias(name)` | Show alias definition (use `*` to list all) |
| `ot.snippet(name)` | Show snippet definition (use `*` to list all) |
| `ot.stats(period, tool, output)` | Get runtime usage statistics |

## ot.tools()

List all available tools with signatures.

```python
# List all tools
ot.tools()

# Filter by name pattern
ot.tools(pattern="search")

# Filter by pack
ot.tools(pack="brave")

# Compact output (name and description only)
ot.tools(compact=True)
```

Returns JSON-formatted list of all registered tools.

## ot.push()

Publish a message to a configured topic.

```python
ot.push(topic="notes", message="Remember to review PR #123")
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

## ot.help()

Get detailed documentation for a tool.

```python
ot.help(tool="brave.search")
ot.help(tool="ot.tools")
```

Returns formatted help with signature, args, returns, and examples.

## ot.instructions()

Get usage instructions for a pack.

```python
ot.instructions(pack="brave")
ot.instructions(pack="github")
```

Returns instructions from `prompts.yaml` if configured, otherwise generates from tool docstrings.

## ot.alias()

Show alias definition or list all aliases.

```python
# Show specific alias
ot.alias(name="ws")

# List all aliases
ot.alias(name="*")
```

Aliases are defined in config:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: web.fetch
```

## ot.snippet()

Show snippet definition or list all snippets.

```python
# Show specific snippet
ot.snippet(name="multi_search")

# List all snippets
ot.snippet(name="*")
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

## Source

OneTool internal implementation