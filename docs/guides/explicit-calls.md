# Explicit Tool Calls

**Write code. Call APIs. No guessing.**

OneTool's `__ot` prefix gives you explicit control over tool invocation. You write the code - the LLM doesn't have to guess which tool or which parameters.

## Trigger Prefixes

OneTool supports five trigger prefixes. All prefixes support the same three invocation styles.

| Prefix              | Description                    | Recommended |
| ------------------- | ------------------------------ | ----------- |
| `__onetool__run`    | Full name, explicit tool call  | Yes         |
| `__ot`              | Short form                     | Yes         |
| `__onetool`         | Full name, default tool        |             |
| `__ot__run`         | Short name, explicit tool call |             |
| `mcp__onetool__run` | Explicit MCP call              |             |

**Recommended:** Use `__onetool__run` for clarity or `__ot` for brevity.

**Note:** `mcp__ot__run` is NOT a valid prefix.

## Invocation Styles

Each prefix supports three ways to pass code:

### 1. Simple Call

Direct function call after the prefix:

```
__ot sha256(text="hello")
__onetool__run multiply(a=8472, b=9384)
```

### 2. Inline Backticks

Code wrapped in backticks:

```
__ot `sha256(text="hello")`
__onetool__run `multiply(a=8472, b=9384)`
```

### 3. Code Fence

Multi-line code in a fenced block:

```
__onetool__run
```python
metals = ["Gold", "Silver"]
results = {}
for metal in metals:
    results[metal] = brave.web_search(query=f"{metal} price")
results
```

```

## Direct MCP Call

For programmatic or explicit MCP invocation:

```

mcp__onetool__run(command='sha256(text="hello")')

```

## Complete Examples

### Simple Hash Computation

```

__ot sha256(text="hello world")

```

### Multi-step Computation with Variables

```

__onetool__run

```python
msg = "Hello World"
sha256(text=msg)
```

```

### Loop with Multiple Tool Calls

```

__ot

```python
primes = [is_prime(n=i) for i in range(11, 21)]
primes
```

```

### Chained Operations

```

__ot__run `upper(text=reverse(text="hello"))`

```

---

## Prompt Engineering for Tool Calls

### Pre-Call Instructions

Add context before the tool call to guide the LLM:

```
Calculate the SHA-256 hash of the following text:
__onetool__run sha256(text="hello world")
```

### Post-Call Processing

Request specific formatting or analysis after the tool result:

```
__onetool__run brave.web_search(query="latest AI news", count=5)

Summarise the top 3 results in bullet points.
```

### Structured Output Requests

Combine tool execution with output formatting:

    __onetool__run
    ```python
    results = {
        "hash": sha256(text="hello"),
        "reversed": reverse(text="hello"),
        "length": count_chars(text="hello")
    }
    results
    ```

    Return the results as a markdown table.

---

## Best Practices

Your system prompt should include instructions for reliable tool execution:

```yaml
system_prompt: |
  Never retry successful tool calls to get "better" results.
  If a tool call fails, report the error - do not compute the result yourself.
```

**Why these matter:**

- **No retries on success:** LLMs sometimes want to "improve" results by calling the same tool again. This wastes tokens and can cause loops.
- **No manual computation on failure:** When a tool fails, LLMs often try to compute the answer themselves (e.g., calculating a hash or Fibonacci number). This defeats the purpose of using tools and may produce incorrect results.

---

## Troubleshooting

### "Syntax error at line 1: invalid syntax"

The prefix wasn't stripped properly. Ensure:

1. There's whitespace or a newline after the prefix
2. The code itself is valid Python

### Tool call returns unexpected result

Check that:

1. Function arguments match the expected signature
2. String arguments are properly quoted
3. For multi-line code, the last expression is what you want returned

### Code fence not recognized

Ensure:

1. Opening ` ``` ` is on its own line after the prefix
2. Closing ` ``` ` is on its own line
3. Language hint (e.g., `python`) is optional but recommended