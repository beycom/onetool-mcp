# OneTool Release Snippets

Reusable text for GitHub, PyPI, and marketing.

## Colors

### onetool.color.primary

```text
#0A497C
```

Used for: header, logo

## Brand (Internal)

Project identity — used in README header, logo, internal docs.

### onetool.brand

```text
One tool to rule them all
```

### onetool.brand.lotr

```text
One tool to rule them all, one tool to find them, one tool to bring them all, and in the development bind them.
```

## Pitch (External)

Value proposition — used for GitHub about, PyPI, release notes.

### onetool.pitch

```text
One MCP, unlimited tools.
```

### onetool.pitch.emoji

```text
🧿 One MCP, unlimited tools
```

## Short Descriptions

### github.about

```text
🧿 One MCP, unlimited tools
```

### pypi.description

```text
One MCP, unlimited tools.
```

## Taglines

### onetool.tagline.short

```text
Don't enumerate tools. Execute code.
```

### onetool.tagline.value

```text
98.7% fewer tokens. Same accuracy. 10x lower cost.
```

## Repository

### github.tags

```text
python, mcp, model-context-protocol, mcp-server, llm, code-execution, mcp-tools, agents, token-efficiency, fastmcp, context-rot
```

## Stats

### onetool.stats

```text
- 15 packs
- 90+ tools
- 2 CLIs (ot-serve, ot-bench)
- 98.7% token reduction
- 10x cost reduction
```

## Terminology Style Guide

### Referring to the AI system using tools

Use **"agent"** consistently. Avoid: "LLM", "AI", "model", "Claude", "the AI" when referring to tool-using behavior.

| Context | Term | Example |
|---------|------|---------|
| First mention in a doc | "AI agent" or "the agent (Claude, GPT, etc.)" | "OneTool changes how AI agents use tools." |
| Subsequent mentions | "agent" | "The agent generates code you can review." |
| Headings/taglines | "agent" | "Agent + MCP testing" |
| Technical comparisons | "agent" | "Agent tool selection errors" |

### Exceptions (keep these terms)

| Term | When to use |
|------|-------------|
| **LLM** | Model characteristics: "LLM performance degrades with context length" |
| **LLM-powered** | Describing the engine: "LLM-powered transformation" |
| **`llm.transform`** | Pack/function names (product names) |
| **model** | Configuration: "transform.model", "Gemini model" |
| **Claude Code** | Product name in setup instructions |

### MCP Terminology

Use Anthropic's standard MCP terminology consistently:

| Term | Use for | Not |
|------|---------|-----|
| **MCP server** | A connected tool provider | "MCP tool", "MCP service" |
| **tool definitions** | The JSON schemas sent to agent | "tool schemas", "tool specs" |
| **tool calls** | Individual invocations | "tool requests", "API calls" |
| **tool use** | The practice of using tools | "tool calling" (as a noun) |
| **context window** | The token space | "context", "context budget" |
| **context rot** | Performance degradation from tokens | (OneTool-specific term) |

**Examples:**
- "MCP servers consume tokens through tool definitions"
- "Each tool call requires inference"
- "Tool use accuracy improved to 88%"
- "Context window is limited"

### Examples

**Correct:**
- "The agent generates code you can review before execution"
- "Explicit calls prevent agent tool selection errors"
- "Real agent + MCP testing with ot-bench"
- "LLM performance degrades as tokens increase" (model characteristic)

**Avoid:**
- "The LLM generates code" → "The agent generates code"
- "Guide the LLM" → "Guide the agent"
- "LLM tool selection" → "Agent tool selection"
