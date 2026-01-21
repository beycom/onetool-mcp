---
name: ot
description: Execute OneTool MCP commands. Use when asked to run tools, search the web, query databases, fetch docs, or perform batch operations via OneTool.
argument-hint: [task or command]
allowed-tools: Bash(mcp__onetool__run)
---

Execute OneTool commands with dynamic tool discovery.

## Trigger Syntax

Use `__ot` followed by Python-style calls:

```
__ot foo.bar(x=1)
```

For multi-line code:
```
__ot
```python
x = foo.bar(a=1)
y = baz.qux(b=2)
{"results": [x, y]}
```
```

## Step 1: Discover Tools

**Always discover available tools first.** Tools vary by server configuration.

```
__ot ot.tools(compact=True)
```

Filter by namespace or pattern:
```
__ot ot.tools(ns="brave")
__ot ot.tools(pattern="search")
```

## Step 2: Execute

**Rules:**
- Keyword args only: `foo.bar(x=1)` not `foo.bar(1)`
- Batch when possible: combine operations in one call
- Return last expression for multi-step code

**Batch example:**
```
__ot brave.search_batch(queries=["gold price", "silver price", "copper price"])
```

**Snippet shortcuts** (pre-defined templates):
```
__ot $brv_research topic="commodity prices"
__ot $c7_docs library="facebook/react" topic="hooks"
```

## Critical Rules

1. Pass code exactly as-is - do NOT reimplement
2. Do NOT use subprocess, eval, exec
3. Do NOT expand snippets - OneTool handles `$snippet_name`
4. Do NOT retry successful calls

## Task

$ARGUMENTS

First discover tools, then execute the appropriate commands:
```
__ot ot.tools(compact=True)
```
