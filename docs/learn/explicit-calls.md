# Explicit Tool Calls

OneTool gives you explicit control over tool invocation. You write code, invoke a snippet, or ask the agent to synthesize code; the agent sends the final command to the `run` MCP tool as `run(command="...")`.

## Invocation Modes

OneTool has three modes, selected by the shape after `__run`, `__r`, or `__ot`.

| Shape | Mode | Meaning |
|-------|------|---------|
| Valid Python, inline backticks, or a fenced code block | Code | Execute the Python exactly after prefix/fence stripping |
| `:name key=value` | Snippet | Expand a configured Jinja2 snippet, then execute the generated Python |
| Free-form text naming OneTool or a tool | Natural language to code | Ask the agent to discover args if needed and synthesize the Python |

### Snippet Mode

Jinja2 templates are invoked with `:name`. Values are plain strings; Python syntax does not apply.

```
__run :g q=latest AI tools
__run :pkg_npm packages=react lodash
__run :g q="AI news"
```

- Quotes are optional and stripped (`q=abc` is equivalent to `q="abc"`)
- Param names support prefix abbreviation (`q` resolves to `query` if defined)
- Per-template features, such as pipe batch, belong to the template, not the snippet language

### Code Mode

Python executes directly against the tool namespace.

```
__run brave.search(q="AI news")
__run `ground.search(q='price of gold')`
__run x = foo(text="hello"); x
```

- Python syntax applies: strings must be quoted
- Short param names work: `q` resolves to `query`
- Keyword arguments only: `fn(key="val")` not `fn("val")`
- Backticks and fenced blocks mean "execute this Python", not "rewrite it"

### Natural Language to Code

You can ask the agent to use OneTool without writing the final Python yourself:

```
__run ground.search for the price of gold
Use __run ground.search to find the price of gold.
```

The agent should synthesize the command, using `ot.tool_info(name="pack.tool")` or `ot.help(query="pack.tool")` first if it does not know the tool arguments. If a syntactically valid close call fails, the agent can repair it from the error and retry once.

## Trigger Prefixes

| Prefix | Role |
|--------|------|
| `__run` | Canonical explicit invocation |
| `__r` | Concise alias |
| `__ot` | OneTool alias |

Removed forms such as `>>>`, `mcp__onetool__run`, `__onetool`, and `__ot__run` are not runtime prefixes.

## Invocation Styles

Direct call after the prefix:

```
__run foo(text="hello")
__run multiply(a=8472, b=9384)
```

Multi-line code in a fenced block:

````
__run
```python
metals = ["Gold", "Silver"]
results = {}
for metal in metals:
    results[metal] = brave.search(query=f"{metal} price")
results
```
````

## Complete Examples

```
__run foo(text="hello world")
```

````
__run
```python
msg = "Hello World"
foo(text=msg)
```
````

````
__run
```python
primes = [is_prime(n=i) for i in range(11, 21)]
primes
```
````

## Prompting

If you ask an agent to use OneTool, direct it to call the MCP tool:

```
Use OneTool run(command="brave.search(query='latest AI news', count=5)")
```

If you ask for `use ot brave.search(...)`, the agent should execute `brave.search(...)` through `run` directly, not write Python code locally or call the `onetool` CLI.
