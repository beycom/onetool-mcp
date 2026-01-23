# Why OneTool Exists

**MCP doesn't scale. OneTool fixes this.**

The AI coding landscape faces three converging crises that are fundamentally changing how we build with LLMs.

## The Three Crises

### 1. Context Rot

LLM performance degrades as input tokens increase. [Chroma's research](https://research.trychroma.com/context-rot) found that the 10,000th token is handled less reliably than the 100th.

> "Context must be treated as a finite resource with diminishing marginal returns."
> - [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### 2. MCP Token Bloat

Every MCP server you connect adds thousands of tokens to your context - before you even start talking.

| Setup | Token Cost | Impact |
|-------|------------|--------|
| 5 servers | ~55K | Before any conversation |
| 10+ servers | 100K+ | Context nearly exhausted |
| Tool calls | N loops | Expensive LLM deliberation |

This isn't additive - it's *degradative*. Each server compounds the context rot problem.

### 3. Vibe Coding Collapse

[Collins Dictionary's 2025 Word of the Year](https://en.wikipedia.org/wiki/Vibe_coding) - Andrej Karpathy's term for accepting code "that looks roughly right."

The reality? A [UK study of 120 firms](https://www.secondtalent.com/resources/vibe-coding-statistics/) found **41% more debugging time** at scale. The "Day 2" problem - maintaining AI-generated systems - remains unsolved.

## The Solution

OneTool addresses all three crises with one tool, code execution, and spec-driven development.

### The Numbers

| Metric | Traditional MCP | OneTool | Improvement |
|--------|-----------------|---------|-------------|
| Token usage | 150,000 | 2,000 | **98.7% reduction** |
| Cost per query | $0.025 | $0.002 | **10x cheaper** |
| Tool calls | 5+ | 1 | **Single call** |

### How It Works

```
Traditional MCP:
  Load tools (55K) → Reason → Call tool → Reason → Return
  Total: ~150K tokens, 5+ reasoning loops

OneTool:
  run request → Execute Python → Return
  Total: ~2K tokens, 1 call
```

Instead of loading 50 separate tool schemas, LLMs write Python:

```python
__ot brave.search(query="AI trends 2026")
```

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Fight Context Rot** | MCP tool enumeration consumes 55K-150K tokens. OneTool reduces to ~2K (98.7% reduction). |
| **Code is King** | LLMs write Python to call functions directly. No JSON schema parsing, no tool selection loops. |
| **Explicit Invocation** | You write the code to call APIs - no hoping the LLM guesses the right tool or usage. The `__ot` prefix makes tool calls deterministic and visible. |
| **Batteries Included + Extensible** | 10 namespaces built-in. Add snippets, functions, or new tools by dropping in Python files. |

## The Industry Shift

> "The industry is shifting from vibe coding to agentic engineering."
> - [MIT Technology Review](https://www.technologyreview.com/2025/11/05/1127477/from-vibe-coding-to-context-engineering-2025-in-software-development/)

OneTool is built for that future.

## Key Benefits

- **Token efficiency**: 24x fewer tokens, same accuracy
- **Drop-in tools**: Add Python files, no registration needed
- **AST security**: Code validated before execution - no sandbox escapes
- **Benchmark harness**: Test LLM + MCP combinations rigorously with `ot-bench`
- **Proxy support**: Wrap existing MCP servers through the efficient execution model
