# OneTool Brand

Brand assets, messaging, and reference materials for OneTool.

---

## Documents

| Document | Purpose |
|----------|---------|
| **This file** | Snippets, taglines, quick reference |
| [terminology.md](terminology.md) | Terminology style guide |
| [claims.md](claims.md) | Benchmark evidence for marketing claims |
| [external-references.md](external-references.md) | External references and resources |

For user-facing tool pack descriptions, use [docs/reference/tools/index.md](../../../docs/reference/tools/index.md).

**Documentation styling:** See main docs for design system and best practices.

---

## Brand Identity

### Internal Brand

```text
One tool to rule them all
```

### External Pitch

`🧿 One MCP for developers - No tool tax, no context rot.
Configured packs can include Brave, Google grounding, Context7, Excalidraw, Version Checker, Excel, File Ops, Database, Playwright, Chrome utility tools, and more.`

---

## Taglines

### Short

```text
Don't enumerate tools. Execute code.
```

### Value Proposition

```text
96% fewer tokens. 30x lower cost.
```

See [claims.md](claims.md) for benchmark sources.

---

## Key Claims

| Claim | Summary |
|-------|---------|
| **96% token reduction** | 46K → 2K tokens (one-shot), gap widens with turns |
| **30x cost reduction** | 7.35¢ → 0.30¢ per 3-turn conversation |
| **$30/server/month** | Each MCP server wastes ~$30/month in tokens |

Details and methodology: [claims.md](claims.md)

---

## Short Descriptions

```text
🧿 One MCP for developers - No tool tax, no context rot. Configured packs can include Brave, Google grounding, Context7, Excalidraw, Version Checker, Excel, File Ops, Database, Playwright, Chrome utility tools, and more.
```

## GitHub Tags

```text
python, mcp, model-context-protocol, mcp-server, llm, code-execution, mcp-tools, agents, token-efficiency, fastmcp, context-rot
```

---

## Stats

```text
- Current configured inventory: 29 packs, 252 tools (`uv run python scripts/list_tool_inventory.py --output -`)
- 1 CLI (onetool)
- 96% token reduction
- 30x cost reduction
```

---

## Terminology (Quick Reference)

Full guide: [terminology.md](terminology.md)

### Key Rules

| Rule | Example |
|------|---------|
| Use "agent" for tool behavior | "The agent generates code" |
| Use "LLM" for model characteristics | "LLM performance degrades" |
| Use "MCP server" not "MCP tool" | "Connect an MCP server" |
| Use "tool definitions" not "schemas" | "Tool definitions consume tokens" |

### OneTool Terms

| Term | Meaning |
|------|---------|
| **context rot** | Performance degradation from token bloat |
| **pack** | Collection of related tools |
| **explicit calls** | Direct tool invocation via code |
| **snippet** | Reusable code template |
