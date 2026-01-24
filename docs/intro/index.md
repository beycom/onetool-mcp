# Why OneTool Exists

**MCP doesn't scale.**

Here's the problem: every MCP server you add makes your AI dumber. Not in theory - in practice.

## What's actually happening

### Context rot is real

LLM performance degrades as input tokens pile up. [Chroma's research](https://research.trychroma.com/context-rot) measured this: the 10,000th token is handled less reliably than the 100th.

> "Context must be treated as a finite resource with diminishing marginal returns."
> - [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### MCP eats your context for breakfast

Every MCP server you connect adds thousands of tokens before you've said anything.

| Setup | Token Cost | What that means |
| ----- | ---------- | --------------- |
| 5 servers | ~55K | Gone before you type |
| 10+ servers | 100K+ | Context nearly full |
| Tool calls | N loops | LLM deliberation tax |

Each server makes context rot worse, not just bigger.

### Vibe coding catches up with you

[Collins Dictionary's 2025 Word of the Year](https://en.wikipedia.org/wiki/Vibe_coding): Andrej Karpathy's term for accepting code "that looks roughly right."

A [UK study of 120 firms](https://www.secondtalent.com/resources/vibe-coding-statistics/) found 41% more debugging time at scale. Day 2 maintenance of AI-generated code is still an unsolved problem.

## What OneTool does differently

One tool. Code execution. That's basically it.

### The numbers

| Metric | Traditional MCP | OneTool |
| ------ | --------------- | ------- |
| Token usage | 150,000 | 2,000 |
| Cost per query | $0.025 | $0.002 |
| Tool calls | 5+ | 1 |

98.7% fewer tokens. 10x cheaper. One call instead of five.

### How it works

```
Traditional MCP:
  Load tools (55K) → Reason → Call tool → Reason → Return
  Total: ~150K tokens, 5+ reasoning loops

OneTool:
  run request → Execute Python → Return
  Total: ~2K tokens, 1 call
```

Instead of loading 50 tool schemas, LLMs write Python:

```python
__ot brave.search(query="AI trends 2026")
```

## The approach

LLMs write Python to call functions. No JSON schema parsing. No tool selection loops. You see exactly what's being called because you wrote it.

14 packs built-in. Adding your own is dropping a Python file in a folder.

[MIT Technology Review](https://www.technologyreview.com/2025/11/05/1127477/from-vibe-coding-to-context-engineering-2025-in-software-development/) calls this shift "from vibe coding to agentic engineering." Whatever you call it, the token math works out.

## What you get

- 24x fewer tokens, same accuracy
- Drop a Python file, get a new pack
- AST validation before execution
- `ot-bench` for testing LLM + MCP combinations
- Proxy mode wraps existing MCP servers
