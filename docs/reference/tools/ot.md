# ot.* Internal Tools

**Introspect. Configure. Manage. OneTool from the inside.**

Internal tools for OneTool introspection and management.

## Functions

| Function | Description |
|----------|-------------|
| `ot.tools()` | List all available tools and their signatures |
| `ot.push(topic, message)` | Publish message to configured topic |
| `ot.config(path)` | Get configuration value by dotted path |
| `ot.health()` | Check tool dependencies and API connectivity |
| `ot.help(tool)` | Get detailed help for a specific tool |
| `ot.alias()` | List configured aliases |
| `ot.snippet(name)` | Get snippet by name |

## ot.tools()

List all available tools with signatures.

```python
ot.tools()
```

Returns YAML-formatted list of all registered tools.

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
      - topic: notes
        file: .notes/inbox.md
      - topic: ideas
        file: .notes/ideas.md
```

## ot.config()

Get configuration values by dotted path.

```python
# Get timeout setting
ot.config(path="tools.brave.timeout")

# Get all tool configs
ot.config(path="tools")
```

## ot.health()

Check system health and API connectivity.

```python
ot.health()
```

Returns status of:
- Required API keys
- External dependencies (ripgrep, playwright)
- Database connections

## ot.help()

Get detailed documentation for a tool.

```python
ot.help(tool="brave.search")
```

## ot.alias()

List configured aliases.

```python
ot.alias()
```

Aliases are defined in config:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: web.fetch
```

## ot.snippet()

Get or execute a snippet template.

```python
ot.snippet(name="multi_search")
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

## Related

- [Configuration](../../getting-started/configuration.md) - Full config schema
- [Creating Tools](../../extending/creating-tools.md) - Add custom tools
