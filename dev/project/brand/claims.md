# Marketing Claims

Consistent claims for OneTool marketing, based on benchmark evidence.

## Primary Claims

### Claim Usage Guide

| Context    | Recommended Claim                      |
| ---------- | -------------------------------------- |
| Headlines  | "96% fewer tokens" or "30x lower cost" |
| Cost focus | "$30/server/month in wasted tokens"    |

### $30 per MCP server per month

Each MCP server you add costs approximately $30 per MCP server per month in wasted tokens.

**Assumptions:**

- 18 MCP servers cause ~$485/month overhead ($485 / 18 = $27, rounded to $30)
- Developer workload: 20 working days, 10 conversations/day, 10 turns each
- Model: Claude Opus 4.5 @ $5/M input tokens
- Source: [compare.md](../../../docs/learn/comparison.md)

---

### 97% reduction in token usage (~40x)

OneTool reduces input token usage by ~97% compared to multiple MCP servers.

**Assumptions:**

- One-shot: 47,660 → 1,131 tokens = 97.6% reduction (42x)
- Multi-turn (3 turns): 119,258 → 2,947 tokens = 97.5% reduction (40x)
- Gap widens with more turns (tool definitions resent each turn)
- 18 MCP servers vs OneTool (single tool)
- Measured: February 2026 (raw data: `docs/results/result-20260223-0334.csv`). The benchmark harness (OT Bench) now lives outside this repository; these are the last figures generated from it before externalization.
- Source: [comparison.md](../../../docs/learn/comparison.md)

**Comparison** (industry data from [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)):

| Technique                 | Token Reduction |
| ------------------------- | --------------- |
| **OneTool**               | **97%**         |
| Tool Search Tool          | 85%             |
| Programmatic Tool Calling | 37%             |

---

**Assumptions:**

- 7.35c / 0.30c = 24.5x (presented as "up to 30x" in marketing copy)
- 3-turn conversation
- Source: [compare.md](../../../docs/learn/comparison.md)

---
