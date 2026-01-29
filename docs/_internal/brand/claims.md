# Marketing Claims

Consistent claims for OneTool marketing, based on benchmark evidence.

## Primary Claims

### Claim Usage Guide

| Context    | Recommended Claim                      |
| ---------- | -------------------------------------- |
| Headlines  | "96% fewer tokens" or "24x lower cost" |
| Cost focus | "$30/server/month in wasted tokens"    |

### $30 per MCP server per month

Each MCP server you add costs approximately $30/month in wasted tokens.

**Assumptions:**

- 18 MCP servers cause ~$485/month overhead ($485 / 18 = $27, rounded to $30)
- Developer workload: 20 working days, 10 conversations/day, 10 turns each
- Model: Claude Opus 4.5 @ $5/M input tokens
- Source: [compare.md](../../learn/comparison.md)

---

### 96% reduction in token usage (25x)

OneTool reduces input token usage by 96% compared to multiple MCP servers.

**Assumptions:**

- One-shot: 46,130 → 1,999 tokens = 95.7% reduction (23x)
- Multi-turn (3 turns): 146,387 → 5,152 tokens = 96.5% reduction (28x)
- Gap widens with more turns (tool definitions resent each turn)
- 18 MCP servers vs OneTool (single tool)
- Source: [compare.md](../../learn/comparison.md)

**Comparison** (industry data from [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)):

| Technique                 | Token Reduction |
| ------------------------- | --------------- |
| **OneTool**               | **96%**         |
| Tool Search Tool          | 85%             |
| Programmatic Tool Calling | 37%             |

---

**Assumptions:**

- 7.35c / 0.30c = 24.5x (rounded to 24x)
- 3-turn conversation
- Source: [compare.md](../../learn/comparison.md)

---
