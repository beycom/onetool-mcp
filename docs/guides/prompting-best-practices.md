# Prompting Best Practices

**Make your LLM reliable. Stop the retry loops.**

Two rules prevent 90% of tool-calling problems. Add them to your system prompt.

## System Prompt Guidelines

Include these instructions in your system prompt:

```yaml
system_prompt: |
  Never retry successful tool calls to get "better" results.
  If a tool call fails, report the error - do not compute the result yourself.
```

**Why these matter:**

- **No retries on success:** LLMs sometimes want to "improve" results by calling the same tool again. This wastes tokens and can cause loops.
- **No manual computation on failure:** When a tool fails, LLMs often try to compute the answer themselves (e.g., calculating a hash). This defeats the purpose of using tools and may produce incorrect results.

## Pre-Call Instructions

Add context before tool calls to guide the LLM:

```
Calculate the SHA-256 hash of the following text:
__onetool__run sha256(text="hello world")
```

## Post-Call Processing

Request specific formatting after tool results:

```
__onetool__run brave.search(query="latest AI news", count=5)

Summarise the top 3 results in bullet points.
```

## Structured Output

Combine tool execution with output formatting:

```
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
```

## Batch Operations

For multiple related queries, use batch functions:

```python
# Instead of multiple calls
brave.search(query="topic 1")
brave.search(query="topic 2")

# Use batch
brave.search_batch(queries=["topic 1", "topic 2"])
```

## Error Handling

When tools return errors:

1. **Report the error** - Don't try to work around it
2. **Check prerequisites** - API keys, dependencies
3. **Validate inputs** - Query length, parameter types

## Token Efficiency

- Use short prefixes (`__ot`) for simple calls
- Use code fences for multi-step operations
- Prefer batch operations over multiple calls